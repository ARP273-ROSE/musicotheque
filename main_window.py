"""Main window for MusicOthèque."""
import os
import sys
import subprocess
import platform
import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTreeWidget, QTreeWidgetItem, QTableWidget, QTableWidgetItem,
    QTableView, QHeaderView, QLabel, QPushButton, QSlider, QLineEdit,
    QStatusBar, QMenuBar, QMenu, QToolBar, QFileDialog,
    QMessageBox, QProgressBar, QAbstractItemView, QComboBox,
    QStyle, QApplication, QSizePolicy, QFrame, QStackedWidget,
    QDialog, QTextBrowser, QDialogButtonBox, QGroupBox,
    QFormLayout, QSpinBox, QCheckBox, QInputDialog,
    QStyledItemDelegate
)
from PyQt6.QtCore import (
    Qt, QThread, QTimer, QSize, pyqtSignal, QSettings,
    QAbstractTableModel, QModelIndex, QMimeData, QUrl
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QPixmap, QImage, QIcon, QFont,
    QPalette, QColor
)

import database as db
from i18n import T, get_lang, set_lang, TX
from player import AudioPlayer, PlayerState, RepeatMode, ShuffleMode
from scanner import ScanWorker, write_metadata
from itunes_import import ITunesImportWorker, ITunesPodcastImportWorker
from metadata_fetch import MetadataFetchWorker
from backup_manager import backup_database, restore_database, list_backups
from podcast_manager import (PodcastDownloadWorker, PodcastSubscribeWorker,
                              parse_rss_feed, search_podcasts)
from web_radio import (RADIO_STATIONS, CATEGORIES, get_stations_by_category,
                        station_display_name)

log = logging.getLogger(__name__)

# Minimum listen time (seconds) before incrementing play count
PLAY_COUNT_THRESHOLD_S = 30

# Column definitions for podcast episodes table
EPISODE_COLUMNS = [
    ('col_title', 'title', 300),
    ('col_podcast', 'podcast_title', 180),
    ('col_published', 'published_at', 100),
    ('col_duration', 'duration_ms', 70),
    ('col_listened', 'listened', 60),
    ('col_downloaded', 'file_path', 60),
]

# All available columns: (i18n_key, db_key, default_width, visible_by_default)
ALL_COLUMNS = [
    ('col_disc_num', 'disc_number', 40, False),
    ('col_track_num', 'track_number', 40, True),
    ('col_title', 'title', 280, True),
    ('col_artist', 'artist_name', 180, True),
    ('col_album', 'album_title', 180, True),
    ('col_duration', 'duration_ms', 70, True),
    ('col_year', 'year', 55, True),
    ('col_genre', 'genre', 100, True),
    ('col_composer', 'composer', 140, False),
    ('col_period', 'period', 100, False),
    ('col_movement', 'movement', 110, False),
    ('col_sub_period', 'sub_period', 100, False),
    ('col_form', 'form', 90, False),
    ('col_catalogue', 'catalogue', 90, False),
    ('col_instruments', 'instruments', 110, False),
    ('col_music_key', 'music_key', 70, False),
    ('col_format', 'file_format', 55, True),
    ('col_bitrate', 'bitrate', 70, True),
    ('col_sample_rate', 'sample_rate', 80, True),
    ('col_bit_depth', 'bit_depth', 55, True),
    ('col_channels', 'channels', 55, False),
    ('col_file_size', 'file_size', 70, False),
    ('col_play_count', 'play_count', 50, True),
    ('col_rating', 'rating', 50, True),
    ('col_added_at', 'added_at', 100, False),
    ('col_file_path', 'file_path', 200, False),
]

# Default visible columns (for backward compat)
DEFAULT_VISIBLE = {c[1] for c in ALL_COLUMNS if c[3]}

# Numeric columns that should sort numerically
NUMERIC_KEYS = {'track_number', 'disc_number', 'duration_ms', 'bitrate', 'sample_rate',
                'bit_depth', 'play_count', 'year', 'rating', 'channels', 'file_size'}


def _sort_key(text):
    """Generate a sort key that handles accents and case correctly."""
    import unicodedata
    # NFD decomposition strips accents: É -> E + combining accent
    nfkd = unicodedata.normalize('NFKD', text.lower())
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


class TrackTableModel(QAbstractTableModel):
    """High-performance model for 40K+ tracks. No widget items created."""

    _CH_MAP = {1: 'Mono', 2: 'Stereo', 6: '5.1', 8: '7.1'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks = []
        self._columns = ALL_COLUMNS

    def setTracks(self, tracks):
        """Replace all data — instant, no item creation."""
        self.beginResetModel()
        self._tracks = tracks
        self.endResetModel()

    def tracks(self):
        return self._tracks

    def trackAt(self, row):
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def rowCount(self, parent=QModelIndex()):
        return len(self._tracks)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row < 0 or row >= len(self._tracks):
            return None
        track = self._tracks[row]
        key = self._columns[col][1]
        val = track.get(key, '')

        if role == Qt.ItemDataRole.DisplayRole:
            return self._format(key, val)
        elif role == Qt.ItemDataRole.UserRole:
            return track
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if key in NUMERIC_KEYS:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return T(self._columns[section][0])
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        """Sort by column — operates on the backing list directly."""
        if not self._tracks:
            return
        self.layoutAboutToBeChanged.emit()
        key = self._columns[column][1]
        reverse = (order == Qt.SortOrder.DescendingOrder)
        if key in NUMERIC_KEYS:
            self._tracks.sort(key=lambda t: t.get(key, 0) or 0, reverse=reverse)
        else:
            self._tracks.sort(
                key=lambda t: _sort_key(str(t.get(key, '') or '')),
                reverse=reverse
            )
        self.layoutChanged.emit()

    def flags(self, index):
        """Enable drag for all items."""
        default = super().flags(index)
        if index.isValid():
            return default | Qt.ItemFlag.ItemIsDragEnabled
        return default

    def mimeTypes(self):
        return ['text/uri-list']

    def mimeData(self, indexes):
        """Provide file URLs for drag & drop to external apps."""
        mime = QMimeData()
        urls = []
        seen = set()
        for idx in indexes:
            if idx.column() != 0:
                continue
            track = self.trackAt(idx.row())
            if not track:
                continue
            fp = track.get('file_path', '')
            if fp and fp not in seen and os.path.exists(fp):
                seen.add(fp)
                urls.append(QUrl.fromLocalFile(fp))
        mime.setUrls(urls)
        return mime

    def _format(self, key, val):
        """Format a cell value for display."""
        if key == 'duration_ms':
            return format_duration(val)
        if key == 'bitrate':
            return format_bitrate(val)
        if key == 'sample_rate':
            return format_sample_rate(val)
        if key == 'bit_depth':
            return f"{val}-bit" if val else ''
        if key == 'file_size':
            return format_file_size(val) if val else ''
        if key == 'channels':
            return self._CH_MAP.get(val, str(val)) if val else ''
        if key == 'rating':
            return '\u2605' * val if val else ''
        if key in NUMERIC_KEYS:
            return str(val) if val else ''
        return str(val) if val else ''


class EpisodeTableModel(QAbstractTableModel):
    """Lightweight model for podcast episodes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._episodes = []

    def setEpisodes(self, episodes):
        self.beginResetModel()
        self._episodes = episodes
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return len(self._episodes)

    def columnCount(self, parent=QModelIndex()):
        return len(EPISODE_COLUMNS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        if row < 0 or row >= len(self._episodes):
            return None
        ep = self._episodes[row]
        key = EPISODE_COLUMNS[col][1]
        val = ep.get(key, '')

        if role == Qt.ItemDataRole.DisplayRole:
            if key == 'duration_ms':
                return format_duration(val)
            if key == 'published_at':
                return str(val)[:10] if val else ''
            if key == 'listened':
                return '\u2713' if val else ''
            if key == 'file_path':
                return '\U0001f4be' if val else ''
            return str(val) if val else ''
        elif role == Qt.ItemDataRole.UserRole:
            return ep
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if key in ('duration_ms', 'listened', 'file_path', 'published_at'):
                return int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return T(EPISODE_COLUMNS[section][0])
        return None

    def sort(self, column, order=Qt.SortOrder.AscendingOrder):
        if not self._episodes:
            return
        self.layoutAboutToBeChanged.emit()
        key = EPISODE_COLUMNS[column][1]
        reverse = (order == Qt.SortOrder.DescendingOrder)
        self._episodes.sort(
            key=lambda e: e.get(key, '') or '',
            reverse=reverse
        )
        self.layoutChanged.emit()


def format_duration(ms):
    """Format milliseconds to mm:ss or h:mm:ss."""
    if not ms or ms <= 0:
        return '0:00'
    s = ms // 1000
    m = s // 60
    s = s % 60
    h = m // 60
    if h > 0:
        m = m % 60
        return f'{h}:{m:02d}:{s:02d}'
    return f'{m}:{s:02d}'


def format_duration_long(ms):
    """Format milliseconds to human-readable d/h/m for large totals."""
    if not ms or ms <= 0:
        return '0 min'
    total_s = ms // 1000
    total_m = total_s // 60
    total_h = total_m // 60
    m = total_m % 60
    d = total_h // 24
    h = total_h % 24
    lang = get_lang()
    if d > 0:
        day_label = 'j' if lang == 'fr' else 'd'
        return f"{d}{day_label} {h}h {m:02d}min"
    if total_h > 0:
        return f"{total_h}h {m:02d}min"
    return f"{total_m} min"


def format_size(size_bytes):
    """Format bytes to human-readable size."""
    if not size_bytes:
        return '0 B'
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if abs(size_bytes) < 1024.0:
            return f'{size_bytes:.1f} {unit}'
        size_bytes /= 1024.0
    return f'{size_bytes:.1f} PB'


def format_bitrate(bps):
    """Format bitrate."""
    if not bps:
        return ''
    if bps >= 1000:
        return f'{bps // 1000} kbps'
    return f'{bps} bps'


def format_sample_rate(sr):
    """Format sample rate."""
    if not sr:
        return ''
    if sr >= 1000:
        return f'{sr / 1000:.1f} kHz'
    return f'{sr} Hz'


def format_file_size(size_bytes):
    """Format file size in human-readable form."""
    if not size_bytes:
        return ''
    if size_bytes < 1024:
        return f'{size_bytes} B'
    if size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.0f} KB'
    if size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.1f} MB'
    return f'{size_bytes / (1024 * 1024 * 1024):.2f} GB'


def cover_to_pixmap(cover_data, size=200):
    """Convert cover art bytes to QPixmap."""
    if not cover_data:
        return None
    try:
        img = QImage()
        img.loadFromData(cover_data)
        if img.isNull():
            return None
        return QPixmap.fromImage(img).scaled(
            size, size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
    except Exception:
        return None


# Fields editable in single-track mode (all)
_SINGLE_FIELDS = [
    ('meta_title', 'title'),
    ('meta_artist', 'artist_name'),
    ('meta_album_artist', 'album_artist'),
    ('meta_album', 'album_title'),
    ('meta_genre', 'genre'),
    ('meta_year', 'year'),
    ('meta_track_num', 'track_number'),
    ('meta_disc_num', 'disc_number'),
    ('meta_composer', 'composer'),
    ('meta_period', 'period'),
    ('meta_movement', 'movement'),
    ('meta_sub_period', 'sub_period'),
    ('meta_form', 'form'),
    ('meta_catalogue', 'catalogue'),
    ('meta_instruments', 'instruments'),
    ('meta_music_key', 'music_key'),
]

# Fields editable in multi-track mode (shared/batch fields only)
_MULTI_FIELDS = [
    ('meta_artist', 'artist_name'),
    ('meta_album_artist', 'album_artist'),
    ('meta_album', 'album_title'),
    ('meta_genre', 'genre'),
    ('meta_year', 'year'),
    ('meta_composer', 'composer'),
    ('meta_period', 'period'),
    ('meta_movement', 'movement'),
    ('meta_sub_period', 'sub_period'),
    ('meta_form', 'form'),
    ('meta_catalogue', 'catalogue'),
    ('meta_instruments', 'instruments'),
    ('meta_music_key', 'music_key'),
]

# DB column → scanner write_metadata key mapping
_DB_TO_SCANNER = {
    'artist_name': 'artist',
    'album_artist': 'album_artist',
    'album_title': 'album',
    'title': 'title',
    'genre': 'genre',
    'composer': 'composer',
    'period': 'period',
    'movement': 'movement',
    'sub_period': 'sub_period',
    'form': 'form',
    'catalogue': 'catalogue',
    'instruments': 'instruments',
    'music_key': 'music_key',
}


class MetadataEditDialog(QDialog):
    """iTunes-style metadata editor. Adapts to single or multi-track selection."""

    def __init__(self, tracks, parent=None):
        super().__init__(parent)
        self._tracks = tracks
        self._multi = len(tracks) > 1
        self._fields = _MULTI_FIELDS if self._multi else _SINGLE_FIELDS
        self._edits = {}  # db_key → QLineEdit/QSpinBox

        if self._multi:
            self.setWindowTitle(T('edit_metadata_multi', count=len(tracks)))
        else:
            self.setWindowTitle(T('edit_metadata_single'))
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Info banner for multi-edit
        if self._multi:
            info = QLabel(T('edit_metadata_multi', count=len(tracks)))
            info.setStyleSheet("font-weight: bold; padding: 6px; color: #aaa;")
            layout.addWidget(info)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        for i18n_key, db_key in self._fields:
            label = T(i18n_key)
            if db_key in ('year', 'track_number', 'disc_number'):
                widget = QSpinBox()
                widget.setRange(0, 99999)
                widget.setSpecialValueText('')  # Show empty when 0
                if not self._multi:
                    val = tracks[0].get(db_key, 0) or 0
                    widget.setValue(int(val))
                else:
                    # For multi: show common value or 0 (keep original)
                    values = {t.get(db_key, 0) or 0 for t in tracks}
                    if len(values) == 1:
                        widget.setValue(values.pop())
                    else:
                        widget.setValue(0)
                        widget.setToolTip(T('meta_keep_original'))
                self._edits[db_key] = widget
            else:
                widget = QLineEdit()
                if not self._multi:
                    widget.setText(str(tracks[0].get(db_key, '') or ''))
                else:
                    # Show common value or placeholder
                    values = {str(t.get(db_key, '') or '') for t in tracks}
                    if len(values) == 1:
                        widget.setText(values.pop())
                    else:
                        widget.setPlaceholderText(T('meta_keep_original'))
                self._edits[db_key] = widget
            form.addRow(label + ':', widget)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_changes(self):
        """Return dict of {db_key: new_value} for fields that were modified.
        For multi-edit, only returns fields where user typed something."""
        changes = {}
        for db_key, widget in self._edits.items():
            if isinstance(widget, QSpinBox):
                val = widget.value()
                if self._multi:
                    # In multi-mode, 0 = keep original (unless all were 0)
                    original_values = {t.get(db_key, 0) or 0 for t in self._tracks}
                    if len(original_values) == 1 and original_values.pop() == val:
                        continue  # unchanged
                    if val == 0 and len(original_values) > 1:
                        continue  # user didn't change mixed value
                    changes[db_key] = val
                else:
                    orig = self._tracks[0].get(db_key, 0) or 0
                    if val != int(orig):
                        changes[db_key] = val
            else:
                val = widget.text().strip()
                if self._multi:
                    # Empty = keep original (placeholder shown)
                    if not val:
                        continue
                    # Check if it's the same as the common value
                    values = {str(t.get(db_key, '') or '') for t in self._tracks}
                    if len(values) == 1 and values.pop() == val:
                        continue
                    changes[db_key] = val
                else:
                    orig = str(self._tracks[0].get(db_key, '') or '')
                    if val != orig:
                        changes[db_key] = val
        return changes


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._settings = QSettings('MusicOtheque', 'MusicOtheque')
        self._player = AudioPlayer(self)

        # Restore saved audio device
        saved_device = db.fetchone("SELECT value FROM config WHERE key = 'audio_device'")
        if saved_device and saved_device['value']:
            self._player.set_audio_device_by_name(saved_device['value'])

        # Worker threads and workers (all initialized to None)
        self._scan_thread = None
        self._scan_worker = None
        self._import_thread = None
        self._import_worker = None
        self._fetch_thread = None
        self._fetch_worker = None
        self._podcast_thread = None
        self._podcast_import_thread = None
        self._podcast_import_worker = None
        self._podcast_refresh_worker = None
        self._podcast_subscribe_thread = None
        self._podcast_subscribe_worker = None
        self._harmonize_thread = None
        self._harmonize_worker = None
        self._cd_thread = None
        self._cd_worker = None

        # View state
        self._current_view = 'all_tracks'
        self._current_filter = None
        self._all_tracks_cache = []
        self._content_mode = 'music'  # 'music' or 'podcasts'
        self._playing_track_path = None
        self._playing_track_start = 0

        self._setup_ui()
        self._setup_menus()
        self._connect_signals()
        self._restore_state()
        self._refresh_library()

        # Auto-backup timer (every 5 minutes for transparent continuous backup)
        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._backup_timer.start(5 * 60 * 1000)

        # Library file watcher — monitors folders for changes
        from library_watcher import LibraryWatcher
        self._watcher = LibraryWatcher(self)
        self._watcher.changes_detected.connect(self._on_watcher_changes)
        self._watcher.paths_relocated.connect(self._on_watcher_relocated)
        self._watcher.scan_requested.connect(self._on_watcher_scan)
        self._watcher.start()

    def _setup_ui(self):
        """Build the main UI layout."""
        self.setWindowTitle(T('app_name'))
        self.setMinimumSize(1100, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Search bar at top
        search_bar = QFrame()
        search_bar.setFrameShape(QFrame.Shape.NoFrame)
        search_layout = QHBoxLayout(search_bar)
        search_layout.setContentsMargins(8, 4, 8, 4)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(T('search'))
        self._search_input.setToolTip(T('search_tip'))
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMaximumWidth(350)
        search_layout.addWidget(self._search_input)
        search_layout.addStretch()

        # Library stats label
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #888; font-size: 11px;")
        search_layout.addWidget(self._stats_label)

        main_layout.addWidget(search_bar)

        # Main splitter: sidebar | content
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Sidebar ---
        self._sidebar = QTreeWidget()
        self._sidebar.setHeaderHidden(True)
        self._sidebar.setMinimumWidth(180)
        self._sidebar.setMaximumWidth(300)
        self._sidebar.setToolTip(T('library'))
        self._sidebar.setIndentation(16)
        self._sidebar.setAnimated(True)
        self._build_sidebar()

        # --- Content area ---
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Track table (QTableView + model for 40K+ track performance)
        self._track_model = TrackTableModel(self)
        self._track_table = QTableView()
        self._track_table.setModel(self._track_model)
        self._track_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._track_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._track_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._track_table.setAlternatingRowColors(True)
        self._track_table.setSortingEnabled(True)
        self._track_table.verticalHeader().setVisible(False)
        self._track_table.verticalHeader().setDefaultSectionSize(26)
        self._track_table.setShowGrid(False)
        self._track_table.setDragEnabled(True)
        self._track_table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self._track_table.setDefaultDropAction(Qt.DropAction.CopyAction)

        # Load saved column visibility or use defaults
        settings = QSettings('MusicOtheque', 'MusicOtheque')
        saved_vis = settings.value('visible_columns', None)
        if saved_vis and isinstance(saved_vis, list):
            self._visible_columns = set(saved_vis)
        else:
            self._visible_columns = set(DEFAULT_VISIBLE)

        # Column widths and visibility
        header = self._track_table.horizontalHeader()
        title_col_idx = 2
        for i, (_, key, w, _) in enumerate(ALL_COLUMNS):
            self._track_table.setColumnWidth(i, w)
            if key not in self._visible_columns:
                self._track_table.setColumnHidden(i, True)
            if key == 'title':
                title_col_idx = i
        header.setStretchLastSection(False)
        header.setSectionResizeMode(title_col_idx, QHeaderView.ResizeMode.Stretch)

        # Right-click on header for column chooser
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self._on_header_context_menu)

        # Episode mode flag (for switching between track/episode views)
        self._episode_mode = False

        content_layout.addWidget(self._track_table, 1)

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(content)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([200, 800])

        main_layout.addWidget(self._splitter, 1)

        # --- Audio visualizer (hidden by default) ---
        self._visualizer_panel = None
        self._audio_analyzer = None

        # --- Player bar at bottom ---
        self._player_bar = self._build_player_bar()
        main_layout.addWidget(self._player_bar)

        # Status bar
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._progress_bar = QProgressBar()
        self._progress_bar.setMaximumWidth(200)
        self._progress_bar.setMaximumHeight(16)
        self._progress_bar.hide()
        self._status_bar.addPermanentWidget(self._progress_bar)
        self._status_bar.showMessage(T('ready'))

    def _build_sidebar(self):
        """Build the library navigation sidebar."""
        self._sidebar.clear()

        # Library section
        lib_root = QTreeWidgetItem(self._sidebar, [T('library')])
        lib_root.setExpanded(True)
        font = lib_root.font(0)
        font.setBold(True)
        lib_root.setFont(0, font)

        self._item_all_tracks = QTreeWidgetItem(lib_root, [T('view_all_tracks')])
        self._item_all_tracks.setData(0, Qt.ItemDataRole.UserRole, 'all_tracks')
        self._item_all_tracks.setToolTip(0, T('sidebar_all_tracks_tip'))

        self._item_artists = QTreeWidgetItem(lib_root, [T('view_artists')])
        self._item_artists.setData(0, Qt.ItemDataRole.UserRole, 'artists')
        self._item_artists.setToolTip(0, T('sidebar_artists_tip'))

        self._item_albums = QTreeWidgetItem(lib_root, [T('view_albums')])
        self._item_albums.setData(0, Qt.ItemDataRole.UserRole, 'albums')
        self._item_albums.setToolTip(0, T('sidebar_albums_tip'))

        self._item_genres = QTreeWidgetItem(lib_root, [T('view_genres')])
        self._item_genres.setData(0, Qt.ItemDataRole.UserRole, 'genres')
        self._item_genres.setToolTip(0, T('sidebar_genres_tip'))

        # Periods section (musical eras)
        self._item_periods = QTreeWidgetItem(lib_root, [T('view_periods')])
        self._item_periods.setData(0, Qt.ItemDataRole.UserRole, 'periods')
        self._item_periods.setToolTip(0, T('sidebar_periods_tip'))

        # Playlists section
        self._pl_root = QTreeWidgetItem(self._sidebar, [T('view_playlists')])
        self._pl_root.setExpanded(True)
        self._pl_root.setToolTip(0, T('sidebar_playlists_tip'))
        font2 = self._pl_root.font(0)
        font2.setBold(True)
        self._pl_root.setFont(0, font2)

        self._refresh_playlists_sidebar()

        # Podcasts section
        self._pod_root = QTreeWidgetItem(self._sidebar, [T('podcasts')])
        self._pod_root.setExpanded(False)
        self._pod_root.setToolTip(0, T('sidebar_podcasts_tip'))
        font3 = self._pod_root.font(0)
        font3.setBold(True)
        self._pod_root.setFont(0, font3)

        self._item_all_episodes = QTreeWidgetItem(self._pod_root, [T('podcast_episodes')])
        self._item_all_episodes.setData(0, Qt.ItemDataRole.UserRole, 'all_episodes')

        self._refresh_podcasts_sidebar()

        # Web Radio section
        self._radio_root = QTreeWidgetItem(self._sidebar, [T('web_radio')])
        self._radio_root.setExpanded(False)
        self._radio_root.setToolTip(0, T('web_radio_tip'))
        font_radio = self._radio_root.font(0)
        font_radio.setBold(True)
        self._radio_root.setFont(0, font_radio)

        for cat_id, cat_key in CATEGORIES:
            stations = get_stations_by_category(cat_id)
            if not stations:
                continue
            cat_item = QTreeWidgetItem(self._radio_root, [T(cat_key)])
            cat_item.setExpanded(False)
            for station in stations:
                s_item = QTreeWidgetItem(cat_item, [station_display_name(station)])
                s_item.setData(0, Qt.ItemDataRole.UserRole, f"radio:{station['url']}")
                s_item.setToolTip(0, f"{station['name']} ({station['country']})")

    def _refresh_playlists_sidebar(self):
        """Refresh playlists in sidebar."""
        # Remove old playlist items
        while self._pl_root.childCount():
            self._pl_root.removeChild(self._pl_root.child(0))

        playlists = db.fetchall("SELECT id, name FROM playlists ORDER BY name")
        for pl in playlists:
            item = QTreeWidgetItem(self._pl_root, [pl['name']])
            item.setData(0, Qt.ItemDataRole.UserRole, f"playlist:{pl['id']}")

    def _refresh_podcasts_sidebar(self):
        """Refresh podcast shows in sidebar."""
        # Keep "All Episodes" item, remove show items
        while self._pod_root.childCount() > 1:
            self._pod_root.removeChild(self._pod_root.child(1))

        podcasts = db.fetchall("""
            SELECT p.id, p.title, COUNT(e.id) as ep_count
            FROM podcasts p
            LEFT JOIN podcast_episodes e ON e.podcast_id = p.id
            GROUP BY p.id ORDER BY p.title
        """)
        for pod in podcasts:
            label = f"{pod['title']} ({pod['ep_count']})"
            item = QTreeWidgetItem(self._pod_root, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, f"podcast:{pod['id']}")

    def _build_player_bar(self):
        """Build the bottom player bar with controls."""
        bar = QFrame()
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar.setMinimumHeight(80)
        bar.setMaximumHeight(90)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)

        # Cover art
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(64, 64)
        self._cover_label.setStyleSheet("background: #222; border-radius: 4px;")
        self._cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cover_label.setToolTip(T('cover_tip'))
        layout.addWidget(self._cover_label)

        # Track info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self._track_title_label = QLabel('')
        self._track_title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._track_title_label.setMaximumWidth(250)
        self._track_artist_label = QLabel('')
        self._track_artist_label.setStyleSheet("color: #888; font-size: 11px;")
        self._track_artist_label.setMaximumWidth(250)
        info_layout.addStretch()
        info_layout.addWidget(self._track_title_label)
        info_layout.addWidget(self._track_artist_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)
        layout.addStretch()

        # Transport controls
        ctrl_layout = QVBoxLayout()
        ctrl_layout.setSpacing(2)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addStretch()

        self._btn_shuffle = QPushButton('🔀')
        self._btn_shuffle.setFixedSize(32, 32)
        self._btn_shuffle.setToolTip(T('shuffle'))
        self._btn_shuffle.setCheckable(True)
        btn_row.addWidget(self._btn_shuffle)

        self._btn_prev = QPushButton('⏮')
        self._btn_prev.setFixedSize(32, 32)
        self._btn_prev.setToolTip(T('previous'))
        btn_row.addWidget(self._btn_prev)

        self._btn_play = QPushButton('▶')
        self._btn_play.setFixedSize(40, 40)
        self._btn_play.setToolTip(T('play'))
        font = self._btn_play.font()
        font.setPointSize(14)
        self._btn_play.setFont(font)
        btn_row.addWidget(self._btn_play)

        self._btn_next = QPushButton('⏭')
        self._btn_next.setFixedSize(32, 32)
        self._btn_next.setToolTip(T('next'))
        btn_row.addWidget(self._btn_next)

        self._btn_repeat = QPushButton('🔁')
        self._btn_repeat.setFixedSize(32, 32)
        self._btn_repeat.setToolTip(T('repeat_off'))
        btn_row.addWidget(self._btn_repeat)

        btn_row.addStretch()
        ctrl_layout.addLayout(btn_row)

        # Seek bar row
        seek_row = QHBoxLayout()
        seek_row.setSpacing(4)
        self._position_label = QLabel('0:00')
        self._position_label.setStyleSheet("font-size: 10px; color: #888; min-width: 40px;")
        self._position_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        seek_row.addWidget(self._position_label)

        self._seek_slider = QSlider(Qt.Orientation.Horizontal)
        self._seek_slider.setRange(0, 0)
        self._seek_slider.setToolTip(T('seek_tip'))
        seek_row.addWidget(self._seek_slider)

        self._duration_label = QLabel('0:00')
        self._duration_label.setStyleSheet("font-size: 10px; color: #888; min-width: 40px;")
        seek_row.addWidget(self._duration_label)

        ctrl_layout.addLayout(seek_row)
        layout.addLayout(ctrl_layout, 1)

        layout.addStretch()

        # Volume
        vol_layout = QHBoxLayout()
        vol_layout.setSpacing(4)
        self._btn_mute = QPushButton('🔊')
        self._btn_mute.setFixedSize(28, 28)
        self._btn_mute.setToolTip(T('mute'))
        vol_layout.addWidget(self._btn_mute)

        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(80)
        self._volume_slider.setFixedWidth(100)
        self._volume_slider.setToolTip(T('volume'))
        vol_layout.addWidget(self._volume_slider)

        layout.addLayout(vol_layout)

        # Audio info section (right side)
        audio_info_layout = QVBoxLayout()
        audio_info_layout.setSpacing(1)
        audio_info_layout.setContentsMargins(4, 0, 0, 0)

        # Quality badge (Hi-Res / CD / Lossless / Lossy / LIVE)
        self._quality_label = QLabel('')
        self._quality_label.setStyleSheet(
            "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
            "background: #2a5a2a; color: #8f8;"
        )
        self._quality_label.hide()
        audio_info_layout.addWidget(self._quality_label)

        # Format info: "FLAC · 96kHz/24-bit"
        self._format_info_label = QLabel('')
        self._format_info_label.setStyleSheet(
            "font-size: 9px; color: #999; padding: 0 2px;"
        )
        self._format_info_label.setToolTip(T('audio_chain_info'))
        self._format_info_label.hide()
        audio_info_layout.addWidget(self._format_info_label)

        # Device indicator: "→ USB DAC Name"
        self._device_label = QLabel('')
        self._device_label.setStyleSheet(
            "font-size: 8px; color: #666; padding: 0 2px;"
        )
        self._device_label.setToolTip(T('audio_device_tip'))
        self._device_label.hide()
        audio_info_layout.addWidget(self._device_label)

        layout.addLayout(audio_info_layout)

        return bar

    def _setup_menus(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu(T('menu_file'))

        act_add = file_menu.addAction(T('add_folder'))
        act_add.setToolTip(T('add_folder_tip'))
        act_add.setShortcut(QKeySequence('Ctrl+O'))
        act_add.triggered.connect(self._on_add_folder)

        act_rescan = file_menu.addAction(T('rescan'))
        act_rescan.setToolTip(T('rescan_tip'))
        act_rescan.setShortcut(QKeySequence('F5'))
        act_rescan.triggered.connect(self._on_rescan)

        file_menu.addSeparator()

        act_itunes = file_menu.addAction(T('import_itunes'))
        act_itunes.setToolTip(T('import_itunes_tip'))
        act_itunes.triggered.connect(self._on_import_itunes)

        act_itunes_pod = file_menu.addAction(T('import_podcasts'))
        act_itunes_pod.setToolTip(T('import_podcasts_tip'))
        act_itunes_pod.triggered.connect(self._on_import_itunes_podcasts)

        file_menu.addSeparator()

        act_cd = file_menu.addAction(T('cd_rip'))
        act_cd.setToolTip(T('cd_rip_tip'))
        act_cd.triggered.connect(self._on_cd_rip)

        file_menu.addSeparator()

        act_settings = file_menu.addAction(T('settings'))
        act_settings.setToolTip(T('settings_tip'))
        act_settings.setShortcut(QKeySequence('Ctrl+,'))
        act_settings.triggered.connect(self._on_settings)

        file_menu.addSeparator()

        act_quit = file_menu.addAction(T('quit'))
        act_quit.setToolTip(T('quit_tip'))
        act_quit.setShortcut(QKeySequence('Ctrl+Q'))
        act_quit.triggered.connect(self.close)

        # Edit menu
        edit_menu = menubar.addMenu(T('menu_edit'))

        act_search = edit_menu.addAction(T('search'))
        act_search.setShortcut(QKeySequence('Ctrl+F'))
        act_search.triggered.connect(lambda: self._search_input.setFocus())

        # Playback menu
        play_menu = menubar.addMenu(T('menu_playback'))

        act_play_pause = play_menu.addAction(T('play') + '/' + T('pause'))
        act_play_pause.setShortcut(QKeySequence('Space'))
        act_play_pause.triggered.connect(self._player.play_pause)

        act_stop = play_menu.addAction(T('stop'))
        act_stop.setShortcut(QKeySequence('Ctrl+.'))
        act_stop.triggered.connect(self._player.stop)

        act_next = play_menu.addAction(T('next'))
        act_next.setShortcut(QKeySequence('Ctrl+Right'))
        act_next.triggered.connect(self._player.next)

        act_prev = play_menu.addAction(T('previous'))
        act_prev.setShortcut(QKeySequence('Ctrl+Left'))
        act_prev.triggered.connect(self._player.previous)

        play_menu.addSeparator()

        act_radio = play_menu.addAction(T('smart_radio'))
        act_radio.setToolTip(T('smart_radio_tip'))
        act_radio.setShortcut(QKeySequence('Ctrl+R'))
        act_radio.triggered.connect(self._on_smart_radio)

        play_menu.addSeparator()

        act_vol_up = play_menu.addAction(T('volume') + ' +')
        act_vol_up.setShortcut(QKeySequence('Ctrl+Up'))
        act_vol_up.triggered.connect(lambda: self._player.set_volume(self._player.volume + 5))

        act_vol_dn = play_menu.addAction(T('volume') + ' -')
        act_vol_dn.setShortcut(QKeySequence('Ctrl+Down'))
        act_vol_dn.triggered.connect(lambda: self._player.set_volume(self._player.volume - 5))

        # View menu
        view_menu = menubar.addMenu(T('menu_view'))

        act_meta = view_menu.addAction(T('fetch_metadata'))
        act_meta.setToolTip(T('fetch_metadata_tip'))
        act_meta.triggered.connect(self._on_fetch_metadata)

        view_menu.addSeparator()

        act_pod_sub = view_menu.addAction(T('podcast_subscribe'))
        act_pod_sub.setToolTip(T('podcast_subscribe_tip'))
        act_pod_sub.triggered.connect(self._on_podcast_subscribe)

        act_pod_search = view_menu.addAction(T('podcast_search'))
        act_pod_search.setToolTip(T('podcast_search_tip'))
        act_pod_search.triggered.connect(self._on_podcast_search)

        act_pod_refresh = view_menu.addAction(T('podcast_refresh'))
        act_pod_refresh.setToolTip(T('podcast_refresh_tip'))
        act_pod_refresh.triggered.connect(self._on_podcast_refresh)

        view_menu.addSeparator()

        act_visualizer = view_menu.addAction(T('visualizer'))
        act_visualizer.setToolTip(T('visualizer_tip'))
        act_visualizer.setShortcut(QKeySequence('Ctrl+V'))
        act_visualizer.triggered.connect(self._toggle_visualizer)

        # Tools menu
        tools_menu = menubar.addMenu(T('menu_tools'))

        act_harmonize = tools_menu.addAction(T('harmonize'))
        act_harmonize.setToolTip(T('harmonize_tip'))
        act_harmonize.triggered.connect(self._on_harmonize)

        tools_menu.addSeparator()

        act_backup = tools_menu.addAction(T('backup'))
        act_backup.setToolTip(T('backup_tip'))
        act_backup.triggered.connect(self._on_backup)

        act_restore = tools_menu.addAction(T('restore'))
        act_restore.setToolTip(T('restore_tip'))
        act_restore.triggered.connect(self._on_restore)

        tools_menu.addSeparator()

        act_relocate = tools_menu.addAction(T('relocate_paths'))
        act_relocate.setToolTip(T('relocate_paths_tip'))
        act_relocate.triggered.connect(self._on_relocate_paths)

        act_broken = tools_menu.addAction(T('broken_paths'))
        act_broken.setToolTip(T('broken_paths_tip'))
        act_broken.triggered.connect(self._on_check_broken)

        tools_menu.addSeparator()

        act_export = tools_menu.addAction(T('export_library'))
        act_export.setToolTip(T('export_library_tip'))
        act_export.triggered.connect(self._on_export_library)

        tools_menu.addSeparator()

        act_reset_counts = tools_menu.addAction(T('reset_play_counts'))
        act_reset_counts.setToolTip(T('reset_play_counts_tip'))
        act_reset_counts.triggered.connect(self._on_reset_play_counts)

        tools_menu.addSeparator()

        act_classify = tools_menu.addAction(T('classify_library'))
        act_classify.setToolTip(T('classify_library_tip'))
        act_classify.triggered.connect(self._on_classify_library)

        tools_menu.addSeparator()

        act_organize = tools_menu.addAction(T('organize_library'))
        act_organize.setToolTip(T('organize_library_tip'))
        act_organize.triggered.connect(self._on_organize_library)

        tools_menu.addSeparator()

        act_stats = tools_menu.addAction(T('stats_menu'))
        act_stats.setToolTip(T('stats_menu_tip'))
        act_stats.setShortcut(QKeySequence('Ctrl+I'))
        act_stats.triggered.connect(self._on_show_stats)

        # Help menu
        help_menu = menubar.addMenu(T('menu_help'))

        act_about = help_menu.addAction(T('about'))
        act_about.triggered.connect(self._on_about)

        act_help = help_menu.addAction(T('help_title'))
        act_help.setShortcut(QKeySequence('F1'))
        act_help.triggered.connect(self._on_help)

        help_menu.addSeparator()

        act_bug = help_menu.addAction(T('report_bug'))
        act_bug.triggered.connect(self._on_report_bug)

        act_updates = help_menu.addAction(T('check_updates'))
        act_updates.triggered.connect(self._on_check_updates)

    def _connect_signals(self):
        """Wire up all signals."""
        # Player signals
        self._player.state_changed.connect(self._on_player_state)
        self._player.position_changed.connect(self._on_position)
        self._player.duration_changed.connect(self._on_duration)
        self._player.track_changed.connect(self._on_track_changed)
        self._player.volume_changed.connect(self._on_volume_changed)
        self._player.repeat_changed.connect(self._on_repeat_changed)
        self._player.shuffle_changed.connect(self._on_shuffle_changed)
        self._player.radio_changed.connect(self._on_radio_changed)
        self._player.audio_info_changed.connect(self._on_audio_info)
        self._player.error_occurred.connect(
            lambda msg: self._status_bar.showMessage(f"Error: {msg}", 5000)
        )

        # UI controls
        self._btn_play.clicked.connect(self._player.play_pause)
        self._btn_next.clicked.connect(self._player.next)
        self._btn_prev.clicked.connect(self._player.previous)
        self._btn_shuffle.clicked.connect(self._player.toggle_shuffle)
        self._btn_repeat.clicked.connect(self._player.cycle_repeat)
        self._btn_mute.clicked.connect(self._player.toggle_mute)
        self._volume_slider.valueChanged.connect(self._player.set_volume)

        # Seek slider
        self._seek_slider.sliderMoved.connect(self._player.seek)

        # Table double-click and context menu
        self._track_table.doubleClicked.connect(self._on_track_double_click)
        self._track_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._track_table.customContextMenuRequested.connect(self._on_track_context_menu)

        # Sidebar
        self._sidebar.currentItemChanged.connect(self._on_sidebar_changed)

        # Search
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._on_search)
        self._search_input.textChanged.connect(
            lambda: self._search_timer.start(300)
        )

    # --- Data loading ---

    def _refresh_library(self):
        """Reload library data and update sidebar counts."""
        stats = db.get_library_stats()
        parts = [
            f"{stats['tracks']} {T('view_tracks').lower()}",
            f"{stats['albums']} {T('view_albums').lower()}",
            f"{stats['artists']} {T('view_artists').lower()}",
        ]
        if stats.get('podcasts', 0) > 0:
            parts.append(f"{stats['podcasts']} podcasts")
        self._stats_label.setText(' | '.join(parts))
        self._refresh_playlists_sidebar()
        self._refresh_podcasts_sidebar()
        self._load_view(self._current_view, self._current_filter)

    def _load_view(self, view, filter_value=None):
        """Load tracks for the current view."""
        self._current_view = view
        self._current_filter = filter_value

        if view == 'all_tracks':
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                ORDER BY a.name, al.year, t.disc_number, t.track_number
            """)
        elif view == 'artists':
            self._load_artists_view()
            return
        elif view == 'albums':
            self._load_albums_view()
            return
        elif view == 'genres':
            self._load_genres_view()
            return
        elif view == 'periods':
            self._load_periods_view()
            return
        elif view == 'artist' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.artist_id = ? OR t.album_artist_id = ?
                ORDER BY al.year, t.disc_number, t.track_number
            """, (filter_value, filter_value))
        elif view == 'album' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.album_id = ?
                ORDER BY t.disc_number, t.track_number
            """, (filter_value,))
        elif view == 'genre' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.genre = ?
                ORDER BY a.name, al.year, t.disc_number, t.track_number
            """, (filter_value,))
        elif view == 'period' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.period = ?
                ORDER BY t.composer, t.year, al.title, t.disc_number, t.track_number
            """, (filter_value,))
        elif view.startswith('playlist:'):
            try:
                pl_id = int(view.split(':')[1])
            except (IndexError, ValueError):
                tracks = []
                self._populate_table(tracks)
                return
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title
                FROM playlist_tracks pt
                JOIN tracks t ON pt.track_id = t.id
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE pt.playlist_id = ?
                ORDER BY pt.position
            """, (pl_id,))
        elif view == 'all_episodes':
            self._load_episodes_view()
            return
        elif view.startswith('podcast:'):
            try:
                pod_id = int(view.split(':')[1])
            except (IndexError, ValueError):
                return
            self._load_episodes_view(pod_id)
            return
        else:
            tracks = []

        self._content_mode = 'music'
        self._populate_table(tracks)

    def _load_artists_view(self):
        """Show artist list in sidebar children."""
        self._item_artists.takeChildren()
        artists = db.fetchall("""
            SELECT a.id, a.name, COUNT(t.id) as track_count
            FROM artists a
            JOIN tracks t ON (t.artist_id = a.id OR t.album_artist_id = a.id)
            GROUP BY a.id
            ORDER BY a.sort_name
        """)
        for art in artists:
            item = QTreeWidgetItem(self._item_artists,
                                   [f"{art['name']} ({art['track_count']})"])
            item.setData(0, Qt.ItemDataRole.UserRole, f"artist:{art['id']}")
        self._item_artists.setExpanded(True)
        self._populate_table([])

    def _load_albums_view(self):
        """Show album list in sidebar children."""
        self._item_albums.takeChildren()
        albums = db.fetchall("""
            SELECT al.id, al.title, a.name as artist_name, al.year,
                   COUNT(t.id) as track_count
            FROM albums al
            LEFT JOIN artists a ON al.artist_id = a.id
            LEFT JOIN tracks t ON t.album_id = al.id
            GROUP BY al.id
            ORDER BY a.sort_name, al.year
        """)
        for alb in albums:
            yr = f" ({alb['year']})" if alb['year'] else ''
            label = f"{alb['title']}{yr} - {alb['artist_name'] or '?'}"
            item = QTreeWidgetItem(self._item_albums, [label])
            item.setData(0, Qt.ItemDataRole.UserRole, f"album:{alb['id']}")
        self._item_albums.setExpanded(True)
        self._populate_table([])

    def _load_genres_view(self):
        """Show genre list."""
        self._item_genres.takeChildren()
        genres = db.fetchall("""
            SELECT genre, COUNT(*) as cnt FROM tracks
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre ORDER BY genre
        """)
        for g in genres:
            item = QTreeWidgetItem(self._item_genres,
                                   [f"{g['genre']} ({g['cnt']})"])
            item.setData(0, Qt.ItemDataRole.UserRole, f"genre:{g['genre']}")
        self._item_genres.setExpanded(True)
        self._populate_table([])

    def _load_periods_view(self):
        """Show musical period list (Baroque, Classical, Romantic, etc.)."""
        self._item_periods.takeChildren()
        periods = db.fetchall("""
            SELECT period, COUNT(*) as cnt FROM tracks
            WHERE period IS NOT NULL AND period != ''
            GROUP BY period ORDER BY
                CASE period
                    WHEN 'Medieval' THEN 1
                    WHEN 'Renaissance' THEN 2
                    WHEN 'Baroque' THEN 3
                    WHEN 'Classical' THEN 4
                    WHEN 'Romantic' THEN 5
                    WHEN 'Modern' THEN 6
                    WHEN 'Contemporary' THEN 7
                    WHEN 'Recent' THEN 8
                    ELSE 9
                END
        """)
        for p in periods:
            item = QTreeWidgetItem(self._item_periods,
                                   [f"{p['period']} ({p['cnt']})"])
            item.setData(0, Qt.ItemDataRole.UserRole, f"period:{p['period']}")
        self._item_periods.setExpanded(True)
        self._populate_table([])

    def _load_episodes_view(self, podcast_id=None):
        """Load podcast episodes into the table."""
        self._content_mode = 'podcasts'
        if podcast_id:
            episodes = db.fetchall("""
                SELECT e.*, p.title as podcast_title, p.image_data
                FROM podcast_episodes e
                LEFT JOIN podcasts p ON e.podcast_id = p.id
                WHERE e.podcast_id = ?
                ORDER BY e.published_at DESC
            """, (podcast_id,))
        else:
            episodes = db.fetchall("""
                SELECT e.*, p.title as podcast_title, p.image_data
                FROM podcast_episodes e
                LEFT JOIN podcasts p ON e.podcast_id = p.id
                ORDER BY e.published_at DESC
                LIMIT 500
            """)
        self._populate_episodes_table(episodes)

    def _populate_episodes_table(self, episodes):
        """Fill table with podcast episodes using episode model."""
        self._episode_mode = True
        ep_list = []
        for row_data in episodes:
            ep = dict(row_data)
            ep['_is_episode'] = True
            ep_list.append(ep)

        self._all_tracks_cache = ep_list

        # Switch to episode model
        if not hasattr(self, '_episode_model'):
            self._episode_model = EpisodeTableModel(self)
        self._episode_model.setEpisodes(ep_list)
        self._track_table.setModel(self._episode_model)

        # Set column widths
        for i, (_, _, w) in enumerate(EPISODE_COLUMNS):
            self._track_table.setColumnWidth(i, w)
        header = self._track_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # Show all episode columns
        for i in range(len(EPISODE_COLUMNS)):
            self._track_table.setColumnHidden(i, False)

        self._update_view_stats(ep_list)

    def _update_view_stats(self, items):
        """Update status bar with totals for current view."""
        total_duration = sum(t.get('duration_ms', 0) or 0 for t in items)
        total_size = sum(t.get('file_size', 0) or 0 for t in items)
        count = len(items)
        lang = get_lang()
        label = 'pistes' if lang == 'fr' else 'tracks'
        count_str = f"{count:,}".replace(',', ' ')
        parts = [f"{count_str} {label}"]
        if total_duration > 0:
            parts.append(format_duration_long(total_duration))
        if total_size > 0:
            parts.append(format_size(total_size))
        self._status_bar.showMessage(' | '.join(parts))

    def _populate_table(self, tracks):
        """Fill track table — instant via model (no widget items created)."""
        # Switch back from episode model if needed
        if self._episode_mode:
            self._episode_mode = False
            self._track_table.setModel(self._track_model)
            # Restore track column widths and visibility
            for i, (_, key, w, _) in enumerate(ALL_COLUMNS):
                self._track_table.setColumnWidth(i, w)
                self._track_table.setColumnHidden(i, key not in self._visible_columns)
            header = self._track_table.horizontalHeader()
            for i, (_, key, _, _) in enumerate(ALL_COLUMNS):
                if key == 'title':
                    header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
                    break

        self._all_tracks_cache = [dict(row_data) for row_data in tracks]
        self._track_model.setTracks(self._all_tracks_cache)
        self._update_view_stats(self._all_tracks_cache)

    # --- Event handlers ---

    def _on_sidebar_changed(self, current, previous):
        """Handle sidebar selection change."""
        if not current:
            return
        view_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not view_id:
            return

        # Web radio station
        if str(view_id).startswith('radio:'):
            stream_url = str(view_id)[6:]  # Remove 'radio:' prefix
            from web_radio import find_station_by_url
            station = find_station_by_url(stream_url)
            if station:
                self._player.play_stream(station)
            return

        if ':' in str(view_id) and not view_id.startswith('playlist:'):
            parts = view_id.split(':', 1)
            self._load_view(parts[0], parts[1] if len(parts) > 1 else None)
        elif view_id.startswith('playlist:'):
            self._load_view(view_id)
        else:
            self._load_view(view_id)

    def _get_visual_queue(self):
        """Build playback queue from current model order (cached)."""
        model = self._track_table.model()
        if not model:
            return []
        # Use the backing list directly instead of iterating model.data()
        if isinstance(model, TrackTableModel):
            return list(model.tracks())
        # Fallback for episode model
        return [model.data(model.index(r, 0), Qt.ItemDataRole.UserRole)
                for r in range(model.rowCount())]

    def _on_track_double_click(self, index):
        """Play track or episode on double-click."""
        if not index.isValid():
            return
        model = self._track_table.model()
        track = model.data(index, Qt.ItemDataRole.UserRole)
        if not track:
            return

        # For podcast episodes, use file_path if downloaded
        if track.get('_is_episode'):
            fp = track.get('file_path')
            if not fp:
                self._status_bar.showMessage(T('podcast_download') + '...', 3000)
                return
            ep_track = {
                'file_path': fp,
                'title': track.get('title', ''),
                'artist_name': track.get('podcast_title', ''),
                'album_title': 'Podcast',
                'duration_ms': track.get('duration_ms', 0),
            }
            self._player.play_track(ep_track)
            if track.get('id'):
                db.execute(
                    "UPDATE podcast_episodes SET listened = 1, listened_at = datetime('now') WHERE id = ?",
                    (track['id'],), commit=True
                )
            return

        # Build queue from current model (sorted) order
        visual_queue = self._get_visual_queue()
        self._player.play_track(track, queue=visual_queue, index=index.row())

    def _on_search(self):
        """Handle search input."""
        query = self._search_input.text().strip()
        if len(query) < 2:
            self._load_view(self._current_view, self._current_filter)
            return

        results = db.search_tracks(query)
        self._populate_table(results)

    def _on_player_state(self, state):
        """Update play button icon."""
        if state == PlayerState.PLAYING:
            self._btn_play.setText('⏸')
            self._btn_play.setToolTip(T('pause'))
        else:
            self._btn_play.setText('▶')
            self._btn_play.setToolTip(T('play'))

    def _on_position(self, pos):
        """Update seek slider and time label."""
        if self._player.is_streaming:
            return  # No seek on live streams
        if not self._seek_slider.isSliderDown():
            self._seek_slider.setValue(pos)
        self._position_label.setText(format_duration(pos))

    def _on_duration(self, dur):
        """Update duration display."""
        if self._player.is_streaming:
            return  # No duration on live streams
        self._seek_slider.setRange(0, dur)
        self._duration_label.setText(format_duration(dur))

    def _on_track_changed(self, track):
        """Update UI for new track."""
        self._track_title_label.setText(track.get('title', ''))
        self._track_artist_label.setText(track.get('artist_name', track.get('artist', '')))

        # Cover art (load on demand, not in listing queries)
        album_id = track.get('album_id')
        cover = None
        if album_id:
            row = db.fetchone("SELECT cover_data FROM albums WHERE id = ?", (album_id,))
            cover = row['cover_data'] if row else None
        pm = cover_to_pixmap(cover, 64) if cover else None
        if pm:
            self._cover_label.setPixmap(pm)
        else:
            self._cover_label.clear()
            self._cover_label.setText('♫')
            self._cover_label.setStyleSheet(
                "background: #222; border-radius: 4px; color: #666; font-size: 24px;"
            )

        # Quality badge
        fmt = track.get('file_format', '')
        sr = track.get('sample_rate', 0) or 0
        bd = track.get('bit_depth', 0) or 0

        if fmt in ('FLAC', 'ALAC', 'WAV', 'AIFF', 'APE', 'WV', 'DSD', 'DSF', 'DFF'):
            if sr > 48000 or bd > 16:
                self._quality_label.setText(T('quality_hires'))
                self._quality_label.setStyleSheet(
                    "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
                    "background: #5a2a5a; color: #f8f;"
                )
            elif sr == 44100 and bd == 16:
                self._quality_label.setText(T('quality_cd'))
                self._quality_label.setStyleSheet(
                    "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
                    "background: #2a5a2a; color: #8f8;"
                )
            else:
                self._quality_label.setText(T('quality_lossless'))
                self._quality_label.setStyleSheet(
                    "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
                    "background: #2a5a2a; color: #8f8;"
                )
            self._quality_label.show()
        elif fmt in ('MP3', 'AAC', 'OGG', 'OPUS', 'WMA', 'M4A'):
            self._quality_label.setText(T('quality_lossy'))
            self._quality_label.setStyleSheet(
                "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
                "background: #5a5a2a; color: #ff8;"
            )
            self._quality_label.show()
        else:
            self._quality_label.hide()

        # Record play count for previous track if listened long enough
        import time as _time
        prev_path = getattr(self, '_playing_track_path', None)
        prev_start = getattr(self, '_playing_track_start', 0)
        if prev_path and (_time.time() - prev_start) >= PLAY_COUNT_THRESHOLD_S:
            db.execute(
                "UPDATE tracks SET play_count = play_count + 1, last_played = datetime('now') WHERE file_path = ?",
                (prev_path,), commit=True
            )

        # Track start time for play count threshold
        self._playing_track_path = track.get('file_path', '')
        self._playing_track_start = _time.time()

    def _on_radio_changed(self, station):
        """Update UI when web radio starts/stops."""
        if station:
            from web_radio import station_display_name, COUNTRY_FLAGS
            self._track_title_label.setText(station.get('name', ''))
            country = station.get('country', '')
            flag = COUNTRY_FLAGS.get(country, '')
            self._track_artist_label.setText(f"{flag} {T('radio_live')}")

            # Show LIVE badge instead of quality
            self._quality_label.setText(T('radio_live'))
            self._quality_label.setStyleSheet(
                "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
                "background: #aa2222; color: #fff; font-weight: bold;"
            )
            self._quality_label.show()

            # Cover: radio icon
            self._cover_label.clear()
            self._cover_label.setText('📻')
            self._cover_label.setStyleSheet(
                "background: #222; border-radius: 4px; color: #5577aa; font-size: 28px;"
            )

            # Hide seek bar and format info (live stream)
            self._seek_slider.setEnabled(False)
            self._seek_slider.setValue(0)
            self._position_label.setText(T('radio_live'))
            self._duration_label.setText('')
            self._format_info_label.hide()
        else:
            # Returning from radio to normal mode
            self._seek_slider.setEnabled(True)
            self._quality_label.hide()
            self._format_info_label.hide()
            self._position_label.setText('0:00')
            self._duration_label.setText('0:00')

    def _on_audio_info(self, info):
        """Update audio chain display in player bar."""
        fmt = info.get('format', '')
        sr = info.get('sample_rate', 0)
        bd = info.get('bit_depth', 0)
        br = info.get('bitrate', 0)
        dev_name = info.get('device_name', '')

        # Build format string: "FLAC · 96kHz/24-bit" or "MP3 · 320kbps"
        parts = []
        if fmt:
            parts.append(fmt)
        if sr:
            rate_str = f"{sr / 1000:.1f}kHz" if sr >= 1000 else f"{sr}Hz"
            # Clean up "44.1kHz" not "44.1kHz"
            rate_str = rate_str.replace('.0kHz', 'kHz')
            if bd:
                parts.append(f"{rate_str}/{bd}-bit")
            else:
                parts.append(rate_str)
        elif bd:
            parts.append(f"{bd}-bit")
        if br and fmt in ('MP3', 'AAC', 'OGG', 'OPUS', 'WMA', 'M4A'):
            parts.append(f"{br}kbps")

        channels = info.get('channels', 2)
        if channels and channels != 2:
            ch_map = {1: 'Mono', 6: '5.1', 8: '7.1'}
            ch_str = ch_map.get(channels, f"{channels}ch")
            parts.append(ch_str)

        if parts:
            self._format_info_label.setText(' · '.join(parts))
            self._format_info_label.show()
        else:
            self._format_info_label.hide()

        # Device indicator
        if dev_name:
            prefix = '→ '
            # Truncate long device names
            display_name = dev_name if len(dev_name) <= 30 else dev_name[:27] + '...'
            self._device_label.setText(f"{prefix}{display_name}")
            self._device_label.setToolTip(
                T('audio_device_tip') + f"\n{dev_name}"
            )
            self._device_label.show()
        else:
            self._device_label.hide()

    def _on_volume_changed(self, vol):
        """Update volume slider and mute button."""
        if not self._volume_slider.isSliderDown():
            self._volume_slider.setValue(vol)
        self._btn_mute.setText('🔇' if vol == 0 else '🔊')

    def _on_repeat_changed(self, mode):
        """Update repeat button."""
        if mode == RepeatMode.OFF:
            self._btn_repeat.setText('🔁')
            self._btn_repeat.setToolTip(T('repeat_off'))
            self._btn_repeat.setStyleSheet('')
        elif mode == RepeatMode.ALL:
            self._btn_repeat.setText('🔁')
            self._btn_repeat.setToolTip(T('repeat_all'))
            self._btn_repeat.setStyleSheet('background: #335;')
        elif mode == RepeatMode.ONE:
            self._btn_repeat.setText('🔂')
            self._btn_repeat.setToolTip(T('repeat_one'))
            self._btn_repeat.setStyleSheet('background: #335;')

    def _on_shuffle_changed(self, mode):
        """Update shuffle button."""
        self._btn_shuffle.setChecked(mode == ShuffleMode.ON)

    # --- Actions ---

    def _on_add_folder(self):
        """Add a music folder to scan."""
        folder = QFileDialog.getExistingDirectory(
            self, T('add_folder'), '',
            QFileDialog.Option.ShowDirsOnly
        )
        if not folder:
            return

        # Save to DB
        db.execute(
            "INSERT OR IGNORE INTO scan_folders(path) VALUES(?)",
            (folder,), commit=True
        )

        # Start scan
        self._start_scan([folder])

    def _on_rescan(self):
        """Rescan all folders."""
        folders = [
            row['path'] for row in
            db.fetchall("SELECT path FROM scan_folders")
        ]
        if not folders:
            self._status_bar.showMessage(T('add_folder'), 3000)
            return
        self._start_scan(folders, full_rescan=True)

    def _cleanup_thread(self, attr_thread, attr_worker=None):
        """Safely clean up a previous QThread and its worker."""
        thread = getattr(self, attr_thread, None)
        if thread:
            if thread.isRunning():
                thread.quit()
                if not thread.wait(5000):
                    log.warning("Thread %s did not stop in 5s, terminating", attr_thread)
                    thread.terminate()
                    thread.wait(1000)
            thread.deleteLater()
            setattr(self, attr_thread, None)
        if attr_worker:
            worker = getattr(self, attr_worker, None)
            if worker:
                worker.deleteLater()
                setattr(self, attr_worker, None)

    def _start_scan(self, folders, full_rescan=False):
        """Launch scan worker in thread."""
        if self._scan_thread and self._scan_thread.isRunning():
            self._status_bar.showMessage(T('scanning'), 2000)
            return

        self._cleanup_thread('_scan_thread', '_scan_worker')
        self._scan_worker = ScanWorker(folders, full_rescan)
        self._scan_thread = QThread()
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.error.connect(self._scan_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(T('scanning'))
        self._scan_thread.start()

    def _on_scan_progress(self, current, total, filename):
        """Update scan progress."""
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._status_bar.showMessage(T('scan_progress', current=current, total=total))

    def _on_scan_finished(self, added, updated, removed):
        """Handle scan completion."""
        self._progress_bar.hide()
        self._status_bar.showMessage(
            T('scan_complete', added=added, updated=updated, removed=removed), 10000
        )
        self._refresh_library()

    def _on_scan_error(self, msg):
        """Handle scan error."""
        self._progress_bar.hide()
        self._status_bar.showMessage(f"Scan error: {msg}", 5000)
        log.error("Scan error: %s", msg)

    def _on_import_itunes(self):
        """Import iTunes library XML."""
        xml_path, _ = QFileDialog.getOpenFileName(
            self, T('itunes_select_xml'), '',
            'iTunes XML (*.xml);;All Files (*.*)'
        )
        if not xml_path:
            return

        self._cleanup_thread('_import_thread', '_import_worker')
        worker = ITunesImportWorker(xml_path)
        self._import_thread = QThread()
        worker.moveToThread(self._import_thread)

        self._import_thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(lambda t, p: self._on_itunes_done(t, p))
        worker.error.connect(lambda msg: self._on_scan_error(msg))
        worker.finished.connect(self._import_thread.quit)
        worker.error.connect(self._import_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(T('itunes_importing'))
        self._import_thread.start()
        self._import_worker = worker

    def _on_itunes_done(self, tracks, playlists):
        """Handle iTunes import completion."""
        self._progress_bar.hide()
        self._status_bar.showMessage(
            T('itunes_complete', tracks=tracks, playlists=playlists), 10000
        )
        self._refresh_library()

    def _on_fetch_metadata(self):
        """Fetch metadata from MusicBrainz."""
        model = self._track_table.model()
        track_ids = set()
        for index in self._track_table.selectionModel().selectedRows():
            track = model.data(index, Qt.ItemDataRole.UserRole)
            if track and isinstance(track, dict) and 'id' in track:
                track_ids.add(track['id'])

        self._cleanup_thread('_fetch_thread', '_fetch_worker')
        worker = MetadataFetchWorker(
            list(track_ids) if track_ids else None
        )
        self._fetch_thread = QThread()
        worker.moveToThread(self._fetch_thread)

        self._fetch_thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(lambda n: self._on_fetch_done(n))
        worker.error.connect(lambda msg: self._on_scan_error(msg))
        worker.finished.connect(self._fetch_thread.quit)
        worker.error.connect(self._fetch_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(T('fetching_metadata'))
        self._fetch_thread.start()
        self._fetch_worker = worker

    def _on_fetch_done(self, count):
        """Handle metadata fetch completion."""
        self._progress_bar.hide()
        self._status_bar.showMessage(
            f"Metadata updated: {count} tracks", 10000
        )
        self._refresh_library()

    def _on_settings(self):
        """Open settings dialog."""
        dlg = SettingsDialog(player=self._player, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_library()

    def _on_about(self):
        """Show about dialog."""
        from musicotheque import VERSION
        version = VERSION

        QMessageBox.about(
            self,
            T('about'),
            f"<h2>{T('app_name')}</h2>"
            f"<p>{T('app_subtitle')}</p>"
            f"<p>Version {version}</p>"
            f"<p>Python / PyQt6 / mutagen / QMediaPlayer</p>"
            f"<p>© 2026 Kevin</p>"
        )

    def _on_help(self):
        """Show help dialog."""
        dlg = HelpDialog(self)
        dlg.exec()

    # --- Context menu ---

    def _on_track_context_menu(self, pos):
        """Show context menu for track table — supports multi-selection."""
        index = self._track_table.indexAt(pos)
        if not index.isValid():
            return
        model = self._track_table.model()

        # Gather all selected tracks
        selected_indexes = self._track_table.selectionModel().selectedRows()
        selected_tracks = []
        for idx in selected_indexes:
            t = model.data(idx, Qt.ItemDataRole.UserRole)
            if t and isinstance(t, dict):
                selected_tracks.append(t)
        if not selected_tracks:
            return

        track = selected_tracks[0]
        row = index.row()
        multi = len(selected_tracks) > 1

        menu = QMenu(self)
        visual_queue = self._get_visual_queue()

        # Play actions (always use clicked track, not selection)
        act_play = menu.addAction(T('play_now'))
        act_play.triggered.connect(
            lambda: self._player.play_track(track, queue=visual_queue, index=row)
        )

        act_next = menu.addAction(T('play_next'))
        act_next.triggered.connect(lambda: self._player.add_to_queue(track))

        act_queue = menu.addAction(T('add_to_queue'))
        if multi:
            act_queue.triggered.connect(
                lambda: [self._player.add_to_queue(t) for t in selected_tracks]
            )
        else:
            act_queue.triggered.connect(lambda: self._player.add_to_queue(track))

        menu.addSeparator()

        # Add to playlist submenu (adds all selected tracks)
        pl_menu = menu.addMenu(T('add_to_playlist'))
        playlists = db.fetchall("SELECT id, name FROM playlists ORDER BY name")
        for pl in playlists:
            act = pl_menu.addAction(pl['name'])
            pl_id = pl['id']
            track_ids = [t.get('id') for t in selected_tracks if t.get('id')]
            act.triggered.connect(
                lambda checked, pid=pl_id, tids=track_ids: [
                    self._add_track_to_playlist(pid, tid) for tid in tids
                ]
            )
        if playlists:
            pl_menu.addSeparator()
        act_new_pl = pl_menu.addAction(T('new_playlist'))
        act_new_pl.triggered.connect(lambda: self._create_playlist_with_track(track))

        menu.addSeparator()

        # Edit metadata (adapts to single/multi)
        act_edit = menu.addAction(T('edit_metadata'))
        act_edit.setToolTip(T('edit_metadata_tip'))
        tracks_copy = list(selected_tracks)
        act_edit.triggered.connect(lambda: self._edit_track_metadata(tracks_copy))

        # Fetch metadata online
        act_fetch = menu.addAction(T('fetch_metadata'))
        act_fetch.triggered.connect(self._on_fetch_metadata)

        menu.addSeparator()

        # Track info (single only)
        if not multi:
            act_info = menu.addAction(T('track_info'))
            act_info.triggered.connect(lambda: self._show_track_info(track))

        act_explorer = menu.addAction(T('show_in_explorer'))
        act_explorer.triggered.connect(lambda: self._show_in_explorer(track))

        # Reset play count
        has_plays = any(t.get('play_count', 0) > 0 for t in selected_tracks)
        if has_plays:
            menu.addSeparator()
            act_reset = menu.addAction(T('reset_play_count'))
            if multi:
                act_reset.triggered.connect(
                    lambda: [self._reset_track_play_count(t) for t in selected_tracks]
                )
            else:
                act_reset.triggered.connect(lambda: self._reset_track_play_count(track))

        menu.exec(self._track_table.viewport().mapToGlobal(pos))

    def _on_header_context_menu(self, pos):
        """Show column visibility chooser on header right-click."""
        menu = QMenu(self)

        # Add checkbox action for each column
        for i, (i18n_key, db_key, _, _) in enumerate(ALL_COLUMNS):
            # Title column cannot be hidden
            if db_key == 'title':
                continue
            act = menu.addAction(T(i18n_key))
            act.setCheckable(True)
            act.setChecked(db_key in self._visible_columns)
            act.triggered.connect(lambda checked, idx=i, key=db_key: self._toggle_column(idx, key, checked))

        menu.addSeparator()

        # Show all columns
        act_all = menu.addAction(T('show_all_columns'))
        act_all.triggered.connect(self._show_all_columns)

        # Reset to default
        act_reset = menu.addAction(T('reset_columns'))
        act_reset.triggered.connect(self._reset_columns)

        menu.exec(self._track_table.horizontalHeader().mapToGlobal(pos))

    def _toggle_column(self, col_idx, db_key, visible):
        """Toggle a column's visibility."""
        if visible:
            self._visible_columns.add(db_key)
        else:
            self._visible_columns.discard(db_key)
        self._track_table.setColumnHidden(col_idx, not visible)
        self._save_column_visibility()

    def _show_all_columns(self):
        """Show all available columns."""
        for i, (_, db_key, _, _) in enumerate(ALL_COLUMNS):
            self._visible_columns.add(db_key)
            self._track_table.setColumnHidden(i, False)
        self._save_column_visibility()

    def _reset_columns(self):
        """Reset columns to defaults."""
        self._visible_columns = set(DEFAULT_VISIBLE)
        for i, (_, db_key, _, _) in enumerate(ALL_COLUMNS):
            self._track_table.setColumnHidden(i, db_key not in self._visible_columns)
        self._save_column_visibility()

    def _save_column_visibility(self):
        """Persist column visibility to QSettings."""
        settings = QSettings('MusicOtheque', 'MusicOtheque')
        settings.setValue('visible_columns', list(self._visible_columns))

    def _add_track_to_playlist(self, playlist_id, track_id):
        """Add a track to a playlist."""
        if not track_id:
            return
        pos = db.fetchone(
            "SELECT MAX(position) as p FROM playlist_tracks WHERE playlist_id = ?",
            (playlist_id,)
        )
        next_pos = (pos['p'] or 0) + 1 if pos else 0
        db.execute(
            "INSERT OR IGNORE INTO playlist_tracks(playlist_id, track_id, position) VALUES(?,?,?)",
            (playlist_id, track_id, next_pos), commit=True
        )
        self._status_bar.showMessage(T('add_to_playlist'), 2000)

    def _create_playlist_with_track(self, track):
        """Create a new playlist and add track to it."""
        name, ok = QInputDialog.getText(self, T('new_playlist'), T('new_playlist'))
        if ok and name:
            db.execute("INSERT INTO playlists(name) VALUES(?)", (name,), commit=True)
            pl_id = db.fetchone("SELECT last_insert_rowid() as id")['id']
            if track.get('id'):
                db.execute(
                    "INSERT INTO playlist_tracks(playlist_id, track_id, position) VALUES(?,?,0)",
                    (pl_id, track['id']), commit=True
                )
            self._refresh_playlists_sidebar()

    def _show_track_info(self, track):
        """Show track information dialog with classification."""
        import html as html_mod
        from music_classifier import classify_track as _classify
        esc = html_mod.escape
        info_parts = [
            f"<b>{T('col_title')}:</b> {esc(str(track.get('title', '')))}",
            f"<b>{T('col_artist')}:</b> {esc(str(track.get('artist_name', '')))}",
            f"<b>{T('col_album')}:</b> {esc(str(track.get('album_title', '')))}",
            f"<b>{T('col_duration')}:</b> {format_duration(track.get('duration_ms', 0))}",
            f"<b>{T('col_format')}:</b> {esc(str(track.get('file_format', '')))}",
            f"<b>{T('col_sample_rate')}:</b> {format_sample_rate(track.get('sample_rate', 0))}",
            f"<b>{T('col_bit_depth')}:</b> {track.get('bit_depth', 0)}-bit",
            f"<b>{T('col_bitrate')}:</b> {format_bitrate(track.get('bitrate', 0))}",
            f"<b>{T('col_year')}:</b> {esc(str(track.get('year', '')))}",
            f"<b>{T('col_genre')}:</b> {esc(str(track.get('genre', '')))}",
        ]

        # Classification
        cl = _classify(
            title=str(track.get('title', '')),
            composer=str(track.get('composer', '')),
            genre=str(track.get('genre', '')),
            album=str(track.get('album_title', '')),
            year=track.get('year'),
        )
        info_parts.append('<br><b>--- ' + T('classification') + ' ---</b>')
        if cl['period']:
            info_parts.append(f"<b>{T('period')}:</b> {esc(cl['period'])}")
        if cl['form']:
            info_parts.append(f"<b>{T('form')}:</b> {esc(cl['form'])}")
        if cl['catalogue']:
            info_parts.append(f"<b>{T('catalogue_num')}:</b> {esc(cl['catalogue'])}")
        if cl['key']:
            info_parts.append(f"<b>{T('musical_key')}:</b> {esc(cl['key'])}")
        if cl['instruments']:
            info_parts.append(f"<b>{T('instruments')}:</b> {esc(', '.join(cl['instruments']))}")

        info_parts.append(f"<br><b>Path:</b> {esc(str(track.get('file_path', '')))}")
        QMessageBox.information(self, T('track_info'), '<br>'.join(info_parts))

    def _show_in_explorer(self, track):
        """Open file explorer at the track's location."""
        fp = track.get('file_path', '')
        if not fp or '\x00' in fp:
            return
        if not os.path.exists(fp):
            self._status_bar.showMessage(T('file_not_found'), 3000)
            return
        folder = os.path.dirname(fp)
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', '/select,', os.path.normpath(fp)])
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', '-R', fp])
        else:
            subprocess.Popen(['xdg-open', folder])

    def _edit_track_metadata(self, tracks):
        """Open iTunes-style metadata editor for single or multiple tracks."""
        dlg = MetadataEditDialog(tracks, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        changes = dlg.get_changes()
        if not changes:
            return

        # Whitelist valid DB columns to prevent SQL injection via key names
        _VALID_DB_KEYS = {f[1] for f in _SINGLE_FIELDS}
        safe_changes = {k: v for k, v in changes.items() if k in _VALID_DB_KEYS}
        if not safe_changes:
            return

        # Pre-build scanner updates once (same for all tracks)
        scanner_updates = {}
        for db_key, val in safe_changes.items():
            scanner_key = _DB_TO_SCANNER.get(db_key)
            if scanner_key:
                scanner_updates[scanner_key] = str(val) if val else ''

        # Pre-build SQL once (same columns for all tracks)
        set_clause = ', '.join(f"{k} = ?" for k in safe_changes)
        base_values = list(safe_changes.values())

        self._status_bar.showMessage(T('meta_writing_files'))

        errors = 0
        updated_count = 0
        total = len(tracks)

        for i, track in enumerate(tracks):
            track_id = track.get('id')
            fp = track.get('file_path', '')

            # Update database (batch commit every 50)
            if track_id:
                values = base_values + [track_id]
                try:
                    db.execute(
                        f"UPDATE tracks SET {set_clause} WHERE id = ?",
                        values, commit=False
                    )
                except Exception as e:
                    log.warning("DB update failed for track %s: %s", track_id, e)

            # Write to file via mutagen
            if fp and scanner_updates and os.path.exists(fp):
                try:
                    write_metadata(fp, scanner_updates)
                except Exception as e:
                    log.warning("Failed to write metadata to %s: %s", fp, e)
                    errors += 1

            # Update in-memory cache
            for db_key, val in safe_changes.items():
                track[db_key] = val

            updated_count += 1

            # Batch commit + keep UI responsive every 50 tracks
            if (i + 1) % 50 == 0:
                db.commit()
                self._status_bar.showMessage(
                    f"{T('meta_writing_files')} {i + 1}/{total}")
                QApplication.processEvents()

        # Final commit
        db.commit()

        # Refresh display
        self._track_model.layoutChanged.emit()

        if errors:
            self._status_bar.showMessage(
                T('meta_save_success', count=updated_count) + ' | ' +
                T('meta_save_error', count=errors), 8000
            )
        else:
            self._status_bar.showMessage(
                T('meta_save_success', count=updated_count), 5000
            )

    # --- Watcher handlers ---

    def _on_watcher_changes(self, added, modified, removed):
        """Handle library changes detected by file watcher."""
        msg = T('watcher_changes', added=added, modified=modified, removed=removed)
        self._status_bar.showMessage(msg, 8000)
        log.info("Watcher: +%d ~%d -%d", added, modified, removed)

    def _on_watcher_relocated(self, old_prefix, new_prefix, count):
        """Handle automatic path relocation."""
        msg = T('watcher_relocated', count=count, old=old_prefix, new=new_prefix)
        self._status_bar.showMessage(msg, 10000)
        self._refresh_library()

    def _on_watcher_scan(self, folders):
        """Handle scan request from watcher."""
        self._start_scan(folders)

    # --- Tools actions ---

    def _auto_backup(self):
        """Periodic auto-backup (transparent, every 5 min)."""
        import threading
        def _bg_backup():
            try:
                from musicotheque import DB_PATH, BACKUP_DIR
                backup_database(str(DB_PATH), str(BACKUP_DIR), label='auto')
                log.debug("Auto-backup completed")
            except Exception as e:
                log.warning("Auto-backup failed: %s", e)
        threading.Thread(target=_bg_backup, daemon=True).start()

    def _on_backup(self):
        """Manual backup."""
        from musicotheque import DB_PATH, BACKUP_DIR
        result = backup_database(str(DB_PATH), str(BACKUP_DIR), label='manual')
        if result:
            self._status_bar.showMessage(T('backup_done'), 5000)
        else:
            self._status_bar.showMessage(T('error'), 5000)

    def _on_restore(self):
        """Restore database from backup."""
        from musicotheque import DB_PATH, BACKUP_DIR
        backups = list_backups(str(BACKUP_DIR))
        if not backups:
            self._status_bar.showMessage(T('no_backups_found'), 3000)
            return

        items = [f"{b['name']} ({b['date']}, {b['size']//1024} KB)" for b in backups]
        item, ok = QInputDialog.getItem(
            self, T('restore'), T('restore_confirm'), items, 0, False
        )
        if not ok:
            return

        idx = items.index(item)
        confirm = QMessageBox.question(
            self, T('restore'), T('restore_confirm'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        db.close_connection()
        if restore_database(backups[idx]['path'], str(DB_PATH)):
            QMessageBox.information(self, T('info'), T('restore_done'))
            # Re-init DB connection
            db.init(str(DB_PATH))
            self._refresh_library()

    def _on_relocate_paths(self):
        """Relocate music paths dialog."""
        old_prefix, ok1 = QInputDialog.getText(
            self, T('relocate_paths'), T('relocate_old')
        )
        if not ok1 or not old_prefix:
            return
        new_prefix, ok2 = QInputDialog.getText(
            self, T('relocate_paths'), T('relocate_new')
        )
        if not ok2 or not new_prefix:
            return

        count = db.relocate_paths(old_prefix, new_prefix)
        self._status_bar.showMessage(T('relocate_done', count=count), 5000)
        self._refresh_library()

    def _on_check_broken(self):
        """Check for broken file paths (in background thread)."""
        import threading

        self._status_bar.showMessage(T('broken_paths') + '...')

        def _check():
            try:
                broken = db.find_broken_paths()
            except Exception as e:
                log.warning("Broken paths check failed: %s", e)
                broken = []
            finally:
                db.close_connection()
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._show_broken_results(broken))

        threading.Thread(target=_check, daemon=True).start()

    def _show_broken_results(self, broken):
        """Display broken paths results on main thread."""
        if not broken:
            self._status_bar.showMessage(T('no_broken_paths'), 5000)
            return

        msg = T('broken_paths_result', count=len(broken))
        details = '\n'.join(f"- {b['title']}: {b['file_path']}" for b in broken[:50])
        box = QMessageBox(self)
        box.setWindowTitle(T('broken_paths'))
        box.setText(msg)
        box.setDetailedText(details)
        box.exec()

    def _on_export_library(self):
        """Export library to JSON."""
        path, _ = QFileDialog.getSaveFileName(
            self, T('export_library'), 'musicotheque_export.json',
            'JSON (*.json);;All Files (*.*)'
        )
        if path:
            count = db.export_library(path)
            self._status_bar.showMessage(T('export_done', count=count), 5000)

    def _on_reset_play_counts(self):
        """Reset all play counts (anonymity/privacy)."""
        stats = db.get_library_stats()
        count = stats.get('tracks', 0)
        if count == 0:
            return

        reply = QMessageBox.warning(
            self, T('reset_play_counts'),
            T('reset_play_counts_confirm', count=count),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        db.execute("UPDATE tracks SET play_count = 0, last_played = NULL", commit=True)
        self._status_bar.showMessage(T('reset_play_counts_done', count=count), 5000)
        self._refresh_library()

    def _reset_track_play_count(self, track):
        """Reset play count for a single track."""
        track_id = track.get('id')
        if track_id:
            db.execute(
                "UPDATE tracks SET play_count = 0, last_played = NULL WHERE id = ?",
                (track_id,), commit=True
            )
            self._status_bar.showMessage(T('reset_play_count_done'), 3000)
            self._refresh_library()

    def _on_smart_radio(self):
        """Open Smart Radio dialog."""
        dlg = SmartRadioDialog(self._player, self)
        dlg.exec()

    def _on_report_bug(self):
        """Open GitHub issues page."""
        import webbrowser
        webbrowser.open('https://github.com/ARP273-ROSE/musicotheque/issues/new')

    def _on_check_updates(self):
        """Manual update check (non-blocking)."""
        import threading

        self._status_bar.showMessage(T('check_updates') + '...')

        def _check():
            try:
                import requests
                from musicotheque import VERSION as _ver
                resp = requests.get(
                    'https://api.github.com/repos/ARP273-ROSE/musicotheque/releases/latest',
                    timeout=5, headers={'User-Agent': f'MusicOtheque/{_ver}'}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    remote = data.get('tag_name', '').lstrip('v')
                    current = _ver
                    if remote and remote != current:
                        # Use QTimer to show dialog on main thread
                        QTimer.singleShot(0, lambda: QMessageBox.information(
                            self, T('check_updates'),
                            T('update_available', current=current, remote=remote)
                        ))
                    else:
                        QTimer.singleShot(0, lambda: self._status_bar.showMessage(T('up_to_date'), 3000))
                else:
                    QTimer.singleShot(0, lambda: self._status_bar.showMessage(T('no_releases_found'), 3000))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._status_bar.showMessage(f"{T('update_check_failed')}: {e}", 3000))

        threading.Thread(target=_check, daemon=True).start()

    # --- Podcast actions ---

    def _on_import_itunes_podcasts(self):
        """Import podcasts from iTunes XML."""
        xml_path, _ = QFileDialog.getOpenFileName(
            self, T('itunes_select_xml'), '',
            'iTunes XML (*.xml);;All Files (*.*)'
        )
        if not xml_path:
            return

        # Ask for path remapping
        remap = {}
        old_prefix, ok = QInputDialog.getText(
            self, T('import_podcasts'),
            T('relocate_old') + '\n(Leave empty to skip remapping)',
        )
        if ok and old_prefix:
            new_prefix, ok2 = QInputDialog.getText(
                self, T('import_podcasts'), T('relocate_new')
            )
            if ok2 and new_prefix:
                remap[old_prefix] = new_prefix

        worker = ITunesPodcastImportWorker(xml_path, remap_paths=remap)
        self._podcast_import_thread = QThread()
        worker.moveToThread(self._podcast_import_thread)

        self._podcast_import_thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(lambda s, e: self._on_podcast_import_done(s, e))
        worker.error.connect(lambda msg: self._on_scan_error(msg))
        worker.finished.connect(self._podcast_import_thread.quit)
        worker.error.connect(self._podcast_import_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(T('podcast_importing'))
        self._podcast_import_thread.start()
        self._podcast_import_worker = worker

    def _on_podcast_import_done(self, shows, episodes):
        """Handle podcast import completion."""
        self._progress_bar.hide()
        self._status_bar.showMessage(
            T('podcast_import_done', shows=shows, episodes=episodes), 10000
        )
        self._refresh_library()

    def _on_podcast_subscribe(self):
        """Subscribe to a new podcast by RSS URL."""
        url, ok = QInputDialog.getText(
            self, T('podcast_subscribe'), T('podcast_feed_url')
        )
        if not ok or not url:
            return
        self._run_podcast_subscribe(url)

    def _run_podcast_subscribe(self, url):
        """Run podcast subscription in a worker thread."""
        worker = PodcastSubscribeWorker(url)
        thread = QThread()
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(lambda pid: (
            self._status_bar.showMessage(T('podcast_subscribed'), 5000),
            self._refresh_library()
        ))
        worker.error.connect(lambda msg: self._status_bar.showMessage(f"Error: {msg}", 5000))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)

        self._podcast_subscribe_worker = worker
        self._podcast_subscribe_thread = thread
        self._status_bar.showMessage(T('podcast_subscribe') + '...')
        thread.start()

    def _on_podcast_search(self):
        """Search podcasts online (iTunes directory) in a worker thread."""
        query, ok = QInputDialog.getText(
            self, T('podcast_search'), T('search')
        )
        if not ok or not query:
            return

        import threading

        self._status_bar.showMessage(T('podcast_search') + '...')

        def _search():
            try:
                results = search_podcasts(query)
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_podcast_search_done(results))
            except Exception as e:
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._status_bar.showMessage(f"{T('search_error')}: {e}", 5000))

        threading.Thread(target=_search, daemon=True).start()

    def _on_podcast_search_done(self, results):
        """Handle podcast search results on main thread."""
        if not results:
            self._status_bar.showMessage(T('no_results'), 3000)
            return

        items = [f"{r['name']} — {r['author']}" for r in results]
        item, ok = QInputDialog.getItem(
            self, T('podcast_search'),
            f"{len(results)} results:", items, 0, False
        )
        if ok:
            idx = items.index(item)
            feed_url = results[idx].get('feed_url')
            if feed_url:
                self._run_podcast_subscribe(feed_url)

    def _on_podcast_refresh(self):
        """Refresh all podcast feeds (in background thread)."""
        podcasts = db.fetchall("SELECT id, feed_url, title FROM podcasts WHERE feed_url IS NOT NULL")
        if not podcasts:
            self._status_bar.showMessage(T('no_podcast_subs'), 3000)
            return

        # Run in background thread to avoid blocking UI
        class RefreshWorker(QObject):
            finished = pyqtSignal(int)
            error = pyqtSignal(str)

            def __init__(self, pods):
                super().__init__()
                self._pods = pods

            def run(self):
                try:
                    new_total = 0
                    for pod in self._pods:
                        try:
                            feed_data = parse_rss_feed(pod['feed_url'])
                            if not feed_data:
                                continue
                            for ep in feed_data.get('episodes', []):
                                duration_ms = ep.get('duration_seconds', 0) * 1000
                                result = db.execute("""
                                    INSERT OR IGNORE INTO podcast_episodes(
                                        podcast_id, title, description, guid,
                                        published_at, duration_ms, file_url, file_size
                                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    pod['id'], ep.get('title'), ep.get('description'),
                                    ep.get('guid'), ep.get('published'),
                                    duration_ms, ep.get('audio_url'),
                                    ep.get('file_size', 0)
                                ), commit=False)
                                if result.rowcount > 0:
                                    new_total += 1
                            db.execute(
                                "UPDATE podcasts SET last_checked = datetime('now') WHERE id = ?",
                                (pod['id'],), commit=False
                            )
                        except Exception as e:
                            log.warning("Feed refresh failed for %s: %s", pod['title'], e)
                    db.commit()
                    self.finished.emit(new_total)
                except Exception as e:
                    log.exception("Podcast refresh error")
                    self.error.emit(str(e))
                finally:
                    db.close_connection()

        worker = RefreshWorker(list(podcasts))
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(lambda n: self._on_podcast_refresh_done(n))
        worker.error.connect(lambda msg: self._status_bar.showMessage(f"Error: {msg}", 5000))
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        self._podcast_thread = thread
        self._podcast_refresh_worker = worker
        self._status_bar.showMessage(T('podcast_refresh') + '...')
        thread.start()

    def _on_podcast_refresh_done(self, new_count):
        """Handle podcast refresh completion."""
        self._status_bar.showMessage(f"{new_count} new episodes found", 5000)
        self._refresh_library()

    # --- CD Rip ---

    def _on_cd_rip(self):
        """Import audio CD."""
        try:
            from cd_ripper import detect_cd_drives, CDRipWorker
        except ImportError:
            self._status_bar.showMessage(T('cd_ripper_unavailable'), 3000)
            return

        drives = detect_cd_drives()
        if not drives:
            self._status_bar.showMessage(T('cd_no_drive'), 3000)
            return

        # Find drive with media
        drive = None
        for d in drives:
            if d.get('has_media'):
                drive = d
                break
        if not drive:
            self._status_bar.showMessage(T('cd_no_disc'), 3000)
            return

        # Ask for output directory
        default_dir = str(Path.home() / 'Music')
        output_dir = QFileDialog.getExistingDirectory(
            self, T('cd_output_dir'), default_dir
        )
        if not output_dir:
            return

        worker = CDRipWorker(drive['drive'], output_dir)
        self._cd_thread = QThread()
        worker.moveToThread(self._cd_thread)

        self._cd_thread.started.connect(worker.run)
        worker.progress.connect(
            lambda t, total, desc: self._on_scan_progress(t, total, desc)
        )
        worker.finished.connect(lambda tracks, d: self._on_cd_rip_done(tracks, d))
        worker.error.connect(lambda msg: self._on_scan_error(msg))
        worker.finished.connect(self._cd_thread.quit)
        worker.error.connect(self._cd_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(T('cd_detecting'))
        self._cd_thread.start()
        self._cd_worker = worker

    def _on_cd_rip_done(self, tracks, album_dir):
        """Handle CD rip completion."""
        self._progress_bar.hide()
        self._status_bar.showMessage(
            T('cd_rip_done', tracks=tracks, dir=album_dir), 10000
        )
        # Scan the output directory to add to library
        if album_dir:
            self._start_scan([album_dir])

    # --- Harmonization ---

    def _on_harmonize(self):
        """Open harmonization dialog."""
        try:
            from harmonizer import HarmonizeWorker
        except ImportError:
            self._status_bar.showMessage(T('harmonizer_unavailable'), 3000)
            return

        # Preview first
        reply = QMessageBox.question(
            self, T('harmonize'),
            T('harmonize_preview') + '?\n' + T('harmonize_tip'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        worker = HarmonizeWorker(mode='preview')
        self._harmonize_thread = QThread()
        worker.moveToThread(self._harmonize_thread)

        self._harmonize_thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.preview.connect(self._on_harmonize_preview)
        worker.error.connect(lambda msg: self._on_scan_error(msg))
        worker.finished.connect(self._harmonize_thread.quit)
        worker.error.connect(self._harmonize_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._status_bar.showMessage(T('harmonize_running', current=0, total=0))
        self._harmonize_thread.start()
        self._harmonize_worker = worker

    def _on_harmonize_preview(self, changes):
        """Show harmonization preview and ask to apply."""
        self._progress_bar.hide()
        if not changes:
            self._status_bar.showMessage(T('no_changes_needed'), 5000)
            return

        # Show summary
        detail = '\n'.join(
            f"  {c.get('field', '?')}: {c.get('old', '?')} → {c.get('new', '?')}"
            for c in changes[:100]
        )
        if len(changes) > 100:
            detail += f"\n  ... and {len(changes) - 100} more"

        box = QMessageBox(self)
        box.setWindowTitle(T('harmonize'))
        box.setText(f"{len(changes)} changes proposed")
        box.setDetailedText(detail)
        box.setStandardButtons(
            QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel
        )
        result = box.exec()

        if result == QMessageBox.StandardButton.Apply:
            self._apply_harmonization()

    def _apply_harmonization(self):
        """Apply harmonization changes."""
        from harmonizer import HarmonizeWorker

        worker = HarmonizeWorker(mode='apply')
        self._harmonize_thread = QThread()
        worker.moveToThread(self._harmonize_thread)

        self._harmonize_thread.started.connect(worker.run)
        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(lambda stats: self._on_harmonize_done(stats))
        worker.error.connect(lambda msg: self._on_scan_error(msg))
        worker.finished.connect(self._harmonize_thread.quit)
        worker.error.connect(self._harmonize_thread.quit)

        self._progress_bar.setValue(0)
        self._progress_bar.show()
        self._harmonize_thread.start()
        self._harmonize_worker = worker

    def _on_harmonize_done(self, stats):
        """Handle harmonization completion."""
        self._progress_bar.hide()
        self._status_bar.showMessage(
            T('harmonize_done',
              artists=stats.get('artists_normalized', 0),
              albums=stats.get('albums_cleaned', 0),
              composers=stats.get('composers_fixed', 0),
              genres=stats.get('genres_merged', 0)),
            10000
        )
        self._refresh_library()

    # --- Classification ---

    def _on_organize_library(self):
        """Organize music files into Artist/Album/Track folder structure."""
        stats = db.get_library_stats()
        count = stats['tracks']
        if count == 0:
            self._status_bar.showMessage(T('no_changes_needed'), 3000)
            return

        dest = QFileDialog.getExistingDirectory(
            self, T('organize_library'), '',
            QFileDialog.Option.ShowDirsOnly
        )
        if not dest:
            return

        # Confirm
        reply = QMessageBox.question(
            self, T('organize_library'),
            T('organize_confirm', count=count, dest=dest),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from file_organizer import FileOrganizer
        self._organize_worker = FileOrganizer(dest)
        self._organize_thread = QThread()
        self._organize_worker.moveToThread(self._organize_thread)
        self._organize_thread.started.connect(self._organize_worker.run)
        self._organize_worker.progress.connect(
            lambda c, t, f: self._status_bar.showMessage(T('organize_running', current=c, total=t))
        )
        self._organize_worker.finished.connect(
            lambda moved, errs: (
                self._status_bar.showMessage(T('organize_done', count=moved), 10000),
                self._refresh_library(),
                self._organize_thread.quit()
            )
        )
        self._organize_worker.error.connect(
            lambda msg: (self._status_bar.showMessage(f"Error: {msg}", 5000),
                         self._organize_thread.quit())
        )
        self._organize_thread.start()

    def _on_classify_library(self):
        """Classify all tracks by musical period, form, and instrumentation.

        Stores results in database columns (period, form, catalogue, instruments, music_key).
        """
        from music_classifier import classify_track as _classify
        import html as html_mod
        esc = html_mod.escape

        tracks = db.fetchall(
            "SELECT t.id, t.title, t.composer, t.genre, t.year, "
            "a.title as album_title, ar.name as artist_name "
            "FROM tracks t "
            "LEFT JOIN albums a ON t.album_id = a.id "
            "LEFT JOIN artists ar ON t.artist_id = ar.id"
        )

        if not tracks:
            self._status_bar.showMessage(T('no_results'), 3000)
            return

        total = len(tracks)
        self._status_bar.showMessage(T('classify_running'))
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(total)
        self._progress_bar.show()

        # Classify all tracks and store in DB
        period_counts = {}
        form_counts = {}
        classified = 0

        for i, t in enumerate(tracks):
            cl = _classify(
                title=str(t.get('title', '') or ''),
                composer=str(t.get('composer', '') or ''),
                genre=str(t.get('genre', '') or ''),
                album=str(t.get('album_title', '') or ''),
                year=t.get('year'),
            )

            has_data = (cl['period'] or cl['form'] or cl['catalogue']
                        or cl['instruments'] or cl['key'])
            if has_data:
                classified += 1
                instruments_str = (', '.join(cl['instruments'])
                                   if cl['instruments'] else None)
                db.execute("""
                    UPDATE tracks SET
                        period=?, form=?, catalogue=?, instruments=?, music_key=?
                    WHERE id=?
                """, (cl['period'], cl['form'], cl['catalogue'],
                      instruments_str, cl['key'], t['id']), commit=False)

            if cl['period']:
                period_counts[cl['period']] = period_counts.get(cl['period'], 0) + 1
            if cl['form']:
                form_counts[cl['form']] = form_counts.get(cl['form'], 0) + 1

            # Batch commit + keep UI responsive every 500 tracks
            if (i + 1) % 500 == 0:
                db.commit()
                self._progress_bar.setValue(i + 1)
                self._status_bar.showMessage(
                    T('classify_running') + f" {i + 1}/{total}")
                QApplication.processEvents()

        db.commit()
        self._progress_bar.hide()

        # Refresh sidebar to show periods
        self._build_sidebar()

        # Build results dialog
        html = [f"<h3>{T('classify_library')}</h3>"]
        html.append(f"<p>{T('classify_done', count=classified)} / {len(tracks)}</p>")

        period_order = ['Medieval', 'Renaissance', 'Baroque', 'Classical',
                        'Romantic', 'Modern', 'Contemporary', 'Recent']
        if period_counts:
            html.append(f"<h4>{T('period')}</h4><table>")
            for period in period_order:
                count = period_counts.get(period, 0)
                if count:
                    pct = count * 100 // len(tracks)
                    html.append(f"<tr><td><b>{esc(period)}</b></td>"
                               f"<td align='right'>{count}</td>"
                               f"<td align='right'>{pct}%</td></tr>")
            html.append("</table>")

        if form_counts:
            html.append(f"<h4>{T('form')}</h4><table>")
            for form, count in sorted(form_counts.items(),
                                       key=lambda x: x[1], reverse=True)[:20]:
                html.append(f"<tr><td><b>{esc(form)}</b></td>"
                           f"<td align='right'>{count}</td></tr>")
            html.append("</table>")

        dlg = QDialog(self)
        dlg.setWindowTitle(T('classify_library'))
        dlg.setMinimumSize(450, 400)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml('\n'.join(html))
        layout.addWidget(browser)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn.accepted.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()

    # --- Audio Visualizer ---

    def _toggle_visualizer(self):
        """Show/hide the audio visualizer panel."""
        if self._visualizer_panel and self._visualizer_panel.isVisible():
            self._visualizer_panel.stop()
            self._visualizer_panel.hide()
            return

        # Lazy initialization
        if not self._audio_analyzer:
            from audio_visualizer import AudioAnalyzer, VisualizerPanel
            self._audio_analyzer = AudioAnalyzer()
            self._visualizer_panel = VisualizerPanel(self._audio_analyzer, self)
            self._visualizer_panel.closed.connect(
                lambda: self._visualizer_panel.hide()
            )
            self._visualizer_panel.setFixedHeight(160)

            # Connect player audio buffer to analyzer
            self._player.audio_buffer_ready.connect(self._audio_analyzer.feed)

            # Insert into layout before player bar
            central_layout = self.centralWidget().layout()
            # Insert before last 2 items (player bar + status bar)
            idx = central_layout.count() - 2
            central_layout.insertWidget(idx, self._visualizer_panel)

        self._visualizer_panel.show()
        self._visualizer_panel.start()

    # --- Statistics ---

    def _on_show_stats(self):
        """Show comprehensive library statistics dialog."""
        dlg = StatsDialog(self)
        dlg.exec()

    # --- State persistence ---

    def _restore_state(self):
        """Restore window geometry and state."""
        geo = self._settings.value('geometry')
        if geo:
            self.restoreGeometry(geo)
        state = self._settings.value('windowState')
        if state:
            self.restoreState(state)
        vol = self._settings.value('volume', 80, type=int)
        self._player.set_volume(vol)
        self._volume_slider.setValue(vol)

    def closeEvent(self, event):
        """Save state on close."""
        self._settings.setValue('geometry', self.saveGeometry())
        self._settings.setValue('windowState', self.saveState())
        self._settings.setValue('volume', self._player.volume)

        # Record play count for current track before closing
        import time as _time
        prev_path = getattr(self, '_playing_track_path', None)
        prev_start = getattr(self, '_playing_track_start', 0)
        if prev_path and (_time.time() - prev_start) >= PLAY_COUNT_THRESHOLD_S:
            db.execute(
                "UPDATE tracks SET play_count = play_count + 1, last_played = datetime('now') WHERE file_path = ?",
                (prev_path,), commit=True
            )

        # Stop playback and watcher
        self._player.stop()
        self._backup_timer.stop()
        if hasattr(self, '_watcher'):
            self._watcher.stop()

        # Cancel all workers
        for worker_attr in ('_scan_worker', '_import_worker', '_fetch_worker',
                            '_harmonize_worker', '_cd_worker',
                            '_podcast_import_worker', '_podcast_refresh_worker',
                            '_podcast_subscribe_worker'):
            worker = getattr(self, worker_attr, None)
            if worker and hasattr(worker, 'cancel'):
                worker.cancel()

        # Wait for all threads to finish (5s timeout, then terminate)
        for thread_attr in ('_scan_thread', '_import_thread', '_fetch_thread',
                            '_harmonize_thread', '_cd_thread',
                            '_podcast_thread', '_podcast_import_thread',
                            '_podcast_subscribe_thread'):
            thread = getattr(self, thread_attr, None)
            if thread and thread.isRunning():
                thread.quit()
                if not thread.wait(5000):
                    log.warning("Thread %s did not stop, terminating", thread_attr)
                    thread.terminate()
                    thread.wait(1000)

        # Backup on exit
        try:
            from musicotheque import DB_PATH, BACKUP_DIR
            backup_database(str(DB_PATH), str(BACKUP_DIR), label='exit')
        except Exception as e:
            log.warning("Exit backup failed: %s", e)

        db.close_connection()
        event.accept()


class SettingsDialog(QDialog):
    """Settings dialog with scan folders, language, and audio output."""

    def __init__(self, player=None, parent=None):
        super().__init__(parent)
        self._player = player
        self.setWindowTitle(T('settings'))
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # --- Audio Output ---
        grp_audio = QGroupBox(T('audio_output'))
        grp_audio.setToolTip(T('audio_output_tip'))
        audio_layout = QVBoxLayout(grp_audio)

        # Device selector
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel(T('audio_device')))
        self._device_combo = QComboBox()
        self._device_combo.setToolTip(T('audio_device_tip'))
        self._device_combo.setMinimumWidth(280)

        # Populate devices
        self._devices = []
        current_dev_name = ''
        saved_row = db.fetchone("SELECT value FROM config WHERE key = 'audio_device'")
        saved_name = saved_row['value'] if saved_row else ''

        self._device_combo.addItem(T('audio_device_default'), '')
        if player:
            self._devices = player.get_audio_devices()
            current_dev = player.get_current_device()
            current_dev_name = current_dev.description() if current_dev else ''

            for dev in self._devices:
                name = dev.description()
                suffix = ' *' if dev.isDefault() else ''
                self._device_combo.addItem(f"{name}{suffix}", name)

            # Select current device
            if saved_name:
                for i in range(self._device_combo.count()):
                    if self._device_combo.itemData(i) == saved_name:
                        self._device_combo.setCurrentIndex(i)
                        break

        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        dev_row.addWidget(self._device_combo)
        audio_layout.addLayout(dev_row)

        # Device capabilities display
        self._caps_label = QLabel('')
        self._caps_label.setStyleSheet("font-size: 10px; color: #888; padding: 4px 0;")
        self._caps_label.setWordWrap(True)
        audio_layout.addWidget(self._caps_label)
        self._update_caps_display()

        layout.addWidget(grp_audio)

        # --- Scan folders ---
        grp_folders = QGroupBox(T('add_folder'))
        folders_layout = QVBoxLayout(grp_folders)

        self._folder_list = QTreeWidget()
        self._folder_list.setHeaderHidden(True)
        folders = db.fetchall("SELECT id, path FROM scan_folders ORDER BY path")
        for f in folders:
            item = QTreeWidgetItem(self._folder_list, [f['path']])
            item.setData(0, Qt.ItemDataRole.UserRole, f['id'])
        folders_layout.addWidget(self._folder_list)

        btn_row = QHBoxLayout()
        btn_add = QPushButton('+')
        btn_add.setToolTip(T('add_folder'))
        btn_add.clicked.connect(self._add_folder)
        btn_rm = QPushButton('-')
        btn_rm.setToolTip(T('cancel'))
        btn_rm.clicked.connect(self._remove_folder)
        btn_row.addWidget(btn_add)
        btn_row.addWidget(btn_rm)
        btn_row.addStretch()
        folders_layout.addLayout(btn_row)

        layout.addWidget(grp_folders)

        # --- Language ---
        grp_lang = QGroupBox('Language / Langue')
        lang_layout = QHBoxLayout(grp_lang)
        self._lang_combo = QComboBox()
        self._lang_combo.addItem('English', 'en')
        self._lang_combo.addItem('Français', 'fr')
        current_idx = 0 if get_lang() == 'en' else 1
        self._lang_combo.setCurrentIndex(current_idx)
        lang_layout.addWidget(self._lang_combo)
        layout.addWidget(grp_lang)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_device_changed(self, index):
        """Update capabilities display when device selection changes."""
        self._update_caps_display()

    def _update_caps_display(self):
        """Show capabilities of the selected device."""
        if not self._player:
            self._caps_label.setText('')
            return

        idx = self._device_combo.currentIndex()
        if idx <= 0:
            # System default
            dev = None
            for d in self._devices:
                if d.isDefault():
                    dev = d
                    break
            if not dev and self._devices:
                dev = self._devices[0]
        else:
            dev_name = self._device_combo.itemData(idx)
            dev = None
            for d in self._devices:
                if d.description() == dev_name:
                    dev = d
                    break

        if dev:
            info = self._player.get_device_info(dev)
            min_r = info.get('min_sample_rate', 0)
            max_r = info.get('max_sample_rate', 0)
            max_ch = info.get('max_channels', 0)
            fmts = info.get('sample_formats', [])

            rate_str = f"{min_r/1000:.0f}–{max_r/1000:.0f}kHz" if min_r and max_r else '?'
            fmt_str = ', '.join(fmts) if fmts else '?'
            self._caps_label.setText(
                T('audio_device_caps', rates=rate_str, channels=max_ch, formats=fmt_str)
            )
        else:
            self._caps_label.setText('')

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, T('add_folder'))
        if folder:
            db.execute("INSERT OR IGNORE INTO scan_folders(path) VALUES(?)",
                       (folder,), commit=True)
            row = db.fetchone("SELECT id FROM scan_folders WHERE path = ?", (folder,))
            if row:
                item = QTreeWidgetItem(self._folder_list, [folder])
                item.setData(0, Qt.ItemDataRole.UserRole, row['id'])

    def _remove_folder(self):
        current = self._folder_list.currentItem()
        if current:
            fid = current.data(0, Qt.ItemDataRole.UserRole)
            db.execute("DELETE FROM scan_folders WHERE id = ?", (fid,), commit=True)
            idx = self._folder_list.indexOfTopLevelItem(current)
            self._folder_list.takeTopLevelItem(idx)

    def _on_accept(self):
        # Language
        lang = self._lang_combo.currentData()
        set_lang(lang)
        db.execute("INSERT OR REPLACE INTO config(key, value) VALUES('lang', ?)",
                   (lang,), commit=True)

        # Audio device
        dev_name = self._device_combo.currentData() or ''
        db.execute("INSERT OR REPLACE INTO config(key, value) VALUES('audio_device', ?)",
                   (dev_name,), commit=True)
        if self._player:
            if dev_name:
                self._player.set_audio_device_by_name(dev_name)
            else:
                self._player.set_audio_device(None)  # System default

        self.accept()


class HelpDialog(QDialog):
    """Bilingual help dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T('help_title'))
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        browser = QTextBrowser()

        if get_lang() == 'fr':
            browser.setHtml(self._help_fr())
        else:
            browser.setHtml(self._help_en())

        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def _help_en(self):
        return """
        <h2>MusicOthèque Help</h2>

        <h3>Getting Started</h3>
        <p>Add your music folders via <b>File → Add Music Folder</b> (Ctrl+O).
        MusicOthèque scans folders recursively, extracts metadata from audio files,
        and builds a searchable library with cover art.</p>

        <h3>Supported Formats</h3>
        <p>MP3, FLAC, OGG, Opus, M4A, AAC, WMA, WAV, AIFF, ALAC, APE, WavPack,
        DSD (DSF/DFF), MKA, TTA, SPX, MPC, MP4, OGA — 21+ formats via mutagen.</p>

        <h3>Library Navigation</h3>
        <ul>
        <li><b>All Tracks</b> — Every track in your library, sorted by artist/album</li>
        <li><b>Artists</b> — Browse by artist with track counts</li>
        <li><b>Albums</b> — Browse by album with year and artist</li>
        <li><b>Genres</b> — Filter by musical genre</li>
        <li><b>Playlists</b> — User and imported playlists</li>
        </ul>
        <p>Right-click any track for a context menu: play, queue, add to playlist,
        show in file explorer, or view track details.</p>

        <h3>Playback Controls</h3>
        <ul>
        <li><b>Space</b> — Play/Pause</li>
        <li><b>Ctrl+Right/Left</b> — Next/Previous track</li>
        <li><b>Ctrl+Up/Down</b> — Volume up/down</li>
        <li><b>Ctrl+.</b> — Stop playback</li>
        </ul>
        <p>Shuffle and repeat modes (Off / All / One) are available in the player bar.
        The player supports gapless playback with pre-buffering near end of track.
        Play count is only incremented after 30 seconds of listening (skips don't count).</p>

        <h3>Smart Radio (Ctrl+R)</h3>
        <p><b>Play → Smart Radio</b> — Play random tracks with intelligent, combinable filters:</p>
        <ul>
        <li><b>Genre</b> — Filter by musical genre</li>
        <li><b>Artist</b> — Filter by performer</li>
        <li><b>Composer</b> — Filter by composer (ideal for classical music)</li>
        <li><b>Album</b> — Filter by specific album or work</li>
        <li><b>Era</b> — Medieval, Renaissance, Baroque (1600–1750), Classical (1750–1820),
        Romantic (1820–1900), Modern (1900–1950), Contemporary (1950–2000), Recent (2000+),
        or a custom year range</li>
        <li><b>Audio quality</b> — Hi-Res, CD Quality, Lossless, or Lossy</li>
        <li><b>Minimum rating</b> — Only tracks rated ★ or above</li>
        <li><b>Unplayed only</b> — Discover tracks you haven't listened to yet</li>
        </ul>
        <p>All filters combine with AND logic. A live counter shows how many tracks match.
        You can set a limit (e.g. "play 50 random tracks") or play all matching tracks shuffled.</p>

        <h3>Search (Ctrl+F)</h3>
        <p>Full-text search across titles, artists, albums, genres, and composers.
        Uses SQLite FTS5 with Unicode support and diacritics removal. Minimum 2 characters.
        Falls back to LIKE search if FTS encounters special characters.</p>

        <h3>iTunes Import</h3>
        <p><b>File → Import iTunes Library</b> — Select your <code>iTunes Library.xml</code>.
        Imports tracks, playlists, play counts, and ratings. Smart playlists are imported
        as static snapshots. System playlists (Library, Music, Podcasts) are skipped.
        Path remapping available for relocated libraries.</p>

        <h3>Podcasts</h3>
        <p><b>View → Subscribe to Podcast</b> — Add a podcast by RSS feed URL.
        <b>View → Search Podcasts Online</b> — Search the iTunes podcast directory.
        <b>View → Refresh Feeds</b> — Check all feeds for new episodes.
        Episodes can be downloaded for offline listening. Playback position is saved.</p>

        <h3>Web Radio</h3>
        <p>Listen to internet radio stations from around the world. Expand the
        <b>Web Radio</b> section in the sidebar to browse stations by category:</p>
        <ul>
        <li><b>Classical</b> — France Musique (+ Baroque, Concerts, Easy Classique,
        Contemporaine, Jazz, Ocora), Radio Classique, BBC Radio 3, Rai Radio 3 Classica,
        RTS Espace 2, WQXR (New York), BR-Klassik, Concertzender, ABC Classic</li>
        <li><b>Culture</b> — France Culture, France Inter</li>
        <li><b>News</b> — Franceinfo, BBC World Service, NPR (WNYC)</li>
        <li><b>Eclectic</b> — FIP and its themed channels (Rock, Jazz, Electro, World,
        Groove, Pop, Nouveautés)</li>
        </ul>
        <p>Click any station to start streaming. A LIVE badge appears in the player bar.
        Click any track in your library to return to local playback.</p>

        <h3>CD Audio Import</h3>
        <p><b>File → Import Audio CD</b> — Rip audio CDs to FLAC with automatic
        MusicBrainz lookup for track names, album, artist, and cover art.
        Requires ffmpeg installed on your system.</p>

        <h3>Online Metadata (MusicBrainz)</h3>
        <p><b>View → Fetch Metadata Online</b> — Searches MusicBrainz for track info.
        Select specific tracks first, or leave empty to process all unmatched tracks.
        Cover art is fetched from Cover Art Archive. Rate-limited (1 req/sec).</p>

        <h3>Tools Menu</h3>
        <ul>
        <li><b>Harmonize Metadata</b> — Normalize artist names, composers, album titles,
        and genres across your library. Preview changes before applying. Undo supported.</li>
        <li><b>Library Statistics</b> (Ctrl+I) — Comprehensive overview: track/album/artist
        counts, format distribution, quality breakdown, top artists, genres, most played,
        total size and duration.</li>
        <li><b>Backup Database</b> — Create a manual backup of the music database</li>
        <li><b>Restore Database</b> — Restore from a previous backup (5 daily + 4 weekly kept)</li>
        <li><b>Relocate Music Paths</b> — Update all file paths when your music library
        has moved (e.g., <code>J:/Musique</code> → <code>/mnt/nas/Musique</code>).
        Essential when switching between Windows and Linux.</li>
        <li><b>Check Broken Paths</b> — Find tracks whose files no longer exist on disk</li>
        <li><b>Export Library</b> — Export all metadata to portable JSON format</li>
        <li><b>Reset Play Counts</b> — Reset all play counts and last-played dates
        for privacy. Individual tracks can also be reset via right-click context menu.</li>
        <li><b>Classify Library</b> — Automatic classification of all tracks by musical
        period, form/genre, catalogue number, instrumentation, and key. Especially useful
        for classical music collections. The classifier recognizes 200+ composers across all
        periods (Medieval to Contemporary), 60+ musical forms (Symphony, Concerto, Sonata,
        Fugue, Nocturne, Opera, etc.), catalogue numbers (BWV, K., Op., D., RV, HWV...),
        and instruments. Classification also appears in the track details dialog (right-click
        → Track Info).</li>
        <li><b>Organize Files on Disk</b> — Sort music files into a clean Artist / Album / Track
        folder structure. Files are moved and database paths are updated automatically.</li>
        </ul>

        <h3>Audio Visualizer (Ctrl+V)</h3>
        <p><b>View → Audio Visualizer</b> — Real-time audio visualization during playback:</p>
        <ul>
        <li><b>Spectrum Analyzer</b> — 64-bar frequency display with peak hold and smooth decay.
        Colors: green (low) → yellow (mid) → red (high). Updated at 20 fps.</li>
        <li><b>VU Meter</b> — Stereo RMS level meter with peak indicators and dB scale
        (-60 to 0 dB). Updated at 15 fps.</li>
        <li><b>Spectrogram</b> — Waterfall frequency display showing frequency content over time.
        Heat-map coloring from black (silence) to white (loud). Updated at 12 fps.</li>
        </ul>
        <p>Uses QAudioBufferOutput for zero-copy PCM access — no external audio capture needed.
        Total CPU usage &lt; 4%. Toggle on/off anytime with Ctrl+V.</p>

        <h3>Music Classification</h3>
        <p><b>Tools → Classify Library</b> — Automatic classification of your tracks:</p>
        <ul>
        <li><b>Musical period</b> — 350+ composers mapped to Medieval, Renaissance, Baroque,
        Classical, Romantic, Modern, Contemporary periods</li>
        <li><b>Sub-period</b> — Refined classification: Early/High/Late Baroque,
        Galant Style, Early/High/Late Romantic, Fin de Siècle, Interwar Modernism</li>
        <li><b>Musical movement</b> — 20+ styles detected: Impressionism, Expressionism,
        Neoclassicism, Serialism, Minimalism, Holy Minimalism, Nationalism,
        Late Romanticism, Neo-Romanticism, Avant-Garde, Film Music, Verismo,
        Bel Canto, Spectralism, Ars Nova, Franco-Flemish School, Venetian School</li>
        <li><b>Musical form</b> — 70+ forms detected: Symphony, Concerto, Sonata, Fugue,
        Nocturne, Opera, Requiem, String Quartet, Bagatelle, Elegy, Romance, etc.</li>
        <li><b>Catalogue number</b> — BWV (Bach), K. (Mozart), Op., D. (Schubert),
        RV (Vivaldi), HWV (Handel), and more</li>
        <li><b>Instrumentation</b> — Piano, Violin, Orchestra, Chamber, Choir, etc.</li>
        <li><b>Key</b> — e.g., "C minor", "E♭ major"</li>
        </ul>
        <p>Classification data is written directly to audio file metadata
        (TXXX frames for MP3, Vorbis comments for FLAC/OGG, MP4 atoms).</p>
        <p>Right-click any track → Track Info to see individual classification details.</p>

        <h3>Audio Output & HiFi Chain</h3>
        <p><b>File → Settings → Audio Output</b> — Select your audio output device (DAC,
        USB headphones, speakers, etc.). The player bar shows the full audio chain in real time:</p>
        <ul>
        <li><b>Quality badge</b> — Hi-Res, CD Quality, Lossless, or Lossy</li>
        <li><b>Format details</b> — Codec, sample rate, bit depth (e.g. "FLAC · 96kHz/24-bit")</li>
        <li><b>Output device</b> — Current audio device name (e.g. "→ USB DAC")</li>
        </ul>
        <p>Device capabilities (supported sample rates, channel count, bit formats) are displayed
        in Settings. The selected device is remembered across sessions.</p>

        <h3>Audio Quality Indicators</h3>
        <ul>
        <li><span style="color:#f8f"><b>Hi-Res</b></span> — Sample rate > 48kHz or bit depth > 16-bit</li>
        <li><span style="color:#8f8"><b>CD Quality</b></span> — 44.1kHz / 16-bit lossless</li>
        <li><span style="color:#8f8"><b>Lossless</b></span> — FLAC, ALAC, WAV, AIFF, APE, WavPack</li>
        <li><span style="color:#ff8"><b>Lossy</b></span> — MP3, AAC, OGG, Opus, WMA</li>
        </ul>

        <h3>File Organizer</h3>
        <p><b>Tools → Organize Files on Disk</b> — Sorts all music files into a clean
        <code>Artist / Album / Track</code> folder structure. Files are MOVED (not copied).
        Database paths are updated automatically. Safe filename sanitization for all platforms.</p>

        <h3>Library Watcher</h3>
        <p>MusicOthèque automatically monitors your scan folders for changes (new files,
        modifications, deletions). When changes are detected, a background re-scan is triggered.
        If a drive letter changes (e.g., P: becomes Q:), paths are auto-relocated transparently.</p>

        <h3>Data Safety</h3>
        <p>Continuous auto-backup every 5 minutes (background thread, transparent). Additional
        backup on application exit. Backup rotation keeps 5 recent daily + 4 weekly. All database
        writes use SQLite WAL mode with thread-safe locking. Atomic saves prevent corruption.</p>

        <h3>Cross-Platform</h3>
        <p>Works on Windows, Linux, and macOS. Data is stored in the OS-appropriate
        location (APPDATA / XDG_DATA_HOME / Library). Use <b>Tools → Relocate Paths</b>
        when opening the same library on a different OS. Automatic path relocation on drive
        letter changes.</p>

        <h3>Keyboard Shortcuts</h3>
        <table border="0" cellpadding="4">
        <tr><td><b>Space</b></td><td>Play / Pause</td></tr>
        <tr><td><b>Ctrl+Right</b></td><td>Next track</td></tr>
        <tr><td><b>Ctrl+Left</b></td><td>Previous track</td></tr>
        <tr><td><b>Ctrl+Up/Down</b></td><td>Volume +/-</td></tr>
        <tr><td><b>Ctrl+.</b></td><td>Stop</td></tr>
        <tr><td><b>Ctrl+O</b></td><td>Add music folder</td></tr>
        <tr><td><b>Ctrl+F</b></td><td>Focus search bar</td></tr>
        <tr><td><b>F5</b></td><td>Rescan all folders</td></tr>
        <tr><td><b>Ctrl+R</b></td><td>Smart Radio</td></tr>
        <tr><td><b>Ctrl+V</b></td><td>Audio Visualizer</td></tr>
        <tr><td><b>Ctrl+I</b></td><td>Library Statistics</td></tr>
        <tr><td><b>Ctrl+,</b></td><td>Settings</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
        <tr><td><b>F1</b></td><td>This help</td></tr>
        </table>
        """

    def _help_fr(self):
        return """
        <h2>Aide MusicOthèque</h2>

        <h3>Démarrage</h3>
        <p>Ajoutez vos dossiers musicaux via <b>Fichier → Ajouter un dossier musical</b> (Ctrl+O).
        MusicOthèque scanne les dossiers récursivement, extrait les métadonnées des fichiers
        audio, et construit une bibliothèque cherchable avec pochettes d'albums.</p>

        <h3>Formats Supportés</h3>
        <p>MP3, FLAC, OGG, Opus, M4A, AAC, WMA, WAV, AIFF, ALAC, APE, WavPack,
        DSD (DSF/DFF), MKA, TTA, SPX, MPC, MP4, OGA — 21+ formats via mutagen.</p>

        <h3>Navigation dans la Bibliothèque</h3>
        <ul>
        <li><b>Toutes les pistes</b> — Toutes les pistes, triées par artiste/album</li>
        <li><b>Artistes</b> — Parcourir par artiste avec nombre de pistes</li>
        <li><b>Albums</b> — Parcourir par album avec année et artiste</li>
        <li><b>Genres</b> — Filtrer par genre musical</li>
        <li><b>Playlists</b> — Playlists utilisateur et importées</li>
        </ul>
        <p>Clic droit sur une piste pour le menu contextuel : lire, mettre en file,
        ajouter à une playlist, afficher dans l'explorateur, ou voir les détails.</p>

        <h3>Contrôles de Lecture</h3>
        <ul>
        <li><b>Espace</b> — Lecture/Pause</li>
        <li><b>Ctrl+Droite/Gauche</b> — Piste suivante/précédente</li>
        <li><b>Ctrl+Haut/Bas</b> — Volume +/-</li>
        <li><b>Ctrl+.</b> — Arrêter la lecture</li>
        </ul>
        <p>Les modes aléatoire et répétition (Désactivé / Tout / Un) sont dans la barre
        de lecture. Le lecteur supporte la lecture sans coupure avec pré-chargement.
        Le compteur de lecture ne s'incrémente qu'après 30 secondes d'écoute (les skips ne comptent pas).</p>

        <h3>Radio Intelligente (Ctrl+R)</h3>
        <p><b>Lecture → Radio intelligente</b> — Lire des pistes aléatoires avec filtres intelligents combinables :</p>
        <ul>
        <li><b>Genre</b> — Filtrer par genre musical</li>
        <li><b>Artiste</b> — Filtrer par interprète</li>
        <li><b>Compositeur</b> — Filtrer par compositeur (idéal pour la musique classique)</li>
        <li><b>Album</b> — Filtrer par album ou œuvre spécifique</li>
        <li><b>Époque</b> — Médiéval, Renaissance, Baroque (1600–1750), Classique (1750–1820),
        Romantique (1820–1900), Moderne (1900–1950), Contemporain (1950–2000), Récent (2000+),
        ou période personnalisée</li>
        <li><b>Qualité audio</b> — Hi-Res, Qualité CD, Sans perte ou Avec perte</li>
        <li><b>Note minimum</b> — Uniquement les pistes notées ★ ou plus</li>
        <li><b>Jamais écoutées</b> — Découvrir les pistes pas encore écoutées</li>
        </ul>
        <p>Tous les filtres se combinent en ET. Un compteur en direct montre le nombre de pistes
        correspondantes. Possibilité de limiter (ex. « lire 50 pistes aléatoires ») ou de tout lire en aléatoire.</p>

        <h3>Recherche (Ctrl+F)</h3>
        <p>Recherche plein texte sur titres, artistes, albums, genres et compositeurs.
        Utilise SQLite FTS5 avec support Unicode et suppression des diacritiques.
        Minimum 2 caractères. Repli sur recherche LIKE si FTS rencontre des caractères spéciaux.</p>

        <h3>Import iTunes</h3>
        <p><b>Fichier → Importer la bibliothèque iTunes</b> — Sélectionnez votre
        <code>iTunes Library.xml</code>. Importe les pistes, playlists, compteurs de
        lecture et notes. Les playlists intelligentes sont importées comme instantanés
        statiques. Les playlists système sont ignorées.</p>

        <h3>Podcasts</h3>
        <p><b>Affichage → S'abonner à un podcast</b> — Ajouter un podcast par URL RSS.
        <b>Affichage → Chercher des podcasts</b> — Chercher dans le répertoire iTunes.
        <b>Affichage → Actualiser les flux</b> — Vérifier les nouveaux épisodes.
        Les épisodes peuvent être téléchargés pour écoute hors ligne. La position est sauvegardée.</p>

        <h3>Web Radio</h3>
        <p>Écoutez des stations de radio en ligne du monde entier. Développez la section
        <b>Web Radio</b> dans la barre latérale pour parcourir les stations par catégorie :</p>
        <ul>
        <li><b>Classique</b> — France Musique (+ Baroque, Concerts, Easy Classique,
        Contemporaine, Jazz, Ocora), Radio Classique, BBC Radio 3, Rai Radio 3 Classica,
        RTS Espace 2, WQXR (New York), BR-Klassik, Concertzender, ABC Classic</li>
        <li><b>Culture</b> — France Culture, France Inter</li>
        <li><b>Info</b> — Franceinfo, BBC World Service, NPR (WNYC)</li>
        <li><b>Éclectique</b> — FIP et ses chaînes thématiques (Rock, Jazz, Electro, World,
        Groove, Pop, Nouveautés)</li>
        </ul>
        <p>Cliquez sur une station pour commencer le streaming. Un badge EN DIRECT apparaît
        dans la barre de lecture. Cliquez sur une piste de votre bibliothèque pour revenir
        à la lecture locale.</p>

        <h3>Import CD Audio</h3>
        <p><b>Fichier → Importer un CD audio</b> — Extraire les CD audio en FLAC avec
        recherche automatique MusicBrainz pour les titres, album, artiste et pochette.
        Nécessite ffmpeg installé sur votre système.</p>

        <h3>Métadonnées en Ligne (MusicBrainz)</h3>
        <p><b>Affichage → Récupérer les métadonnées</b> — Recherche MusicBrainz pour
        les informations des pistes. Sélectionnez des pistes spécifiques ou laissez vide
        pour traiter toutes les pistes sans identifiant. Les pochettes sont récupérées
        depuis Cover Art Archive. Limité à 1 requête/seconde.</p>

        <h3>Menu Outils</h3>
        <ul>
        <li><b>Harmoniser les métadonnées</b> — Normaliser les noms d'artistes, compositeurs,
        titres d'albums et genres dans toute la bibliothèque. Aperçu avant application. Annulation possible.</li>
        <li><b>Statistiques</b> (Ctrl+I) — Vue d'ensemble complète : nombre de pistes/albums/artistes,
        répartition par format, qualité audio, artistes principaux, genres, plus écoutés,
        taille et durée totales.</li>
        <li><b>Sauvegarder la base</b> — Créer une sauvegarde manuelle de la base musicale</li>
        <li><b>Restaurer la base</b> — Restaurer depuis une sauvegarde (5 quotidiennes + 4 hebdomadaires)</li>
        <li><b>Déplacer les chemins</b> — Mettre à jour tous les chemins quand la
        bibliothèque a été déplacée (ex. <code>J:/Musique</code> → <code>/mnt/nas/Musique</code>).
        Essentiel lors du passage entre Windows et Linux.</li>
        <li><b>Vérifier les chemins cassés</b> — Trouver les pistes dont les fichiers n'existent plus</li>
        <li><b>Exporter la bibliothèque</b> — Exporter toutes les métadonnées en JSON portable</li>
        <li><b>Réinitialiser les compteurs</b> — Remet à zéro tous les compteurs de lecture
        et dates pour l'anonymat. Réinitialisation individuelle via clic droit sur une piste.</li>
        <li><b>Classifier la bibliothèque</b> — Classification automatique de toutes les pistes
        par période musicale, forme/genre, numéro de catalogue, instrumentation et tonalité.
        Particulièrement utile pour les collections de musique classique. Le classifieur
        reconnaît 200+ compositeurs de toutes les époques (Médiéval à Contemporain), 60+
        formes musicales (Symphonie, Concerto, Sonate, Fugue, Nocturne, Opéra, etc.),
        numéros de catalogue (BWV, K., Op., D., RV, HWV...) et instruments. La classification
        apparaît aussi dans les détails de la piste (clic droit → Informations).</li>
        <li><b>Organiser les fichiers</b> — Trie vos fichiers musicaux dans une structure
        propre Artiste / Album / Piste. Les fichiers sont déplacés et la base mise à jour.</li>
        </ul>

        <h3>Visualiseur Audio (Ctrl+V)</h3>
        <p><b>Affichage → Visualiseur audio</b> — Visualisation audio en temps réel pendant la lecture :</p>
        <ul>
        <li><b>Analyseur spectral</b> — 64 barres de fréquences avec pic et décroissance.
        Couleurs : vert (bas) → jaune (milieu) → rouge (haut). Rafraîchi à 20 fps.</li>
        <li><b>VU-mètre</b> — Niveau RMS stéréo avec indicateurs de pic et échelle dB
        (-60 à 0 dB). Rafraîchi à 15 fps.</li>
        <li><b>Spectrogramme</b> — Affichage en cascade montrant le contenu fréquentiel au fil du temps.
        Colorisation thermique du noir (silence) au blanc (fort). Rafraîchi à 12 fps.</li>
        </ul>
        <p>Utilise QAudioBufferOutput pour l'accès direct aux données PCM — aucune capture
        audio externe nécessaire. Utilisation CPU totale &lt; 4%. Activer/désactiver à tout moment
        avec Ctrl+V.</p>

        <h3>Classification Musicale</h3>
        <p><b>Outils → Classifier la bibliothèque</b> — Classification automatique de vos pistes :</p>
        <ul>
        <li><b>Période musicale</b> — 350+ compositeurs classés par époque : Médiéval,
        Renaissance, Baroque, Classique, Romantique, Moderne, Contemporain</li>
        <li><b>Sous-période</b> — Classification affinée : Premier/Haut/Tardif Baroque,
        Style galant, Début/Haut/Tardif Romantique, Fin de siècle, Modernisme entre-deux-guerres</li>
        <li><b>Courant musical</b> — 20+ styles détectés : Impressionnisme, Expressionnisme,
        Néoclassicisme, Sérialisme, Minimalisme, Minimalisme sacré, Nationalisme,
        Romantisme tardif, Néo-romantisme, Avant-Garde, Musique de film, Vérisme,
        Bel Canto, Spectralisme, Ars Nova, École franco-flamande, École vénitienne</li>
        <li><b>Forme musicale</b> — 70+ formes détectées : Symphonie, Concerto, Sonate, Fugue,
        Nocturne, Opéra, Requiem, Quatuor à cordes, Bagatelle, Élégie, Romance, etc.</li>
        <li><b>Numéro de catalogue</b> — BWV (Bach), K. (Mozart), Op., D. (Schubert),
        RV (Vivaldi), HWV (Händel), et plus</li>
        <li><b>Instrumentation</b> — Piano, Violon, Orchestre, Musique de chambre, Chœur, etc.</li>
        <li><b>Tonalité</b> — ex. « Do mineur », « Mi♭ majeur »</li>
        </ul>
        <p>La classification est écrite directement dans les métadonnées des fichiers audio
        (tags TXXX pour MP3, Vorbis comments pour FLAC/OGG, atoms MP4).</p>
        <p>Clic droit sur une piste → Informations pour voir la classification individuelle.</p>

        <h3>Sortie Audio & Chaîne HiFi</h3>
        <p><b>Fichier → Paramètres → Sortie Audio</b> — Sélectionnez votre périphérique de sortie
        (DAC USB, casque, enceintes, etc.). La barre de lecture affiche la chaîne audio complète
        en temps réel :</p>
        <ul>
        <li><b>Badge qualité</b> — Hi-Res, Qualité CD, Sans perte ou Avec perte</li>
        <li><b>Détails format</b> — Codec, fréquence d'échantillonnage, profondeur (ex. « FLAC · 96kHz/24-bit »)</li>
        <li><b>Périphérique de sortie</b> — Nom du périphérique actuel (ex. « → USB DAC »)</li>
        </ul>
        <p>Les capacités du périphérique (fréquences supportées, nombre de canaux, formats) sont
        affichées dans les paramètres. Le périphérique sélectionné est mémorisé entre les sessions.</p>

        <h3>Indicateurs Qualité Audio</h3>
        <ul>
        <li><span style="color:#f8f"><b>Hi-Res</b></span> — Échantillonnage > 48kHz ou profondeur > 16 bits</li>
        <li><span style="color:#8f8"><b>Qualité CD</b></span> — 44.1kHz / 16 bits sans perte</li>
        <li><span style="color:#8f8"><b>Sans perte</b></span> — FLAC, ALAC, WAV, AIFF, APE, WavPack</li>
        <li><span style="color:#ff8"><b>Avec perte</b></span> — MP3, AAC, OGG, Opus, WMA</li>
        </ul>

        <h3>Organisateur de fichiers</h3>
        <p><b>Outils → Organiser les fichiers sur le disque</b> — Trie tous les fichiers dans une
        structure propre <code>Artiste / Album / Piste</code>. Les fichiers sont DÉPLACÉS (pas copiés).
        Les chemins en base sont mis à jour automatiquement. Noms de fichiers assainis pour toutes les plateformes.</p>

        <h3>Surveillance de la bibliothèque</h3>
        <p>MusicOthèque surveille automatiquement vos dossiers de scan pour détecter les changements
        (nouveaux fichiers, modifications, suppressions). Un re-scan en arrière-plan est déclenché
        automatiquement. Si une lettre de lecteur change (ex. P: devient Q:), les chemins sont
        relocalisés automatiquement et de manière transparente.</p>

        <h3>Sécurité des Données</h3>
        <p>Sauvegarde continue automatique toutes les 5 minutes (thread en arrière-plan, transparente).
        Sauvegarde supplémentaire à la fermeture. La rotation garde 5 sauvegardes quotidiennes
        récentes + 4 hebdomadaires. Toutes les écritures utilisent SQLite WAL avec verrouillage
        thread-safe. Sauvegardes atomiques pour éviter la corruption.</p>

        <h3>Multi-Plateforme</h3>
        <p>Fonctionne sur Windows, Linux et macOS. Les données sont stockées dans le
        répertoire approprié au système (APPDATA / XDG_DATA_HOME / Library). Utilisez
        <b>Outils → Déplacer les chemins</b> pour ouvrir la même bibliothèque sur un autre OS.
        Relocalisation automatique des chemins lors des changements de lettre de lecteur.</p>

        <h3>Raccourcis Clavier</h3>
        <table border="0" cellpadding="4">
        <tr><td><b>Espace</b></td><td>Lecture / Pause</td></tr>
        <tr><td><b>Ctrl+Droite</b></td><td>Piste suivante</td></tr>
        <tr><td><b>Ctrl+Gauche</b></td><td>Piste précédente</td></tr>
        <tr><td><b>Ctrl+Haut/Bas</b></td><td>Volume +/-</td></tr>
        <tr><td><b>Ctrl+.</b></td><td>Arrêt</td></tr>
        <tr><td><b>Ctrl+O</b></td><td>Ajouter un dossier</td></tr>
        <tr><td><b>Ctrl+F</b></td><td>Barre de recherche</td></tr>
        <tr><td><b>F5</b></td><td>Rescanner tous les dossiers</td></tr>
        <tr><td><b>Ctrl+R</b></td><td>Radio intelligente</td></tr>
        <tr><td><b>Ctrl+V</b></td><td>Visualiseur audio</td></tr>
        <tr><td><b>Ctrl+I</b></td><td>Statistiques</td></tr>
        <tr><td><b>Ctrl+,</b></td><td>Paramètres</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Quitter</td></tr>
        <tr><td><b>F1</b></td><td>Cette aide</td></tr>
        </table>
        """


class StatsDialog(QDialog):
    """Comprehensive library statistics dialog."""

    LOSSLESS_FORMATS = {'FLAC', 'ALAC', 'WAV', 'AIFF', 'APE', 'WV', 'TTA', 'DSF', 'DFF'}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T('stats_title'))
        self.setMinimumSize(650, 550)

        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_stats_html())
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def _build_stats_html(self):
        """Build complete statistics HTML."""
        import html as html_mod
        esc = html_mod.escape
        stats = db.get_library_stats()

        # Detailed queries
        format_rows = db.fetchall(
            "SELECT file_format, COUNT(*) as cnt, SUM(file_size) as sz, "
            "SUM(duration_ms) as dur FROM tracks GROUP BY file_format ORDER BY cnt DESC"
        )
        genre_rows = db.fetchall(
            "SELECT genre, COUNT(*) as cnt FROM tracks WHERE genre IS NOT NULL "
            "AND genre != '' GROUP BY genre ORDER BY cnt DESC LIMIT 15"
        )
        top_artists = db.fetchall(
            "SELECT a.name, COUNT(t.id) as cnt FROM tracks t "
            "JOIN artists a ON t.artist_id = a.id "
            "GROUP BY t.artist_id ORDER BY cnt DESC LIMIT 15"
        )
        top_played = db.fetchall(
            "SELECT t.title, a.name as artist_name, t.play_count FROM tracks t "
            "LEFT JOIN artists a ON t.artist_id = a.id "
            "WHERE t.play_count > 0 ORDER BY t.play_count DESC LIMIT 15"
        )
        year_range = db.fetchone(
            "SELECT MIN(year) as min_y, MAX(year) as max_y FROM tracks "
            "WHERE year IS NOT NULL AND year > 0"
        )
        avg_bitrate = db.fetchone(
            "SELECT AVG(bitrate) as avg_br FROM tracks WHERE bitrate > 0"
        )
        avg_duration = db.fetchone(
            "SELECT AVG(duration_ms) as avg_d FROM tracks WHERE duration_ms > 0"
        )
        scan_folders = db.fetchall(
            "SELECT path, last_scan FROM scan_folders ORDER BY path"
        )
        db_path = db._db_path or ''
        db_size = os.path.getsize(db_path) if db_path and os.path.exists(db_path) else 0

        # Quality breakdown
        lossless = 0
        lossy = 0
        hires = 0
        cd_quality = 0
        for row in format_rows:
            fmt = (row['file_format'] or '').upper()
            cnt = row['cnt']
            if fmt in self.LOSSLESS_FORMATS:
                lossless += cnt
            else:
                lossy += cnt

        hires_row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM tracks WHERE "
            "(sample_rate > 48000 OR bit_depth > 16) AND file_format IN "
            "('FLAC','ALAC','WAV','AIFF','DSF','DFF','WV')"
        )
        hires = hires_row['cnt'] if hires_row else 0

        cd_q_row = db.fetchone(
            "SELECT COUNT(*) as cnt FROM tracks WHERE "
            "sample_rate = 44100 AND bit_depth = 16 AND file_format IN "
            "('FLAC','ALAC','WAV','AIFF')"
        )
        cd_quality = cd_q_row['cnt'] if cd_q_row else 0

        total_tracks = stats.get('tracks', 0)
        total_dur = stats.get('total_duration_ms', 0)
        total_sz = stats.get('total_size', 0)

        # Duration formatting for large values
        def fmt_total_dur(ms):
            if not ms:
                return '0'
            hours = ms // 3_600_000
            mins = (ms % 3_600_000) // 60_000
            days = hours // 24
            if days > 0:
                rem_h = hours % 24
                return f"{days}d {rem_h}h {mins}min" if get_lang() == 'en' else f"{days}j {rem_h}h {mins}min"
            return f"{hours}h {mins}min"

        # Build HTML
        html = '<div style="font-family: Segoe UI, sans-serif; padding: 8px;">'
        html += f'<h2 style="color:#4fc3f7;">{T("stats_title")}</h2>'

        # --- Overview ---
        html += f'<h3 style="color:#81c784;">{T("stats_overview")}</h3>'
        html += '<table cellpadding="6" cellspacing="0" width="100%">'
        overview = [
            (T('stats_tracks'), f"{total_tracks:,}"),
            (T('stats_albums'), f"{stats.get('albums', 0):,}"),
            (T('stats_artists'), f"{stats.get('artists', 0):,}"),
            (T('stats_playlists'), f"{stats.get('playlists', 0):,}"),
            (T('stats_podcasts'), f"{stats.get('podcasts', 0):,}"),
            (T('stats_episodes'), f"{stats.get('episodes', 0):,}"),
            (T('stats_episodes_dl'), f"{stats.get('episodes_downloaded', 0):,}"),
            (T('stats_total_duration'), fmt_total_dur(total_dur)),
            (T('stats_total_size'), format_size(total_sz)),
            (T('stats_avg_duration'), format_duration(int(avg_duration['avg_d'])) if avg_duration and avg_duration['avg_d'] else '-'),
            (T('stats_avg_bitrate'), format_bitrate(int(avg_bitrate['avg_br'])) if avg_bitrate and avg_bitrate['avg_br'] else '-'),
            (T('stats_year_range'), f"{year_range['min_y']} – {year_range['max_y']}" if year_range and year_range['min_y'] else '-'),
            (T('stats_db_size'), format_size(db_size)),
        ]
        for i, (label, val) in enumerate(overview):
            bg = '#2a2a2a' if i % 2 == 0 else '#333'
            html += f'<tr style="background:{bg};"><td style="color:#aaa;">{label}</td>'
            html += f'<td style="color:#fff; text-align:right; font-weight:bold;">{val}</td></tr>'
        html += '</table>'

        # --- Audio Quality ---
        if total_tracks > 0:
            html += f'<h3 style="color:#81c784;">{T("stats_quality")}</h3>'
            html += '<table cellpadding="6" cellspacing="0" width="100%">'
            quality = [
                (T('stats_hires'), hires, '#e040fb'),
                (T('stats_cd_quality'), cd_quality, '#66bb6a'),
                (T('stats_lossless'), lossless, '#4fc3f7'),
                (T('stats_lossy'), lossy, '#ffa726'),
            ]
            for label, cnt, color in quality:
                pct = cnt * 100 / total_tracks if total_tracks else 0
                bar_w = int(pct * 3)  # max ~300px
                html += f'<tr><td style="color:#aaa; width:120px;">{label}</td>'
                html += f'<td><div style="background:{color}; width:{max(bar_w, 2)}px; '
                html += f'height:16px; border-radius:3px; display:inline-block;"></div> '
                html += f'<span style="color:#fff;">{cnt:,} ({pct:.1f}%)</span></td></tr>'
            html += '</table>'

        # --- Format Distribution ---
        if format_rows:
            html += f'<h3 style="color:#81c784;">{T("stats_formats")}</h3>'
            html += '<table cellpadding="4" cellspacing="0" width="100%">'
            html += '<tr style="color:#4fc3f7; font-weight:bold;">'
            html += '<td>Format</td><td style="text-align:right;">Count</td>'
            html += '<td style="text-align:right;">Size</td>'
            html += f'<td style="text-align:right;">{T("col_duration")}</td></tr>'
            for i, row in enumerate(format_rows):
                bg = '#2a2a2a' if i % 2 == 0 else '#333'
                fmt = row['file_format'] or '?'
                html += f'<tr style="background:{bg};">'
                html += f'<td style="color:#fff; font-weight:bold;">{esc(fmt)}</td>'
                html += f'<td style="color:#ccc; text-align:right;">{row["cnt"]:,}</td>'
                html += f'<td style="color:#ccc; text-align:right;">{format_size(row["sz"] or 0)}</td>'
                html += f'<td style="color:#ccc; text-align:right;">{fmt_total_dur(row["dur"] or 0)}</td></tr>'
            html += '</table>'

        # --- Top Artists ---
        if top_artists:
            html += f'<h3 style="color:#81c784;">{T("stats_top_artists")}</h3>'
            html += '<table cellpadding="4" cellspacing="0" width="100%">'
            max_cnt = top_artists[0]['cnt'] if top_artists else 1
            for i, row in enumerate(top_artists):
                bg = '#2a2a2a' if i % 2 == 0 else '#333'
                bar_w = int(row['cnt'] * 250 / max_cnt)
                html += f'<tr style="background:{bg};">'
                html += f'<td style="color:#fff; width:200px;">{esc(row["name"])}</td>'
                html += f'<td><div style="background:#4fc3f7; width:{max(bar_w, 2)}px; '
                html += f'height:14px; border-radius:3px; display:inline-block;"></div> '
                html += f'<span style="color:#aaa;">{row["cnt"]}</span></td></tr>'
            html += '</table>'

        # --- Top Genres ---
        if genre_rows:
            html += f'<h3 style="color:#81c784;">{T("stats_top_genres")}</h3>'
            html += '<table cellpadding="4" cellspacing="0" width="100%">'
            max_cnt = genre_rows[0]['cnt'] if genre_rows else 1
            for i, row in enumerate(genre_rows):
                bg = '#2a2a2a' if i % 2 == 0 else '#333'
                bar_w = int(row['cnt'] * 250 / max_cnt)
                html += f'<tr style="background:{bg};">'
                html += f'<td style="color:#fff; width:200px;">{esc(row["genre"])}</td>'
                html += f'<td><div style="background:#ffa726; width:{max(bar_w, 2)}px; '
                html += f'height:14px; border-radius:3px; display:inline-block;"></div> '
                html += f'<span style="color:#aaa;">{row["cnt"]}</span></td></tr>'
            html += '</table>'

        # --- Musical Periods ---
        period_rows = db.fetchall(
            "SELECT period, COUNT(*) as cnt FROM tracks WHERE period IS NOT NULL "
            "GROUP BY period ORDER BY "
            "CASE period "
            "WHEN 'Medieval' THEN 1 WHEN 'Renaissance' THEN 2 "
            "WHEN 'Baroque' THEN 3 WHEN 'Classical' THEN 4 "
            "WHEN 'Romantic' THEN 5 WHEN 'Modern' THEN 6 "
            "WHEN 'Contemporary' THEN 7 WHEN 'Recent' THEN 8 ELSE 9 END"
        )
        if period_rows:
            period_colors = {
                'Medieval': '#8d6e63', 'Renaissance': '#a1887f',
                'Baroque': '#ff8a65', 'Classical': '#4fc3f7',
                'Romantic': '#e040fb', 'Modern': '#66bb6a',
                'Contemporary': '#ffa726', 'Recent': '#ef5350',
            }
            html += f'<h3 style="color:#81c784;">{T("view_periods")}</h3>'
            html += '<table cellpadding="4" cellspacing="0" width="100%">'
            max_cnt = max(r['cnt'] for r in period_rows)
            for i, row in enumerate(period_rows):
                bg = '#2a2a2a' if i % 2 == 0 else '#333'
                color = period_colors.get(row['period'], '#4fc3f7')
                bar_w = int(row['cnt'] * 250 / max_cnt)
                html += f'<tr style="background:{bg};">'
                html += f'<td style="color:#fff; width:150px;">{esc(row["period"])}</td>'
                html += f'<td><div style="background:{color}; width:{max(bar_w, 2)}px; '
                html += f'height:14px; border-radius:3px; display:inline-block;"></div> '
                html += f'<span style="color:#aaa;">{row["cnt"]}</span></td></tr>'
            html += '</table>'

        # --- Most Played ---
        if top_played:
            html += f'<h3 style="color:#81c784;">{T("stats_top_played")}</h3>'
            html += '<table cellpadding="4" cellspacing="0" width="100%">'
            for i, row in enumerate(top_played):
                bg = '#2a2a2a' if i % 2 == 0 else '#333'
                html += f'<tr style="background:{bg};">'
                html += f'<td style="color:#fff;">{esc(row["title"])}</td>'
                html += f'<td style="color:#aaa;">{esc(row["artist_name"] or "")}</td>'
                html += f'<td style="color:#4fc3f7; text-align:right; font-weight:bold;">'
                html += f'{row["play_count"]}x</td></tr>'
            html += '</table>'

        # --- Scan Folders ---
        if scan_folders:
            html += f'<h3 style="color:#81c784;">{T("stats_scan_folders")}</h3>'
            html += '<table cellpadding="4" cellspacing="0" width="100%">'
            for i, row in enumerate(scan_folders):
                bg = '#2a2a2a' if i % 2 == 0 else '#333'
                last = str(row['last_scan'])[:19] if row['last_scan'] else '-'
                html += f'<tr style="background:{bg};">'
                html += f'<td style="color:#fff;">{esc(row["path"])}</td>'
                html += f'<td style="color:#aaa; text-align:right;">{last}</td></tr>'
            html += '</table>'

        html += '</div>'
        return html


# Musical eras for Smart Radio filtering
ERAS = [
    ('era_medieval',      None, 1399),
    ('era_renaissance',   1400, 1600),
    ('era_baroque',       1600, 1750),
    ('era_classical',     1750, 1820),
    ('era_romantic',      1820, 1900),
    ('era_modern',        1900, 1950),
    ('era_contemporary',  1950, 2000),
    ('era_recent',        2000, None),
]

LOSSLESS_FORMATS = {'FLAC', 'ALAC', 'WAV', 'AIFF', 'APE', 'WV', 'TTA', 'DSF', 'DFF', 'DSD'}
LOSSY_FORMATS = {'MP3', 'AAC', 'OGG', 'OPUS', 'WMA', 'M4A', 'MPC', 'SPX'}


class SmartRadioDialog(QDialog):
    """Smart Radio — play random tracks with combinable filters.

    Filters: genre, artist, composer, album, era/year range,
    audio quality, minimum rating, unplayed only.
    All filters combine with AND logic.
    """

    def __init__(self, player, parent=None):
        super().__init__(parent)
        self._player = player
        self.setWindowTitle(T('smart_radio_title'))
        self.setMinimumSize(520, 480)

        layout = QVBoxLayout(self)

        # --- Filters ---
        filters_box = QGroupBox(T('smart_radio'))
        form = QFormLayout(filters_box)

        # Genre
        self._genre_combo = QComboBox()
        self._genre_combo.addItem(T('filter_all'), '')
        genres = db.fetchall(
            "SELECT DISTINCT genre FROM tracks WHERE genre IS NOT NULL AND genre != '' ORDER BY genre"
        )
        for g in genres:
            self._genre_combo.addItem(g['genre'], g['genre'])
        self._genre_combo.currentIndexChanged.connect(self._update_count)
        form.addRow(T('filter_genre'), self._genre_combo)

        # Artist
        self._artist_combo = QComboBox()
        self._artist_combo.setEditable(True)
        self._artist_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._artist_combo.addItem(T('filter_all'), 0)
        artists = db.fetchall(
            "SELECT id, name FROM artists ORDER BY sort_name"
        )
        for a in artists:
            self._artist_combo.addItem(a['name'], a['id'])
        self._artist_combo.currentIndexChanged.connect(self._update_count)
        form.addRow(T('filter_artist'), self._artist_combo)

        # Composer
        self._composer_combo = QComboBox()
        self._composer_combo.setEditable(True)
        self._composer_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._composer_combo.addItem(T('filter_all'), '')
        composers = db.fetchall(
            "SELECT DISTINCT composer FROM tracks WHERE composer IS NOT NULL AND composer != '' ORDER BY composer"
        )
        for c in composers:
            self._composer_combo.addItem(c['composer'], c['composer'])
        self._composer_combo.currentIndexChanged.connect(self._update_count)
        form.addRow(T('filter_composer'), self._composer_combo)

        # Album
        self._album_combo = QComboBox()
        self._album_combo.setEditable(True)
        self._album_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._album_combo.addItem(T('filter_all'), 0)
        albums = db.fetchall(
            "SELECT al.id, al.title, a.name as artist_name FROM albums al "
            "LEFT JOIN artists a ON al.artist_id = a.id ORDER BY al.title"
        )
        for al in albums:
            label = f"{al['title']} — {al['artist_name']}" if al['artist_name'] else al['title']
            self._album_combo.addItem(label, al['id'])
        self._album_combo.currentIndexChanged.connect(self._update_count)
        form.addRow(T('filter_album'), self._album_combo)

        # Era
        self._era_combo = QComboBox()
        self._era_combo.addItem(T('filter_all_f'), '')
        for key, _, _ in ERAS:
            self._era_combo.addItem(T(key), key)
        self._era_combo.addItem(T('era_custom'), 'custom')
        self._era_combo.currentIndexChanged.connect(self._on_era_changed)
        form.addRow(T('filter_era'), self._era_combo)

        # Custom year range
        year_row = QHBoxLayout()
        self._year_from = QSpinBox()
        self._year_from.setRange(0, 2100)
        self._year_from.setSpecialValueText('—')
        self._year_from.setValue(0)
        self._year_from.valueChanged.connect(self._update_count)
        self._year_to = QSpinBox()
        self._year_to.setRange(0, 2100)
        self._year_to.setSpecialValueText('—')
        self._year_to.setValue(0)
        self._year_to.valueChanged.connect(self._update_count)
        year_row.addWidget(self._year_from)
        year_row.addWidget(QLabel(T('filter_year_to')))
        year_row.addWidget(self._year_to)
        self._year_widget = QWidget()
        self._year_widget.setLayout(year_row)
        self._year_widget.hide()
        form.addRow('', self._year_widget)

        # Quality
        self._quality_combo = QComboBox()
        self._quality_combo.addItem(T('quality_all'), '')
        self._quality_combo.addItem(T('quality_filter_hires'), 'hires')
        self._quality_combo.addItem(T('quality_filter_cd'), 'cd')
        self._quality_combo.addItem(T('quality_filter_lossless'), 'lossless')
        self._quality_combo.addItem(T('quality_filter_lossy'), 'lossy')
        self._quality_combo.currentIndexChanged.connect(self._update_count)
        form.addRow(T('filter_quality'), self._quality_combo)

        # Rating
        self._rating_combo = QComboBox()
        self._rating_combo.addItem(T('filter_all'), 0)
        for i in range(1, 6):
            self._rating_combo.addItem('★' * i, i)
        self._rating_combo.currentIndexChanged.connect(self._update_count)
        form.addRow(T('filter_rating_min'), self._rating_combo)

        # Unplayed only
        self._unplayed_check = QCheckBox(T('filter_unplayed'))
        self._unplayed_check.stateChanged.connect(self._update_count)
        form.addRow('', self._unplayed_check)

        layout.addWidget(filters_box)

        # --- Match count ---
        self._match_label = QLabel()
        self._match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._match_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 8px; "
            "background: #252530; border-radius: 6px; color: #5577aa;"
        )
        layout.addWidget(self._match_label)

        # --- Limit ---
        limit_row = QHBoxLayout()
        limit_row.addWidget(QLabel(T('smart_radio_limit')))
        self._limit_spin = QSpinBox()
        self._limit_spin.setRange(0, 10000)
        self._limit_spin.setSpecialValueText(T('smart_radio_unlimited'))
        self._limit_spin.setValue(0)
        self._limit_spin.setSuffix(' tracks')
        limit_row.addWidget(self._limit_spin)
        layout.addLayout(limit_row)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        self._btn_play = QPushButton(T('smart_radio_play_all'))
        self._btn_play.setStyleSheet(
            "font-size: 13px; font-weight: bold; padding: 8px 16px; "
            "background: #3c5078; border-radius: 6px; color: #fff;"
        )
        self._btn_play.clicked.connect(self._on_play)
        btn_row.addWidget(self._btn_play)

        btn_cancel = QPushButton(T('cancel') if 'cancel' in TX else 'Cancel')
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        # Initial count
        self._update_count()

    def _on_era_changed(self):
        """Show/hide custom year range based on era selection."""
        era_key = self._era_combo.currentData()
        if era_key == 'custom':
            self._year_widget.show()
        else:
            self._year_widget.hide()
        self._update_count()

    def _build_query(self):
        """Build SQL query and params from current filters."""
        conditions = []
        params = []

        # Genre
        genre = self._genre_combo.currentData()
        if genre:
            conditions.append("t.genre = ?")
            params.append(genre)

        # Artist
        artist_id = self._artist_combo.currentData()
        if artist_id:
            conditions.append("(t.artist_id = ? OR t.album_artist_id = ?)")
            params.extend([artist_id, artist_id])

        # Composer
        composer = self._composer_combo.currentData()
        if composer:
            conditions.append("t.composer = ?")
            params.append(composer)

        # Album
        album_id = self._album_combo.currentData()
        if album_id:
            conditions.append("t.album_id = ?")
            params.append(album_id)

        # Era / Year range — uses period column (classifier) or year fallback
        era_key = self._era_combo.currentData()
        era_to_period = {
            'era_medieval': 'Medieval', 'era_renaissance': 'Renaissance',
            'era_baroque': 'Baroque', 'era_classical': 'Classical',
            'era_romantic': 'Romantic', 'era_modern': 'Modern',
            'era_contemporary': 'Contemporary', 'era_recent': 'Recent',
        }
        if era_key == 'custom':
            y_from = self._year_from.value()
            y_to = self._year_to.value()
            if y_from > 0:
                conditions.append("t.year >= ?")
                params.append(y_from)
            if y_to > 0:
                conditions.append("t.year <= ?")
                params.append(y_to)
        elif era_key:
            period_name = era_to_period.get(era_key)
            if period_name:
                # Use stored period classification (more accurate than year alone)
                # Fall back to year range for unclassified tracks
                for key, start, end in ERAS:
                    if key == era_key:
                        year_conds = []
                        year_params = []
                        if start is not None:
                            year_conds.append("t.year >= ?")
                            year_params.append(start)
                        if end is not None:
                            year_conds.append("t.year <= ?")
                            year_params.append(end)
                        year_clause = (" AND ".join(year_conds)
                                       if year_conds else "1=1")
                        conditions.append(
                            f"(t.period = ? OR (t.period IS NULL AND {year_clause}))")
                        params.append(period_name)
                        params.extend(year_params)
                        break

        # Quality
        quality = self._quality_combo.currentData()
        if quality == 'hires':
            conditions.append(
                "(t.sample_rate > 48000 OR t.bit_depth > 16) AND "
                "t.file_format IN ('FLAC','ALAC','WAV','AIFF','APE','WV','DSF','DFF','DSD','TTA')"
            )
        elif quality == 'cd':
            conditions.append(
                "t.sample_rate = 44100 AND t.bit_depth = 16 AND "
                "t.file_format IN ('FLAC','ALAC','WAV','AIFF','APE','WV','TTA')"
            )
        elif quality == 'lossless':
            placeholders = ','.join('?' * len(LOSSLESS_FORMATS))
            conditions.append(f"t.file_format IN ({placeholders})")
            params.extend(LOSSLESS_FORMATS)
        elif quality == 'lossy':
            placeholders = ','.join('?' * len(LOSSY_FORMATS))
            conditions.append(f"t.file_format IN ({placeholders})")
            params.extend(LOSSY_FORMATS)

        # Rating
        min_rating = self._rating_combo.currentData()
        if min_rating:
            conditions.append("t.rating >= ?")
            params.append(min_rating)

        # Unplayed
        if self._unplayed_check.isChecked():
            conditions.append("(t.play_count = 0 OR t.play_count IS NULL)")

        where = " AND ".join(conditions) if conditions else "1=1"
        return where, params

    def _update_count(self):
        """Update match count label."""
        where, params = self._build_query()
        row = db.fetchone(
            f"SELECT COUNT(*) as cnt FROM tracks t WHERE {where}", tuple(params)
        )
        count = row['cnt'] if row else 0

        if count > 0:
            self._match_label.setText(T('smart_radio_match', count=count))
            self._match_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; padding: 8px; "
                "background: #252530; border-radius: 6px; color: #5577aa;"
            )
            self._btn_play.setEnabled(True)
        else:
            self._match_label.setText(T('smart_radio_no_match'))
            self._match_label.setStyleSheet(
                "font-size: 14px; font-weight: bold; padding: 8px; "
                "background: #252530; border-radius: 6px; color: #aa5555;"
            )
            self._btn_play.setEnabled(False)

    def _on_play(self):
        """Fetch matching tracks, shuffle, and play."""
        import random

        where, params = self._build_query()
        tracks = db.fetchall(
            f"SELECT t.*, a.name as artist_name, al.title as album_title "
            f"FROM tracks t "
            f"LEFT JOIN artists a ON t.artist_id = a.id "
            f"LEFT JOIN albums al ON t.album_id = al.id "
            f"WHERE {where} "
            f"ORDER BY RANDOM()",
            tuple(params)
        )

        if not tracks:
            return

        # Apply limit
        limit = self._limit_spin.value()
        if limit > 0:
            tracks = tracks[:limit]

        # Set queue and play
        self._player.set_queue(tracks, play_index=0)
        self._player.play()

        self.accept()
