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
    QHeaderView, QLabel, QPushButton, QSlider, QLineEdit,
    QStatusBar, QMenuBar, QMenu, QToolBar, QFileDialog,
    QMessageBox, QProgressBar, QAbstractItemView, QComboBox,
    QStyle, QApplication, QSizePolicy, QFrame, QStackedWidget,
    QDialog, QTextBrowser, QDialogButtonBox, QGroupBox,
    QFormLayout, QSpinBox, QCheckBox, QInputDialog
)
from PyQt6.QtCore import (
    Qt, QThread, QTimer, QSize, pyqtSignal, QSettings
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QPixmap, QImage, QIcon, QFont,
    QPalette, QColor
)

import database as db
from i18n import T, get_lang, set_lang, TX
from player import AudioPlayer, PlayerState, RepeatMode, ShuffleMode
from scanner import ScanWorker
from itunes_import import ITunesImportWorker, ITunesPodcastImportWorker
from metadata_fetch import MetadataFetchWorker
from backup_manager import backup_database, restore_database, list_backups
from podcast_manager import PodcastDownloadWorker, parse_rss_feed, search_podcasts

log = logging.getLogger(__name__)

# Column definitions for podcast episodes table
EPISODE_COLUMNS = [
    ('col_title', 'title', 300),
    ('col_podcast', 'podcast_title', 180),
    ('col_published', 'published_at', 100),
    ('col_duration', 'duration_ms', 70),
    ('col_listened', 'listened', 60),
    ('col_downloaded', 'file_path', 60),
]

# Column definitions for track table
COLUMNS = [
    ('col_track_num', 'track_number', 40),
    ('col_title', 'title', 280),
    ('col_artist', 'artist_name', 180),
    ('col_album', 'album_title', 180),
    ('col_duration', 'duration_ms', 70),
    ('col_year', 'year', 55),
    ('col_genre', 'genre', 100),
    ('col_format', 'file_format', 55),
    ('col_bitrate', 'bitrate', 70),
    ('col_sample_rate', 'sample_rate', 80),
    ('col_bit_depth', 'bit_depth', 55),
    ('col_play_count', 'play_count', 50),
    ('col_rating', 'rating', 50),
]


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


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self._settings = QSettings('MusicOtheque', 'MusicOtheque')
        self._player = AudioPlayer(self)
        self._scan_thread = None
        self._scan_worker = None
        self._import_thread = None
        self._fetch_thread = None
        self._podcast_thread = None
        self._podcast_import_thread = None
        self._harmonize_thread = None
        self._cd_thread = None
        self._current_view = 'all_tracks'
        self._current_filter = None
        self._all_tracks_cache = []
        self._content_mode = 'music'  # 'music' or 'podcasts'

        self._setup_ui()
        self._setup_menus()
        self._connect_signals()
        self._restore_state()
        self._refresh_library()

        # Auto-backup timer (every 30 minutes)
        self._backup_timer = QTimer(self)
        self._backup_timer.timeout.connect(self._auto_backup)
        self._backup_timer.start(30 * 60 * 1000)

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

        # Track table
        self._track_table = QTableWidget()
        self._track_table.setColumnCount(len(COLUMNS))
        headers = [T(col[0]) for col in COLUMNS]
        self._track_table.setHorizontalHeaderLabels(headers)
        self._track_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._track_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._track_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._track_table.setAlternatingRowColors(True)
        self._track_table.setSortingEnabled(True)
        self._track_table.verticalHeader().setVisible(False)
        self._track_table.verticalHeader().setDefaultSectionSize(26)
        self._track_table.setShowGrid(False)

        # Column widths
        header = self._track_table.horizontalHeader()
        for i, (_, _, w) in enumerate(COLUMNS):
            self._track_table.setColumnWidth(i, w)
        header.setStretchLastSection(False)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Title stretches

        content_layout.addWidget(self._track_table, 1)

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(content)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([200, 800])

        main_layout.addWidget(self._splitter, 1)

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

        # Quality badge
        self._quality_label = QLabel('')
        self._quality_label.setStyleSheet(
            "font-size: 9px; padding: 2px 6px; border-radius: 3px; "
            "background: #2a5a2a; color: #8f8;"
        )
        self._quality_label.hide()
        vol_layout.addWidget(self._quality_label)

        layout.addLayout(vol_layout)

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
        self._track_table.cellDoubleClicked.connect(self._on_track_double_click)
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
                SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
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
        elif view == 'artist' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.artist_id = ? OR t.album_artist_id = ?
                ORDER BY al.year, t.disc_number, t.track_number
            """, (filter_value, filter_value))
        elif view == 'album' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.album_id = ?
                ORDER BY t.disc_number, t.track_number
            """, (filter_value,))
        elif view == 'genre' and filter_value:
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
                FROM tracks t
                LEFT JOIN artists a ON t.artist_id = a.id
                LEFT JOIN albums al ON t.album_id = al.id
                WHERE t.genre = ?
                ORDER BY a.name, al.year, t.disc_number, t.track_number
            """, (filter_value,))
        elif view.startswith('playlist:'):
            pl_id = int(view.split(':')[1])
            tracks = db.fetchall("""
                SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
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
            pod_id = int(view.split(':')[1])
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
        """Fill table with podcast episodes."""
        self._track_table.setSortingEnabled(False)
        self._track_table.setRowCount(0)
        self._track_table.setColumnCount(len(EPISODE_COLUMNS))
        self._track_table.setHorizontalHeaderLabels([T(c[0]) for c in EPISODE_COLUMNS])
        for i, (_, _, w) in enumerate(EPISODE_COLUMNS):
            self._track_table.setColumnWidth(i, w)
        header = self._track_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        self._all_tracks_cache = []
        for row_data in episodes:
            ep = dict(row_data)
            ep['_is_episode'] = True
            self._all_tracks_cache.append(ep)

        self._track_table.setRowCount(len(self._all_tracks_cache))
        for row, ep in enumerate(self._all_tracks_cache):
            for col, (_, key, _) in enumerate(EPISODE_COLUMNS):
                val = ep.get(key, '')
                if key == 'duration_ms':
                    text = format_duration(val)
                elif key == 'published_at':
                    text = str(val)[:10] if val else ''
                elif key == 'listened':
                    text = '✓' if val else ''
                elif key == 'file_path':
                    text = '💾' if val else ''
                else:
                    text = str(val) if val else ''

                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, ep)
                if key in ('duration_ms', 'listened', 'file_path', 'published_at'):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                self._track_table.setItem(row, col, item)

        self._track_table.setSortingEnabled(True)
        self._update_view_stats(self._all_tracks_cache)

    def _update_view_stats(self, items):
        """Update status bar with totals for current view."""
        total_duration = sum(t.get('duration_ms', 0) or 0 for t in items)
        total_size = sum(t.get('file_size', 0) or 0 for t in items)
        count = len(items)
        parts = [T('total_tracks', count=count)]
        if total_duration > 0:
            parts.append(T('total_duration', duration=format_duration(total_duration)))
        if total_size > 0:
            parts.append(T('total_size', size=format_size(total_size)))
        self._status_bar.showMessage(' | '.join(parts))

    def _populate_table(self, tracks):
        """Fill the track table with data."""
        self._track_table.setSortingEnabled(False)
        self._track_table.setRowCount(0)

        # Restore music columns if coming from podcast view
        if self._track_table.columnCount() != len(COLUMNS):
            self._track_table.setColumnCount(len(COLUMNS))
            self._track_table.setHorizontalHeaderLabels([T(c[0]) for c in COLUMNS])
            for i, (_, _, w) in enumerate(COLUMNS):
                self._track_table.setColumnWidth(i, w)
            header = self._track_table.horizontalHeader()
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        self._all_tracks_cache = []
        for row_data in tracks:
            track = dict(row_data)
            self._all_tracks_cache.append(track)

        self._track_table.setRowCount(len(self._all_tracks_cache))

        for row, track in enumerate(self._all_tracks_cache):
            for col, (_, key, _) in enumerate(COLUMNS):
                val = track.get(key, '')

                if key == 'duration_ms':
                    text = format_duration(val)
                elif key == 'bitrate':
                    text = format_bitrate(val)
                elif key == 'sample_rate':
                    text = format_sample_rate(val)
                elif key == 'bit_depth':
                    text = f"{val}-bit" if val else ''
                elif key == 'track_number':
                    text = str(val) if val else ''
                elif key == 'year':
                    text = str(val) if val else ''
                elif key == 'play_count':
                    text = str(val) if val else ''
                elif key == 'rating':
                    text = '★' * val if val else ''
                else:
                    text = str(val) if val else ''

                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, track)

                # Right-align numeric columns
                if key in ('track_number', 'duration_ms', 'bitrate',
                           'sample_rate', 'bit_depth', 'play_count', 'year'):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )

                self._track_table.setItem(row, col, item)

        self._track_table.setSortingEnabled(True)
        self._update_view_stats(self._all_tracks_cache)

    # --- Event handlers ---

    def _on_sidebar_changed(self, current, previous):
        """Handle sidebar selection change."""
        if not current:
            return
        view_id = current.data(0, Qt.ItemDataRole.UserRole)
        if not view_id:
            return

        if ':' in str(view_id) and not view_id.startswith('playlist:'):
            parts = view_id.split(':', 1)
            self._load_view(parts[0], parts[1] if len(parts) > 1 else None)
        elif view_id.startswith('playlist:'):
            self._load_view(view_id)
        else:
            self._load_view(view_id)

    def _on_track_double_click(self, row, col):
        """Play track or episode on double-click."""
        if row < 0 or row >= len(self._all_tracks_cache):
            return
        track = self._all_tracks_cache[row]

        # For podcast episodes, use file_path if downloaded
        if track.get('_is_episode'):
            fp = track.get('file_path')
            if not fp:
                self._status_bar.showMessage(T('podcast_download') + '...', 3000)
                return
            # Play episode as a track
            ep_track = {
                'file_path': fp,
                'title': track.get('title', ''),
                'artist_name': track.get('podcast_title', ''),
                'album_title': 'Podcast',
                'duration_ms': track.get('duration_ms', 0),
            }
            self._player.play_track(ep_track)
            # Mark as listened
            if track.get('id'):
                db.execute(
                    "UPDATE podcast_episodes SET listened = 1, listened_at = datetime('now') WHERE id = ?",
                    (track['id'],), commit=True
                )
            return

        self._player.play_track(track, queue=self._all_tracks_cache, index=row)

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
        if not self._seek_slider.isSliderDown():
            self._seek_slider.setValue(pos)
        self._position_label.setText(format_duration(pos))

    def _on_duration(self, dur):
        """Update duration display."""
        self._seek_slider.setRange(0, dur)
        self._duration_label.setText(format_duration(dur))

    def _on_track_changed(self, track):
        """Update UI for new track."""
        self._track_title_label.setText(track.get('title', ''))
        self._track_artist_label.setText(track.get('artist_name', track.get('artist', '')))

        # Cover art
        cover = track.get('cover_data')
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

        # Update play count in DB
        db.execute(
            "UPDATE tracks SET play_count = play_count + 1, last_played = datetime('now') WHERE file_path = ?",
            (track.get('file_path', ''),), commit=True
        )

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

    def _start_scan(self, folders, full_rescan=False):
        """Launch scan worker in thread."""
        if self._scan_thread and self._scan_thread.isRunning():
            self._status_bar.showMessage(T('scanning'), 2000)
            return

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
        selected = self._track_table.selectedItems()
        track_ids = set()
        for item in selected:
            track = item.data(Qt.ItemDataRole.UserRole)
            if track and isinstance(track, dict) and 'id' in track:
                track_ids.add(track['id'])

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
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_library()

    def _on_about(self):
        """Show about dialog."""
        try:
            version_file = Path(__file__).parent / 'VERSION'
            version = version_file.read_text().strip() if version_file.exists() else '?'
        except Exception:
            version = '?'

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
        """Show context menu for track table."""
        row = self._track_table.rowAt(pos.y())
        if row < 0 or row >= len(self._all_tracks_cache):
            return

        track = self._all_tracks_cache[row]
        menu = QMenu(self)

        act_play = menu.addAction(T('play_now'))
        act_play.triggered.connect(
            lambda: self._player.play_track(track, queue=self._all_tracks_cache, index=row)
        )

        act_next = menu.addAction(T('play_next'))
        act_next.triggered.connect(lambda: self._player.add_to_queue(track))

        act_queue = menu.addAction(T('add_to_queue'))
        act_queue.triggered.connect(lambda: self._player.add_to_queue(track))

        menu.addSeparator()

        # Add to playlist submenu
        pl_menu = menu.addMenu(T('add_to_playlist'))
        playlists = db.fetchall("SELECT id, name FROM playlists ORDER BY name")
        for pl in playlists:
            act = pl_menu.addAction(pl['name'])
            pl_id = pl['id']
            track_id = track.get('id')
            act.triggered.connect(
                lambda checked, pid=pl_id, tid=track_id: self._add_track_to_playlist(pid, tid)
            )
        if playlists:
            pl_menu.addSeparator()
        act_new_pl = pl_menu.addAction(T('new_playlist'))
        act_new_pl.triggered.connect(lambda: self._create_playlist_with_track(track))

        menu.addSeparator()

        act_info = menu.addAction(T('track_info'))
        act_info.triggered.connect(lambda: self._show_track_info(track))

        act_explorer = menu.addAction(T('show_in_explorer'))
        act_explorer.triggered.connect(lambda: self._show_in_explorer(track))

        menu.exec(self._track_table.viewport().mapToGlobal(pos))

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
        """Show track information dialog."""
        import html as html_mod
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
            f"<b>Path:</b> {esc(str(track.get('file_path', '')))}",
        ]
        QMessageBox.information(self, T('track_info'), '<br>'.join(info_parts))

    def _show_in_explorer(self, track):
        """Open file explorer at the track's location."""
        fp = track.get('file_path', '')
        if not fp:
            return
        folder = os.path.dirname(fp)
        if platform.system() == 'Windows':
            subprocess.Popen(['explorer', '/select,', os.path.normpath(fp)])
        elif platform.system() == 'Darwin':
            subprocess.Popen(['open', '-R', fp])
        else:
            subprocess.Popen(['xdg-open', folder])

    # --- Tools actions ---

    def _auto_backup(self):
        """Periodic auto-backup."""
        from musicotheque import DB_PATH, BACKUP_DIR
        backup_database(str(DB_PATH), str(BACKUP_DIR), label='auto')
        log.debug("Auto-backup completed")

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
            self._status_bar.showMessage("No backups found", 3000)
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
        """Check for broken file paths."""
        broken = db.find_broken_paths()
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
                resp = requests.get(
                    'https://api.github.com/repos/ARP273-ROSE/musicotheque/releases/latest',
                    timeout=5, headers={'User-Agent': 'MusicOtheque/2.0.0'}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    remote = data.get('tag_name', '').lstrip('v')
                    version_file = Path(__file__).parent / 'VERSION'
                    current = version_file.read_text().strip() if version_file.exists() else '?'
                    if remote and remote != current:
                        # Use QTimer to show dialog on main thread
                        QTimer.singleShot(0, lambda: QMessageBox.information(
                            self, T('check_updates'),
                            f"Update available: {current} -> {remote}"
                        ))
                    else:
                        QTimer.singleShot(0, lambda: self._status_bar.showMessage("Up to date", 3000))
                else:
                    QTimer.singleShot(0, lambda: self._status_bar.showMessage("No releases found", 3000))
            except Exception as e:
                QTimer.singleShot(0, lambda: self._status_bar.showMessage(f"Update check failed: {e}", 3000))

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

        try:
            feed_data = parse_rss_feed(url)
            if not feed_data:
                self._status_bar.showMessage(T('error'), 5000)
                return

            # Create podcast in DB
            podcast_id = db.get_or_create_podcast(
                feed_data['title'], feed_url=url, author=feed_data.get('author')
            )

            # Update podcast metadata
            db.execute("""
                UPDATE podcasts SET
                    description = ?, category = ?, language = ?,
                    image_url = ?, last_checked = datetime('now')
                WHERE id = ?
            """, (
                feed_data.get('description'), feed_data.get('category'),
                feed_data.get('language'), feed_data.get('image_url'),
                podcast_id
            ), commit=True)

            # Insert episodes
            for ep in feed_data.get('episodes', []):
                duration_ms = ep.get('duration_seconds', 0) * 1000
                db.execute("""
                    INSERT OR IGNORE INTO podcast_episodes(
                        podcast_id, title, description, guid,
                        published_at, duration_ms, file_url, file_size
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    podcast_id, ep.get('title'), ep.get('description'),
                    ep.get('guid'), ep.get('published'),
                    duration_ms, ep.get('audio_url'),
                    ep.get('file_size', 0)
                ), commit=False)
            db.commit()

            self._status_bar.showMessage(
                f"Subscribed: {feed_data['title']} ({len(feed_data.get('episodes', []))} episodes)",
                5000
            )
            self._refresh_library()

        except Exception as e:
            log.exception("Podcast subscribe error")
            self._status_bar.showMessage(f"Error: {e}", 5000)

    def _on_podcast_search(self):
        """Search podcasts online (iTunes directory)."""
        query, ok = QInputDialog.getText(
            self, T('podcast_search'), T('search')
        )
        if not ok or not query:
            return

        try:
            results = search_podcasts(query)
            if not results:
                self._status_bar.showMessage(T('no_results'), 3000)
                return

            # Show results in a dialog
            items = [f"{r['name']} — {r['author']}" for r in results]
            item, ok = QInputDialog.getItem(
                self, T('podcast_search'),
                f"{len(results)} results:", items, 0, False
            )
            if ok:
                idx = items.index(item)
                feed_url = results[idx].get('feed_url')
                if feed_url:
                    # Subscribe automatically
                    self._on_podcast_subscribe_url(feed_url)
        except Exception as e:
            self._status_bar.showMessage(f"Search error: {e}", 5000)

    def _on_podcast_subscribe_url(self, url):
        """Subscribe to podcast by URL directly."""
        try:
            feed_data = parse_rss_feed(url)
            if feed_data:
                podcast_id = db.get_or_create_podcast(
                    feed_data['title'], feed_url=url,
                    author=feed_data.get('author')
                )
                for ep in feed_data.get('episodes', []):
                    duration_ms = ep.get('duration_seconds', 0) * 1000
                    db.execute("""
                        INSERT OR IGNORE INTO podcast_episodes(
                            podcast_id, title, description, guid,
                            published_at, duration_ms, file_url, file_size
                        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        podcast_id, ep.get('title'), ep.get('description'),
                        ep.get('guid'), ep.get('published'),
                        duration_ms, ep.get('audio_url'),
                        ep.get('file_size', 0)
                    ), commit=False)
                db.commit()
                self._status_bar.showMessage(
                    f"Subscribed: {feed_data['title']}", 5000
                )
                self._refresh_library()
        except Exception as e:
            self._status_bar.showMessage(f"Error: {e}", 5000)

    def _on_podcast_refresh(self):
        """Refresh all podcast feeds (in background thread)."""
        podcasts = db.fetchall("SELECT id, feed_url, title FROM podcasts WHERE feed_url IS NOT NULL")
        if not podcasts:
            self._status_bar.showMessage("No podcast subscriptions", 3000)
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
            self._status_bar.showMessage("CD ripper module not available", 3000)
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
            self._status_bar.showMessage("Harmonizer module not available", 3000)
            return

        # Preview first
        reply = QMessageBox.question(
            self, T('harmonize'),
            T('harmonize_preview') + '?\n' + T('harmonize_tip'),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        worker = HarmonizeWorker(preview=True)
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
            self._status_bar.showMessage("No changes needed", 5000)
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

        worker = HarmonizeWorker(preview=False)
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

        # Stop playback
        self._player.stop()
        self._backup_timer.stop()

        # Cancel all workers
        for worker_attr in ('_scan_worker', '_import_worker', '_fetch_worker',
                            '_harmonize_worker', '_cd_worker',
                            '_podcast_import_worker', '_podcast_refresh_worker'):
            worker = getattr(self, worker_attr, None)
            if worker and hasattr(worker, 'cancel'):
                worker.cancel()

        # Wait for all threads to finish
        for thread_attr in ('_scan_thread', '_import_thread', '_fetch_thread',
                            '_harmonize_thread', '_cd_thread',
                            '_podcast_thread', '_podcast_import_thread'):
            thread = getattr(self, thread_attr, None)
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(2000)

        # Backup on exit
        try:
            from musicotheque import DB_PATH, BACKUP_DIR
            backup_database(str(DB_PATH), str(BACKUP_DIR), label='exit')
        except Exception:
            pass

        db.close_connection()
        event.accept()


class SettingsDialog(QDialog):
    """Settings dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(T('settings'))
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        # Scan folders
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

        # Language
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
        lang = self._lang_combo.currentData()
        set_lang(lang)
        db.execute("INSERT OR REPLACE INTO config(key, value) VALUES('lang', ?)",
                   (lang,), commit=True)
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
        The player supports gapless playback with pre-buffering near end of track.</p>

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
        </ul>

        <h3>Audio Quality Indicators</h3>
        <ul>
        <li><span style="color:#f8f"><b>Hi-Res</b></span> — Sample rate > 48kHz or bit depth > 16-bit</li>
        <li><span style="color:#8f8"><b>CD Quality</b></span> — 44.1kHz / 16-bit lossless</li>
        <li><span style="color:#8f8"><b>Lossless</b></span> — FLAC, ALAC, WAV, AIFF, APE, WavPack</li>
        <li><span style="color:#ff8"><b>Lossy</b></span> — MP3, AAC, OGG, Opus, WMA</li>
        </ul>

        <h3>Data Safety</h3>
        <p>Auto-backup every 30 minutes and on application exit. Backup rotation keeps
        5 recent daily backups + 4 weekly. All database writes use SQLite WAL mode with
        thread-safe locking. Atomic saves (write-tmp-then-rename) prevent corruption.</p>

        <h3>Cross-Platform</h3>
        <p>Works on Windows, Linux, and macOS. Data is stored in the OS-appropriate
        location (APPDATA / XDG_DATA_HOME / Library). Use <b>Tools → Relocate Paths</b>
        when opening the same library on a different OS.</p>

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
        de lecture. Le lecteur supporte la lecture sans coupure avec pré-chargement.</p>

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
        </ul>

        <h3>Indicateurs Qualité Audio</h3>
        <ul>
        <li><span style="color:#f8f"><b>Hi-Res</b></span> — Échantillonnage > 48kHz ou profondeur > 16 bits</li>
        <li><span style="color:#8f8"><b>Qualité CD</b></span> — 44.1kHz / 16 bits sans perte</li>
        <li><span style="color:#8f8"><b>Sans perte</b></span> — FLAC, ALAC, WAV, AIFF, APE, WavPack</li>
        <li><span style="color:#ff8"><b>Avec perte</b></span> — MP3, AAC, OGG, Opus, WMA</li>
        </ul>

        <h3>Sécurité des Données</h3>
        <p>Sauvegarde automatique toutes les 30 minutes et à la fermeture. La rotation
        garde 5 sauvegardes quotidiennes récentes + 4 hebdomadaires. Toutes les écritures
        utilisent SQLite WAL avec verrouillage thread-safe. Sauvegardes atomiques
        (écriture-tmp-puis-renommage) pour éviter la corruption.</p>

        <h3>Multi-Plateforme</h3>
        <p>Fonctionne sur Windows, Linux et macOS. Les données sont stockées dans le
        répertoire approprié au système (APPDATA / XDG_DATA_HOME / Library). Utilisez
        <b>Outils → Déplacer les chemins</b> pour ouvrir la même bibliothèque sur un autre OS.</p>

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
