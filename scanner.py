"""Music file scanner with metadata extraction using mutagen."""
import os
import time
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtCore import QObject, pyqtSignal, QThread

import database as db

log = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {
    '.mp3', '.flac', '.ogg', '.opus', '.m4a', '.aac', '.wma',
    '.wav', '.aiff', '.aif', '.alac', '.ape', '.mpc', '.wv',
    '.dsf', '.dff', '.mp4', '.mka', '.oga', '.spx', '.tta',
}

# Directories to skip during scan (junk, non-music, system)
_SKIP_DIRS = {
    'books', 'ebooks', 'pdfs', 'documents', 'photos', 'images',
    'videos', 'movies', 'software', 'apps', 'games',
    '.git', '.svn', '__pycache__', 'node_modules',
    '$recycle.bin', 'system volume information',
    'zzpart1', 'zzpart2', 'zzpart3',
}

# Short single-word directory names that are likely junk/spam
# (real music dirs are usually artist/album names, not random words)
_JUNK_WORDS = {
    'alluvion', 'antiseptic', 'aqueduct', 'arrogate', 'benevolent',
    'bifocal', 'bulwark', 'capricious', 'cognizant', 'copious',
    'cumulative', 'deleterious', 'dubious', 'ebullient', 'egregious',
    'extraneous', 'fatuous', 'gratuitous', 'hackneyed', 'iconoclast',
    'impervious', 'insidious', 'juxtapose', 'kaleidoscope',
}


def read_metadata(file_path):
    """Read audio metadata from a file using mutagen. Returns dict or None."""
    try:
        import mutagen
        from mutagen.easyid3 import EasyID3
        from mutagen.flac import FLAC
        from mutagen.mp3 import MP3
        from mutagen.mp4 import MP4
        from mutagen.oggvorbis import OggVorbis
        from mutagen.oggopus import OggOpus
        from mutagen.wavpack import WavPack
        from mutagen.aiff import AIFF

        audio = mutagen.File(file_path, easy=True)
        if audio is None:
            # Try harder
            audio = mutagen.File(file_path)
            if audio is None:
                return None

        info = audio.info if hasattr(audio, 'info') else None
        stat = os.stat(file_path)

        meta = {
            'file_path': str(file_path),
            'file_size': stat.st_size,
            'file_mtime': stat.st_mtime,
            'file_format': Path(file_path).suffix.lstrip('.').upper(),
            'title': '',
            'artist': '',
            'album_artist': '',
            'album': '',
            'track_number': 0,
            'disc_number': 1,
            'year': None,
            'genre': '',
            'composer': '',
            'duration_ms': 0,
            'sample_rate': 0,
            'bit_depth': 0,
            'bitrate': 0,
            'channels': 2,
            'cover_data': None,
        }

        # Duration and audio info
        if info:
            meta['duration_ms'] = int((info.length or 0) * 1000)
            meta['sample_rate'] = getattr(info, 'sample_rate', 0) or 0
            meta['channels'] = getattr(info, 'channels', 2) or 2
            meta['bitrate'] = getattr(info, 'bitrate', 0) or 0
            meta['bit_depth'] = getattr(info, 'bits_per_sample', 0) or 0

        # Tags - handle both easy and regular interfaces
        def get_tag(keys, default=''):
            for key in keys:
                try:
                    val = audio.get(key)
                    if val:
                        if isinstance(val, list):
                            return str(val[0])
                        return str(val)
                except Exception:
                    pass
            return default

        meta['title'] = get_tag(['title', 'TIT2', '\xa9nam']) or Path(file_path).stem
        meta['artist'] = get_tag(['artist', 'TPE1', '\xa9ART', 'ARTIST'])
        meta['album_artist'] = get_tag(['albumartist', 'TPE2', 'aART', 'ALBUMARTIST']) or meta['artist']
        meta['album'] = get_tag(['album', 'TALB', '\xa9alb', 'ALBUM'])
        meta['genre'] = get_tag(['genre', 'TCON', '\xa9gen', 'GENRE'])
        meta['composer'] = get_tag(['composer', 'TCOM', '\xa9wrt', 'COMPOSER'])

        # Track number
        tn = get_tag(['tracknumber', 'TRCK', 'trkn', 'TRACKNUMBER'])
        if tn:
            try:
                meta['track_number'] = int(str(tn).split('/')[0])
            except (ValueError, IndexError):
                pass

        # Disc number
        dn = get_tag(['discnumber', 'TPOS', 'disk', 'DISCNUMBER'])
        if dn:
            try:
                meta['disc_number'] = int(str(dn).split('/')[0])
            except (ValueError, IndexError):
                pass

        # Year
        yr = get_tag(['date', 'TDRC', '\xa9day', 'year', 'DATE'])
        if yr:
            try:
                meta['year'] = int(str(yr)[:4])
            except (ValueError, IndexError):
                pass

        # Cover art extraction
        try:
            raw_audio = mutagen.File(file_path)
            if raw_audio:
                # FLAC
                if hasattr(raw_audio, 'pictures') and raw_audio.pictures:
                    meta['cover_data'] = raw_audio.pictures[0].data
                # MP3 (ID3)
                elif hasattr(raw_audio, 'tags') and raw_audio.tags:
                    for key in raw_audio.tags:
                        if key.startswith('APIC'):
                            meta['cover_data'] = raw_audio.tags[key].data
                            break
                # MP4/M4A
                if not meta['cover_data'] and isinstance(raw_audio, MP4):
                    covr = raw_audio.tags.get('covr')
                    if covr:
                        meta['cover_data'] = bytes(covr[0])
        except Exception:
            pass

        return meta

    except Exception as e:
        log.warning("Failed to read metadata from %s: %s", file_path, e)
        return None


def write_metadata(file_path, updates):
    """Write metadata updates back to an audio file using mutagen.

    Args:
        file_path: Path to the audio file.
        updates: dict with keys like 'composer', 'genre', 'artist',
                 'album_artist', 'album', 'period', 'movement',
                 'form', 'catalogue', 'instruments', 'music_key', 'sub_period'.
                 Only non-None values are written.

    Returns:
        True if successful, False otherwise.
    """
    if not updates or not os.path.exists(file_path):
        return False

    try:
        import mutagen
        from mutagen.id3 import ID3, TCOM, TCON, TPE1, TPE2, TALB, TXXX, ID3NoHeaderError
        from mutagen.flac import FLAC
        from mutagen.mp4 import MP4
        from mutagen.oggvorbis import OggVorbis
        from mutagen.oggopus import OggOpus

        ext = Path(file_path).suffix.lower()

        # --- ID3 (MP3) ---
        if ext == '.mp3':
            try:
                tags = ID3(file_path)
            except ID3NoHeaderError:
                tags = ID3()
            if 'composer' in updates and updates['composer']:
                tags.delall('TCOM')
                tags.add(TCOM(encoding=3, text=[updates['composer']]))
            if 'genre' in updates and updates['genre']:
                tags.delall('TCON')
                tags.add(TCON(encoding=3, text=[updates['genre']]))
            if 'artist' in updates and updates['artist']:
                tags.delall('TPE1')
                tags.add(TPE1(encoding=3, text=[updates['artist']]))
            if 'album_artist' in updates and updates['album_artist']:
                tags.delall('TPE2')
                tags.add(TPE2(encoding=3, text=[updates['album_artist']]))
            if 'album' in updates and updates['album']:
                tags.delall('TALB')
                tags.add(TALB(encoding=3, text=[updates['album']]))
            # Custom fields via TXXX frames
            _custom_fields = {
                'period': 'MUSICOTHEQUE_PERIOD',
                'movement': 'MUSICOTHEQUE_MOVEMENT',
                'sub_period': 'MUSICOTHEQUE_SUB_PERIOD',
                'form': 'MUSICOTHEQUE_FORM',
                'catalogue': 'MUSICOTHEQUE_CATALOGUE',
                'instruments': 'MUSICOTHEQUE_INSTRUMENTS',
                'music_key': 'MUSICOTHEQUE_KEY',
            }
            for field, desc in _custom_fields.items():
                if field in updates and updates[field]:
                    # Remove existing TXXX with this description
                    tags.delall(f'TXXX:{desc}')
                    tags.add(TXXX(encoding=3, desc=desc, text=[str(updates[field])]))
            tags.save(file_path, v2_version=3)
            return True

        # --- FLAC ---
        elif ext == '.flac':
            audio = FLAC(file_path)
            if 'composer' in updates and updates['composer']:
                audio['composer'] = [updates['composer']]
            if 'genre' in updates and updates['genre']:
                audio['genre'] = [updates['genre']]
            if 'artist' in updates and updates['artist']:
                audio['artist'] = [updates['artist']]
            if 'album_artist' in updates and updates['album_artist']:
                audio['albumartist'] = [updates['album_artist']]
            if 'album' in updates and updates['album']:
                audio['album'] = [updates['album']]
            _vorbis_fields = {
                'period': 'MUSICOTHEQUE_PERIOD',
                'movement': 'MUSICOTHEQUE_MOVEMENT',
                'sub_period': 'MUSICOTHEQUE_SUB_PERIOD',
                'form': 'MUSICOTHEQUE_FORM',
                'catalogue': 'MUSICOTHEQUE_CATALOGUE',
                'instruments': 'MUSICOTHEQUE_INSTRUMENTS',
                'music_key': 'MUSICOTHEQUE_KEY',
            }
            for field, tag in _vorbis_fields.items():
                if field in updates and updates[field]:
                    audio[tag] = [str(updates[field])]
            audio.save()
            return True

        # --- OGG/Opus (Vorbis comments) ---
        elif ext in ('.ogg', '.opus', '.oga'):
            try:
                audio = OggOpus(file_path) if ext == '.opus' else OggVorbis(file_path)
            except Exception:
                audio = mutagen.File(file_path)
                if audio is None:
                    return False
            if hasattr(audio, 'tags') and audio.tags is None:
                return False
            if 'composer' in updates and updates['composer']:
                audio['composer'] = [updates['composer']]
            if 'genre' in updates and updates['genre']:
                audio['genre'] = [updates['genre']]
            if 'artist' in updates and updates['artist']:
                audio['artist'] = [updates['artist']]
            if 'album_artist' in updates and updates['album_artist']:
                audio['albumartist'] = [updates['album_artist']]
            if 'album' in updates and updates['album']:
                audio['album'] = [updates['album']]
            _vorbis_fields = {
                'period': 'MUSICOTHEQUE_PERIOD',
                'movement': 'MUSICOTHEQUE_MOVEMENT',
                'sub_period': 'MUSICOTHEQUE_SUB_PERIOD',
                'form': 'MUSICOTHEQUE_FORM',
                'catalogue': 'MUSICOTHEQUE_CATALOGUE',
                'instruments': 'MUSICOTHEQUE_INSTRUMENTS',
                'music_key': 'MUSICOTHEQUE_KEY',
            }
            for field, tag in _vorbis_fields.items():
                if field in updates and updates[field]:
                    audio[tag] = [str(updates[field])]
            audio.save()
            return True

        # --- MP4/M4A ---
        elif ext in ('.m4a', '.mp4', '.aac', '.alac'):
            audio = MP4(file_path)
            if audio.tags is None:
                audio.add_tags()
            if 'composer' in updates and updates['composer']:
                audio.tags['\xa9wrt'] = [updates['composer']]
            if 'genre' in updates and updates['genre']:
                audio.tags['\xa9gen'] = [updates['genre']]
            if 'artist' in updates and updates['artist']:
                audio.tags['\xa9ART'] = [updates['artist']]
            if 'album_artist' in updates and updates['album_artist']:
                audio.tags['aART'] = [updates['album_artist']]
            if 'album' in updates and updates['album']:
                audio.tags['\xa9alb'] = [updates['album']]
            # MP4 custom tags use freeform atoms
            _mp4_fields = {
                'period': '----:com.musicotheque:PERIOD',
                'movement': '----:com.musicotheque:MOVEMENT',
                'sub_period': '----:com.musicotheque:SUB_PERIOD',
                'form': '----:com.musicotheque:FORM',
                'catalogue': '----:com.musicotheque:CATALOGUE',
                'instruments': '----:com.musicotheque:INSTRUMENTS',
                'music_key': '----:com.musicotheque:KEY',
            }
            from mutagen.mp4 import MP4FreeForm
            for field, tag in _mp4_fields.items():
                if field in updates and updates[field]:
                    audio.tags[tag] = [
                        MP4FreeForm(str(updates[field]).encode('utf-8'),
                                    dataformat=MP4FreeForm.FORMAT_UTF8)
                    ]
            audio.save()
            return True

        # Other formats: skip (WAV, AIFF, etc. have limited tag support)
        return False

    except Exception as e:
        log.debug("Failed to write metadata to %s: %s", file_path, e)
        return False


class ScanWorker(QObject):
    """Worker that scans folders for music files."""
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(int, int, int)  # added, updated, removed
    error = pyqtSignal(str)

    def __init__(self, folders=None, full_rescan=False):
        super().__init__()
        self._folders = folders or []
        self._full_rescan = full_rescan
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        """Scan all folders for music files."""
        try:
            added = 0
            updated = 0
            removed = 0

            # Collect all audio files
            all_files = []
            for folder in self._folders:
                if not os.path.isdir(folder):
                    continue
                for root, dirs, files in os.walk(folder):
                    if self._cancelled:
                        break
                    # Skip hidden, junk, and non-music directories
                    dirs[:] = [d for d in dirs
                               if not d.startswith('.')
                               and d.lower() not in _SKIP_DIRS
                               and d.lower() not in _JUNK_WORDS]
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext in AUDIO_EXTENSIONS:
                            fp = os.path.join(root, f)
                            # Skip tiny files (< 10KB = likely junk)
                            try:
                                if os.path.getsize(fp) < 10240:
                                    continue
                            except OSError:
                                continue
                            all_files.append(fp)

            total = len(all_files)
            log.info("Found %d audio files to scan", total)

            # Get existing tracks for change detection
            existing = {}
            for row in db.fetchall("SELECT file_path, file_mtime FROM tracks"):
                existing[row['file_path']] = row['file_mtime']

            seen_paths = set()

            # Process files
            for i, fpath in enumerate(all_files):
                if self._cancelled:
                    break

                # Throttle progress updates (every 50 files) to reduce signal overhead
                if (i + 1) % 50 == 0 or i == 0 or i + 1 == total:
                    self.progress.emit(i + 1, total, os.path.basename(fpath))
                norm_path = os.path.normpath(fpath)
                seen_paths.add(norm_path)

                # Skip if unchanged
                try:
                    mtime = os.path.getmtime(fpath)
                except OSError:
                    continue

                if norm_path in existing and not self._full_rescan:
                    if abs(existing[norm_path] - mtime) < 1:
                        continue

                # Read metadata
                meta = read_metadata(fpath)
                if meta is None:
                    continue

                # Get or create artist
                artist_name = meta['artist'] or 'Unknown Artist'
                artist_id = db.get_or_create_artist(artist_name)

                # Album artist
                album_artist_name = meta['album_artist'] or artist_name
                album_artist_id = db.get_or_create_artist(album_artist_name) if album_artist_name != artist_name else artist_id

                # Get or create album
                album_title = meta['album'] or 'Unknown Album'
                album_id = db.get_or_create_album(
                    album_title, album_artist_id, meta['year'],
                    os.path.dirname(fpath)
                )

                # Store cover art on album if available
                if meta['cover_data']:
                    existing_cover = db.fetchone("SELECT cover_data FROM albums WHERE id = ?", (album_id,))
                    if existing_cover and not existing_cover['cover_data']:
                        db.execute("UPDATE albums SET cover_data = ? WHERE id = ?",
                                   (meta['cover_data'], album_id), commit=True)

                # Update album metadata
                db.execute("""
                    UPDATE albums SET
                        year = COALESCE(?, year),
                        genre = COALESCE(?, genre),
                        total_tracks = MAX(COALESCE(total_tracks, 0), ?),
                        total_discs = MAX(COALESCE(total_discs, 1), ?)
                    WHERE id = ?
                """, (meta['year'], meta['genre'], meta['track_number'], meta['disc_number'], album_id),
                    commit=False)

                # Insert or update track
                if norm_path in existing:
                    db.execute("""
                        UPDATE tracks SET
                            title=?, album_id=?, artist_id=?, album_artist_id=?,
                            track_number=?, disc_number=?, duration_ms=?,
                            file_format=?, file_size=?, sample_rate=?, bit_depth=?,
                            bitrate=?, channels=?, genre=?, year=?, composer=?,
                            scanned_at=datetime('now'), file_mtime=?
                        WHERE file_path=?
                    """, (
                        meta['title'], album_id, artist_id, album_artist_id,
                        meta['track_number'], meta['disc_number'], meta['duration_ms'],
                        meta['file_format'], meta['file_size'], meta['sample_rate'],
                        meta['bit_depth'], meta['bitrate'], meta['channels'],
                        meta['genre'], meta['year'], meta['composer'],
                        mtime, norm_path
                    ), commit=False)
                    updated += 1
                else:
                    db.execute("""
                        INSERT INTO tracks(
                            title, album_id, artist_id, album_artist_id,
                            track_number, disc_number, duration_ms, file_path,
                            file_format, file_size, sample_rate, bit_depth,
                            bitrate, channels, genre, year, composer,
                            scanned_at, file_mtime
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)
                    """, (
                        meta['title'], album_id, artist_id, album_artist_id,
                        meta['track_number'], meta['disc_number'], meta['duration_ms'],
                        norm_path, meta['file_format'], meta['file_size'],
                        meta['sample_rate'], meta['bit_depth'], meta['bitrate'],
                        meta['channels'], meta['genre'], meta['year'], meta['composer'],
                        mtime
                    ), commit=False)
                    added += 1

                # Batch commit every 100
                if (added + updated) % 100 == 0:
                    db.commit()

            db.commit()

            # Remove tracks with missing files
            if not self._cancelled:
                try:
                    all_existing = db.fetchall("SELECT id, file_path FROM tracks")
                    for row in all_existing:
                        if row['file_path'] not in seen_paths and not os.path.exists(row['file_path']):
                            db.execute("DELETE FROM tracks WHERE id = ?", (row['id'],), commit=False)
                            removed += 1
                    if removed:
                        db.commit()
                        # Clean orphan albums and artists
                        db.execute(
                            "DELETE FROM albums WHERE id NOT IN "
                            "(SELECT DISTINCT album_id FROM tracks WHERE album_id IS NOT NULL)",
                            commit=True)
                        db.execute(
                            "DELETE FROM artists WHERE id NOT IN "
                            "(SELECT DISTINCT artist_id FROM tracks WHERE artist_id IS NOT NULL) "
                            "AND id NOT IN "
                            "(SELECT DISTINCT album_artist_id FROM tracks WHERE album_artist_id IS NOT NULL)",
                            commit=True)
                except Exception as e:
                    log.warning("Orphan cleanup error (non-fatal): %s", e)

            log.info("Scan complete: added=%d, updated=%d, removed=%d", added, updated, removed)
            self.finished.emit(added, updated, removed)

        except Exception as e:
            log.exception("Scan error")
            self.error.emit(str(e))
        finally:
            db.close_connection()
