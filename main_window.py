"""Main window for MusicOthèque."""
import os
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
    QFormLayout, QSpinBox, QCheckBox
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
from itunes_import import ITunesImportWorker
from metadata_fetch import MetadataFetchWorker

log = logging.getLogger(__name__)

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
        self._current_view = 'all_tracks'
        self._current_filter = None
        self._all_tracks_cache = []

        self._setup_ui()
        self._setup_menus()
        self._connect_signals()
        self._restore_state()
        self._refresh_library()

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

        self._item_artists = QTreeWidgetItem(lib_root, [T('view_artists')])
        self._item_artists.setData(0, Qt.ItemDataRole.UserRole, 'artists')

        self._item_albums = QTreeWidgetItem(lib_root, [T('view_albums')])
        self._item_albums.setData(0, Qt.ItemDataRole.UserRole, 'albums')

        self._item_genres = QTreeWidgetItem(lib_root, [T('view_genres')])
        self._item_genres.setData(0, Qt.ItemDataRole.UserRole, 'genres')

        # Playlists section
        self._pl_root = QTreeWidgetItem(self._sidebar, [T('view_playlists')])
        self._pl_root.setExpanded(True)
        font2 = self._pl_root.font(0)
        font2.setBold(True)
        self._pl_root.setFont(0, font2)

        self._refresh_playlists_sidebar()

    def _refresh_playlists_sidebar(self):
        """Refresh playlists in sidebar."""
        # Remove old playlist items
        while self._pl_root.childCount():
            self._pl_root.removeChild(self._pl_root.child(0))

        playlists = db.fetchall("SELECT id, name FROM playlists ORDER BY name")
        for pl in playlists:
            item = QTreeWidgetItem(self._pl_root, [pl['name']])
            item.setData(0, Qt.ItemDataRole.UserRole, f"playlist:{pl['id']}")

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
        self._seek_slider.setToolTip(T('play'))
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

        # Help menu
        help_menu = menubar.addMenu(T('menu_help'))

        act_about = help_menu.addAction(T('about'))
        act_about.triggered.connect(self._on_about)

        act_help = help_menu.addAction(T('help_title'))
        act_help.setShortcut(QKeySequence('F1'))
        act_help.triggered.connect(self._on_help)

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

        # Table double-click
        self._track_table.cellDoubleClicked.connect(self._on_track_double_click)

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
        self._stats_label.setText(
            f"{stats['tracks']} {T('view_tracks').lower()} | "
            f"{stats['albums']} {T('view_albums').lower()} | "
            f"{stats['artists']} {T('view_artists').lower()}"
        )
        self._refresh_playlists_sidebar()
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
        else:
            tracks = []

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

    def _populate_table(self, tracks):
        """Fill the track table with data."""
        self._track_table.setSortingEnabled(False)
        self._track_table.setRowCount(0)

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
        """Play track on double-click."""
        if row < 0 or row >= len(self._all_tracks_cache):
            return
        track = self._all_tracks_cache[row]
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

        # Cancel workers
        if self._scan_worker:
            self._scan_worker.cancel()
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.quit()
            self._scan_thread.wait(2000)

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
        <p>Add your music folders via <b>File → Add Music Folder</b> or <b>Ctrl+O</b>.
        MusicOthèque will scan the folders for audio files and extract metadata.</p>

        <h3>Supported Formats</h3>
        <p>MP3, FLAC, OGG, Opus, M4A, AAC, WMA, WAV, AIFF, ALAC, APE, WavPack,
        DSD (DSF/DFF), MKA, TTA, SPX, MPC, and more.</p>

        <h3>Library Navigation</h3>
        <ul>
        <li><b>All Tracks</b> — Browse all tracks in your library</li>
        <li><b>Artists</b> — Browse by artist</li>
        <li><b>Albums</b> — Browse by album</li>
        <li><b>Genres</b> — Browse by genre</li>
        <li><b>Playlists</b> — Manage your playlists</li>
        </ul>

        <h3>Playback Controls</h3>
        <ul>
        <li><b>Space</b> — Play/Pause</li>
        <li><b>Ctrl+Right</b> — Next track</li>
        <li><b>Ctrl+Left</b> — Previous track</li>
        <li><b>Ctrl+Up/Down</b> — Volume up/down</li>
        <li><b>Ctrl+.</b> — Stop</li>
        </ul>

        <h3>Search</h3>
        <p>Use <b>Ctrl+F</b> or the search bar to search by title, artist, or album.
        Full-text search with fuzzy matching is supported.</p>

        <h3>iTunes Import</h3>
        <p>Import your iTunes library via <b>File → Import iTunes Library</b>.
        Select your <code>iTunes Library.xml</code> file. Playlists, play counts,
        and ratings will be imported.</p>

        <h3>Online Metadata</h3>
        <p>Use <b>View → Fetch Metadata Online</b> to look up track information
        from MusicBrainz. Cover art will also be fetched when available.</p>

        <h3>Audio Quality Indicators</h3>
        <ul>
        <li><span style="color:#f8f">Hi-Res</span> — Sample rate > 48kHz or bit depth > 16</li>
        <li><span style="color:#8f8">CD Quality</span> — 44.1kHz / 16-bit</li>
        <li><span style="color:#8f8">Lossless</span> — FLAC, ALAC, WAV, etc.</li>
        <li><span style="color:#ff8">Lossy</span> — MP3, AAC, OGG, etc.</li>
        </ul>

        <h3>Keyboard Shortcuts</h3>
        <table>
        <tr><td><b>Ctrl+O</b></td><td>Add folder</td></tr>
        <tr><td><b>F5</b></td><td>Rescan library</td></tr>
        <tr><td><b>Ctrl+F</b></td><td>Search</td></tr>
        <tr><td><b>Ctrl+,</b></td><td>Settings</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>
        <tr><td><b>F1</b></td><td>Help</td></tr>
        </table>
        """

    def _help_fr(self):
        return """
        <h2>Aide MusicOthèque</h2>
        <h3>Démarrage</h3>
        <p>Ajoutez vos dossiers musicaux via <b>Fichier → Ajouter un dossier musical</b>
        ou <b>Ctrl+O</b>. MusicOthèque scannera les dossiers pour trouver les fichiers
        audio et extraire les métadonnées.</p>

        <h3>Formats Supportés</h3>
        <p>MP3, FLAC, OGG, Opus, M4A, AAC, WMA, WAV, AIFF, ALAC, APE, WavPack,
        DSD (DSF/DFF), MKA, TTA, SPX, MPC, et plus.</p>

        <h3>Navigation</h3>
        <ul>
        <li><b>Toutes les pistes</b> — Parcourir toutes les pistes</li>
        <li><b>Artistes</b> — Parcourir par artiste</li>
        <li><b>Albums</b> — Parcourir par album</li>
        <li><b>Genres</b> — Parcourir par genre</li>
        <li><b>Playlists</b> — Gérer vos playlists</li>
        </ul>

        <h3>Contrôles de Lecture</h3>
        <ul>
        <li><b>Espace</b> — Lecture/Pause</li>
        <li><b>Ctrl+Droite</b> — Piste suivante</li>
        <li><b>Ctrl+Gauche</b> — Piste précédente</li>
        <li><b>Ctrl+Haut/Bas</b> — Volume +/-</li>
        <li><b>Ctrl+.</b> — Arrêt</li>
        </ul>

        <h3>Recherche</h3>
        <p>Utilisez <b>Ctrl+F</b> ou la barre de recherche pour chercher par titre,
        artiste ou album. La recherche plein texte avec correspondance floue est supportée.</p>

        <h3>Import iTunes</h3>
        <p>Importez votre bibliothèque iTunes via <b>Fichier → Importer la bibliothèque iTunes</b>.
        Sélectionnez votre fichier <code>iTunes Library.xml</code>. Les playlists,
        compteurs de lecture et notes seront importés.</p>

        <h3>Métadonnées en Ligne</h3>
        <p>Utilisez <b>Affichage → Récupérer les métadonnées en ligne</b> pour
        rechercher les informations des pistes sur MusicBrainz. Les pochettes
        d'album seront aussi récupérées si disponibles.</p>

        <h3>Indicateurs Qualité Audio</h3>
        <ul>
        <li><span style="color:#f8f">Hi-Res</span> — Échantillonnage > 48kHz ou profondeur > 16 bits</li>
        <li><span style="color:#8f8">Qualité CD</span> — 44.1kHz / 16 bits</li>
        <li><span style="color:#8f8">Sans perte</span> — FLAC, ALAC, WAV, etc.</li>
        <li><span style="color:#ff8">Avec perte</span> — MP3, AAC, OGG, etc.</li>
        </ul>

        <h3>Raccourcis Clavier</h3>
        <table>
        <tr><td><b>Ctrl+O</b></td><td>Ajouter un dossier</td></tr>
        <tr><td><b>F5</b></td><td>Rescanner la bibliothèque</td></tr>
        <tr><td><b>Ctrl+F</b></td><td>Rechercher</td></tr>
        <tr><td><b>Ctrl+,</b></td><td>Paramètres</td></tr>
        <tr><td><b>Ctrl+Q</b></td><td>Quitter</td></tr>
        <tr><td><b>F1</b></td><td>Aide</td></tr>
        </table>
        """
