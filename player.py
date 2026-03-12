"""HiFi audio player engine using QMediaPlayer."""
import logging
from enum import Enum, auto
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal, QUrl, Qt, QTimer
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QAudioBufferOutput, QAudioFormat

log = logging.getLogger(__name__)


class RepeatMode(Enum):
    OFF = auto()
    ALL = auto()
    ONE = auto()


class ShuffleMode(Enum):
    OFF = auto()
    ON = auto()


class PlayerState(Enum):
    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()


class AudioPlayer(QObject):
    """High-fidelity audio player with queue management.

    Uses QMediaPlayer for broad format support including FLAC, OGG,
    MP3, M4A, WAV, AIFF, and more via platform codecs.
    """

    # Signals
    state_changed = pyqtSignal(object)       # PlayerState
    position_changed = pyqtSignal(int)        # ms
    duration_changed = pyqtSignal(int)        # ms
    track_changed = pyqtSignal(dict)          # track info dict
    volume_changed = pyqtSignal(int)          # 0-100
    queue_changed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    repeat_changed = pyqtSignal(object)       # RepeatMode
    shuffle_changed = pyqtSignal(object)      # ShuffleMode
    radio_changed = pyqtSignal(dict)          # station info or {} when stopped
    audio_buffer_ready = pyqtSignal(object)   # QAudioBuffer for visualization

    def __init__(self, parent=None):
        super().__init__(parent)

        self._player = QMediaPlayer(self)
        self._audio_output = QAudioOutput(self)
        self._player.setAudioOutput(self._audio_output)

        # Audio buffer output for visualization (Float32 stereo 44100Hz)
        self._buffer_output = None
        try:
            fmt = QAudioFormat()
            fmt.setSampleRate(44100)
            fmt.setChannelCount(2)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Float)
            self._buffer_output = QAudioBufferOutput(fmt, self)
            self._player.setAudioBufferOutput(self._buffer_output)
            self._buffer_output.audioBufferReceived.connect(
                lambda buf: self.audio_buffer_ready.emit(buf)
            )
        except Exception as e:
            log.info("Audio buffer output not available: %s", e)

        # Queue
        self._queue = []           # list of track dicts
        self._original_queue = []  # pre-shuffle order
        self._current_index = -1
        self._history = []         # for back navigation

        # State
        self._repeat = RepeatMode.OFF
        self._shuffle = ShuffleMode.OFF
        self._volume = 80
        self._muted = False
        self._state = PlayerState.STOPPED
        self._streaming = False          # True when playing web radio
        self._current_station = None     # Current radio station dict

        # Apply initial volume
        self._audio_output.setVolume(self._volume / 100.0)

        # Connect signals
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Gapless: preload next track near end
        self._gapless_timer = QTimer(self)
        self._gapless_timer.setSingleShot(True)
        self._gapless_timer.timeout.connect(self._prepare_next)

    # --- Public API ---

    @property
    def state(self):
        return self._state

    @property
    def current_track(self):
        if 0 <= self._current_index < len(self._queue):
            return self._queue[self._current_index]
        return None

    @property
    def current_index(self):
        return self._current_index

    @property
    def queue(self):
        return list(self._queue)

    @property
    def queue_length(self):
        return len(self._queue)

    @property
    def position(self):
        return self._player.position()

    @property
    def duration(self):
        return self._player.duration()

    @property
    def volume(self):
        return self._volume

    @property
    def is_muted(self):
        return self._muted

    @property
    def repeat_mode(self):
        return self._repeat

    @property
    def shuffle_mode(self):
        return self._shuffle

    @property
    def is_streaming(self):
        """True when playing a web radio stream."""
        return self._streaming

    @property
    def current_station(self):
        """Current radio station dict, or None."""
        return self._current_station

    def play_stream(self, station):
        """Play a web radio stream.

        Args:
            station: dict with 'name', 'url', 'country', etc.
        """
        url = station.get('url', '')
        if not url:
            return

        self._streaming = True
        self._current_station = station
        self._reconnect_count = 0
        self._player.setSource(QUrl(url))
        self._player.play()
        self.radio_changed.emit(station)
        log.info("Streaming: %s (%s)", station.get('name', '?'), url)

    def stop_stream(self):
        """Stop web radio streaming and return to normal mode."""
        if self._streaming:
            self._player.stop()
            self._streaming = False
            self._current_station = None
            self.radio_changed.emit({})

    def play_track(self, track, queue=None, index=0):
        """Play a specific track, optionally setting the queue."""
        # Stop streaming if active
        if self._streaming:
            self._streaming = False
            self._current_station = None
            self.radio_changed.emit({})

        if queue is not None:
            self._queue = list(queue)
            self._original_queue = list(queue)
            self._current_index = index
        elif track:
            # Find track in queue or add it
            found = False
            for i, t in enumerate(self._queue):
                if t.get('file_path') == track.get('file_path'):
                    self._current_index = i
                    found = True
                    break
            if not found:
                self._queue.append(track)
                self._original_queue.append(track)
                self._current_index = len(self._queue) - 1

        self._load_and_play(track or self.current_track)
        self.queue_changed.emit()

    def play(self):
        """Resume playback."""
        if self._state == PlayerState.PAUSED:
            self._player.play()
        elif self._state == PlayerState.STOPPED and self.current_track:
            self._load_and_play(self.current_track)

    def pause(self):
        """Pause playback."""
        if self._state == PlayerState.PLAYING:
            self._player.pause()

    def play_pause(self):
        """Toggle play/pause."""
        if self._state == PlayerState.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self):
        """Stop playback."""
        self._player.stop()
        self._gapless_timer.stop()

    def seek(self, position_ms):
        """Seek to position in milliseconds."""
        self._player.setPosition(max(0, position_ms))

    def next(self):
        """Skip to next track."""
        if not self._queue:
            return

        if self._repeat == RepeatMode.ONE:
            # In repeat-one, next still advances
            pass

        if self._current_index < len(self._queue) - 1:
            self._history.append(self._current_index)
            self._current_index += 1
            self._load_and_play(self.current_track)
        elif self._repeat == RepeatMode.ALL:
            self._history.append(self._current_index)
            self._current_index = 0
            self._load_and_play(self.current_track)
        else:
            self.stop()

    def previous(self):
        """Go to previous track or restart current if >3s in."""
        if self._player.position() > 3000:
            self.seek(0)
            return

        if self._history:
            self._current_index = self._history.pop()
            self._load_and_play(self.current_track)
        elif self._current_index > 0:
            self._current_index -= 1
            self._load_and_play(self.current_track)
        else:
            self.seek(0)

    def set_volume(self, vol):
        """Set volume (0-100)."""
        self._volume = max(0, min(100, vol))
        if not self._muted:
            self._audio_output.setVolume(self._volume / 100.0)
        self.volume_changed.emit(self._volume)

    def toggle_mute(self):
        """Toggle mute."""
        self._muted = not self._muted
        self._audio_output.setVolume(0.0 if self._muted else self._volume / 100.0)
        self.volume_changed.emit(0 if self._muted else self._volume)

    def set_muted(self, muted):
        """Set mute state."""
        self._muted = muted
        self._audio_output.setVolume(0.0 if self._muted else self._volume / 100.0)
        self.volume_changed.emit(0 if self._muted else self._volume)

    def cycle_repeat(self):
        """Cycle through repeat modes: OFF -> ALL -> ONE -> OFF."""
        modes = [RepeatMode.OFF, RepeatMode.ALL, RepeatMode.ONE]
        idx = modes.index(self._repeat)
        self._repeat = modes[(idx + 1) % 3]
        self.repeat_changed.emit(self._repeat)

    def toggle_shuffle(self):
        """Toggle shuffle mode."""
        import random
        if self._shuffle == ShuffleMode.OFF:
            self._shuffle = ShuffleMode.ON
            current = self.current_track
            self._original_queue = list(self._queue)
            remaining = [t for i, t in enumerate(self._queue) if i != self._current_index]
            random.shuffle(remaining)
            if current:
                self._queue = [current] + remaining
                self._current_index = 0
            else:
                self._queue = remaining
        else:
            self._shuffle = ShuffleMode.OFF
            current = self.current_track
            self._queue = list(self._original_queue)
            if current:
                for i, t in enumerate(self._queue):
                    if t.get('file_path') == current.get('file_path'):
                        self._current_index = i
                        break
        self.shuffle_changed.emit(self._shuffle)
        self.queue_changed.emit()

    def set_queue(self, tracks, play_index=0):
        """Replace the queue with new tracks."""
        self._queue = list(tracks)
        self._original_queue = list(tracks)
        self._current_index = play_index if tracks else -1
        self._history.clear()
        self.queue_changed.emit()

    def add_to_queue(self, tracks):
        """Append tracks to the end of the queue."""
        if isinstance(tracks, dict):
            tracks = [tracks]
        self._queue.extend(tracks)
        self._original_queue.extend(tracks)
        self.queue_changed.emit()

    def remove_from_queue(self, index):
        """Remove track at index from queue."""
        if 0 <= index < len(self._queue):
            self._queue.pop(index)
            if index < self._current_index:
                self._current_index -= 1
            elif index == self._current_index:
                if self._current_index >= len(self._queue):
                    self._current_index = len(self._queue) - 1
            self.queue_changed.emit()

    def clear_queue(self):
        """Clear the playback queue."""
        self.stop()
        self._queue.clear()
        self._original_queue.clear()
        self._history.clear()
        self._current_index = -1
        self.queue_changed.emit()

    # --- Internal ---

    def _load_and_play(self, track):
        """Load a track and start playback."""
        if not track:
            return

        file_path = track.get('file_path', '')
        if not file_path or not Path(file_path).exists():
            log.warning("File not found: %s", file_path)
            self.error_occurred.emit(f"File not found: {file_path}")
            return

        url = QUrl.fromLocalFile(str(file_path))
        self._player.setSource(url)
        self._player.play()
        self.track_changed.emit(track)
        log.info("Playing: %s", file_path)

    def _prepare_next(self):
        """Pre-check next track exists for smoother transition."""
        next_idx = self._current_index + 1
        if next_idx < len(self._queue):
            next_track = self._queue[next_idx]
            fp = next_track.get('file_path', '')
            if not Path(fp).exists():
                log.warning("Next track missing: %s", fp)

    def _on_position_changed(self, position):
        """Handle position updates."""
        self.position_changed.emit(position)

        # Schedule gapless preparation 5s before end
        dur = self._player.duration()
        if dur > 5000 and position > dur - 5000 and not self._gapless_timer.isActive():
            self._gapless_timer.start(100)

    def _on_duration_changed(self, duration):
        """Handle duration change."""
        self.duration_changed.emit(duration)

    def _on_media_status_changed(self, status):
        """Handle media status - mainly for end of track."""
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._on_track_finished()

    def _on_track_finished(self):
        """Handle end of track - advance queue."""
        if self._repeat == RepeatMode.ONE:
            self.seek(0)
            self._player.play()
            return

        if self._current_index < len(self._queue) - 1:
            self._history.append(self._current_index)
            self._current_index += 1
            self._load_and_play(self.current_track)
        elif self._repeat == RepeatMode.ALL and self._queue:
            self._history.append(self._current_index)
            self._current_index = 0
            self._load_and_play(self.current_track)
        else:
            self._state = PlayerState.STOPPED
            self.state_changed.emit(self._state)

    def _on_playback_state_changed(self, state):
        """Map QMediaPlayer states to our PlayerState."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._state = PlayerState.PLAYING
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self._state = PlayerState.PAUSED
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self._state = PlayerState.STOPPED
        self.state_changed.emit(self._state)

    def _on_error(self, error, message=''):
        """Handle player errors, with auto-reconnect for streams."""
        msg = self._player.errorString() or str(error)
        log.error("Player error: %s", msg)

        if self._streaming and self._current_station:
            # Auto-reconnect after 3 seconds for stream errors
            reconnect_count = getattr(self, '_reconnect_count', 0)
            if reconnect_count < 3:
                self._reconnect_count = reconnect_count + 1
                log.info("Stream reconnect attempt %d/3...", self._reconnect_count)
                QTimer.singleShot(3000, self._reconnect_stream)
                return
            else:
                log.warning("Stream reconnect failed after 3 attempts")
                self._reconnect_count = 0
                self.stop_stream()

        self.error_occurred.emit(msg)

    def _reconnect_stream(self):
        """Attempt to reconnect to current radio stream."""
        if self._streaming and self._current_station:
            url = self._current_station.get('url', '')
            if url:
                log.info("Reconnecting to %s", self._current_station.get('name', '?'))
                self._player.setSource(QUrl(url))
                self._player.play()
