"""MusicOthèque — Music Library & HiFi Player.

Entry point with crash handling, logging, hardware detection, and auto-update.
"""
import sys
import os
import json
import logging
import logging.handlers
import platform
import traceback
import time
from pathlib import Path

# Force FFmpeg backend for QMediaPlayer (required for HLS streams like BBC Radio 3)
os.environ.setdefault('QT_MEDIA_BACKEND', 'ffmpeg')

VERSION = '3.3.1'
APP_NAME = 'MusicOthèque'
APP_DIR = Path(__file__).parent


def _get_data_dir():
    """Data directory = project directory (portable across PCs/NAS/Linux)."""
    return APP_DIR


DATA_DIR = _get_data_dir()
DB_PATH = DATA_DIR / 'musicotheque.db'
BACKUP_DIR = DATA_DIR / 'backups'
LOG_PATH = DATA_DIR / 'musicotheque.log'
CRASH_PATH = DATA_DIR / '_crash_report.json'
ERROR_LOG = DATA_DIR / '_error.log'

# Ensure dirs exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging():
    """Configure rotating log file + console output."""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
    root.addHandler(console)

    # File handler (rotating, 500KB max, 3 backups)
    try:
        fh = logging.handlers.RotatingFileHandler(
            str(LOG_PATH), maxBytes=500_000, backupCount=3,
            encoding='utf-8'
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s %(name)s %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        root.addHandler(fh)
    except Exception as e:
        print(f"Warning: Could not create log file: {e}")


def _anonymize_path(text):
    """Replace user home directory with ~ for anonymous crash/bug reports."""
    if not text:
        return text
    home = str(Path.home())
    text = text.replace(home.replace("\\", "/"), "~")
    text = text.replace(home, "~")
    if sys.platform == "win32":
        text = text.replace(home.lower(), "~")
    return text


def crash_handler(exc_type, exc_value, exc_tb):
    """Save crash report and show error dialog."""
    tb_text = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical("CRASH:\n%s", tb_text)

    report = {
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'version': VERSION,
        'python': platform.python_version(),
        'os': platform.system(),
        'arch': platform.machine(),
        'traceback': _anonymize_path(tb_text),
    }

    try:
        CRASH_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass

    # Let PyQt show the error
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def detect_hardware():
    """Detect hardware capabilities for performance tuning."""
    import multiprocessing
    hw = {
        'cpu_cores_physical': 0,
        'cpu_cores_logical': multiprocessing.cpu_count() or 4,
        'ram_gb': 0,
        'storage_type': 'unknown',
    }

    try:
        # Physical cores
        if platform.system() == 'Windows':
            import subprocess
            result = subprocess.run(
                ['wmic', 'cpu', 'get', 'NumberOfCores', '/value'],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'NumberOfCores' in line:
                    hw['cpu_cores_physical'] = int(line.split('=')[1].strip())
        else:
            try:
                hw['cpu_cores_physical'] = len(os.sched_getaffinity(0))
            except AttributeError:
                hw['cpu_cores_physical'] = hw['cpu_cores_logical'] // 2

        # RAM
        if platform.system() == 'Windows':
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            hw['ram_gb'] = round(mem.ullTotalPhys / (1024**3), 1)
        else:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        kb = int(line.split()[1])
                        hw['ram_gb'] = round(kb / (1024**2), 1)
                        break
    except Exception as e:
        logging.debug("Hardware detection partial: %s", e)

    if not hw['cpu_cores_physical']:
        hw['cpu_cores_physical'] = max(1, hw['cpu_cores_logical'] // 2)

    logging.info("Hardware: %d/%d cores, %.1f GB RAM",
                 hw['cpu_cores_physical'], hw['cpu_cores_logical'], hw['ram_gb'])
    return hw


def check_crash_report():
    """Check for crash report from previous session."""
    if not CRASH_PATH.exists():
        return

    try:
        from PyQt6.QtWidgets import QMessageBox
        report = json.loads(CRASH_PATH.read_text(encoding='utf-8'))
        msg = QMessageBox()
        msg.setWindowTitle(APP_NAME)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(
            f"MusicOthèque crashed during the previous session.\n"
            f"Version: {report.get('version', '?')}\n"
            f"Time: {report.get('timestamp', '?')}"
        )
        msg.setDetailedText(report.get('traceback', ''))
        msg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Discard
        )
        msg.button(QMessageBox.StandardButton.Discard).setText('Delete report')
        msg.exec()
        CRASH_PATH.unlink(missing_ok=True)
    except Exception:
        CRASH_PATH.unlink(missing_ok=True)


def migrate_from_appdata():
    """Check for a previous database in %APPDATA%/MusicOtheque/ and offer to migrate.

    This handles the transition from per-user data storage to portable
    project-directory storage (required for multi-PC/NAS access).
    """
    import shutil
    import sqlite3

    # Only look for old data on Windows (Linux/macOS never used this path)
    if platform.system() != 'Windows':
        return False

    appdata = os.environ.get('APPDATA', '')
    if not appdata:
        return False

    old_dir = Path(appdata) / 'MusicOtheque'
    old_db = old_dir / 'musicotheque.db'

    # Skip if old DB doesn't exist or if current DB already has data
    if not old_db.exists():
        return False
    if DB_PATH.exists() and DB_PATH.stat().st_size > 4096:
        # Current DB already has data, skip migration
        return False

    # Check if old DB has actual content
    try:
        conn = sqlite3.connect(str(old_db), timeout=5)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT COUNT(*) as cnt FROM tracks").fetchone()
        track_count = row['cnt'] if row else 0
        row = conn.execute("SELECT COUNT(*) as cnt FROM playlists").fetchone()
        playlist_count = row['cnt'] if row else 0
        conn.close()
    except Exception as e:
        logging.debug("Could not read old DB at %s: %s", old_db, e)
        return False

    if track_count == 0:
        return False

    # Ask user
    from PyQt6.QtWidgets import QMessageBox
    from i18n import T

    msg = QMessageBox()
    msg.setWindowTitle(T('migrate_title'))
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(T('migrate_message', path=str(old_dir),
                  tracks=track_count, playlists=playlist_count))
    msg.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
    )
    msg.setDefaultButton(QMessageBox.StandardButton.Yes)

    if msg.exec() != QMessageBox.StandardButton.Yes:
        return False

    # Copy the database (and WAL/SHM if present)
    try:
        shutil.copy2(str(old_db), str(DB_PATH))
        for ext in ('.db-wal', '.db-shm'):
            old_extra = old_dir / f'musicotheque{ext}'
            if old_extra.exists():
                shutil.copy2(str(old_extra), str(DATA_DIR / f'musicotheque{ext}'))

        # Also copy backups if they exist
        old_backups = old_dir / 'backups'
        if old_backups.exists():
            for bf in old_backups.iterdir():
                if bf.suffix == '.db':
                    shutil.copy2(str(bf), str(BACKUP_DIR / bf.name))

        logging.info("Migrated database from %s (%d tracks)", old_dir, track_count)
        QMessageBox.information(
            None, APP_NAME,
            T('migrate_success', tracks=track_count)
        )
        return True
    except Exception as e:
        logging.error("Migration failed: %s", e)
        QMessageBox.warning(
            None, APP_NAME,
            T('migrate_error', error=str(e))
        )
        return False


def check_for_updates():
    """Check GitHub releases for updates (background, non-blocking)."""
    import threading

    def _check():
        try:
            import requests
            resp = requests.get(
                'https://api.github.com/repos/ARP273-ROSE/musicotheque/releases/latest',
                timeout=5,
                headers={'User-Agent': f'{APP_NAME}/{VERSION}'}
            )
            if resp.status_code != 200:
                return

            data = resp.json()
            remote_version = data.get('tag_name', '').lstrip('v')
            if remote_version and remote_version != VERSION:
                logging.info("Update available: %s -> %s", VERSION, remote_version)
                # Signal to main thread would go here
        except Exception:
            pass

    t = threading.Thread(target=_check, daemon=True)
    t.start()


def main():
    """Application entry point."""
    setup_logging()
    logging.info("Starting %s v%s", APP_NAME, VERSION)
    logging.info("Python %s on %s", platform.python_version(),
                 platform.system())

    # Install crash handler
    sys.excepthook = crash_handler

    # Detect hardware
    hw = detect_hardware()

    # Initialize Qt
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName('MusicOtheque')

    # Application icon
    from PyQt6.QtGui import QIcon
    icon_path = APP_DIR / 'icon.ico'
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    # Dark palette
    from PyQt6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 35))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 30))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(35, 35, 40))
    palette.setColor(QPalette.ColorRole.Text, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 50))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(60, 80, 120))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 55))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(220, 220, 220))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(120, 120, 130))
    app.setPalette(palette)

    # Stylesheet refinements
    app.setStyleSheet("""
        QMainWindow { background: #1e1e23; }
        QSplitter::handle { background: #333; width: 2px; }
        QTreeWidget { background: #1a1a20; border: none; padding: 4px; }
        QTreeWidget::item { padding: 3px 4px; }
        QTreeWidget::item:selected { background: #3c5078; }
        QTreeWidget::item:hover { background: #2a2a35; }
        QTableWidget { background: #19191e; border: none; gridline-color: #2a2a30; }
        QTableWidget::item:selected { background: #3c5078; }
        QHeaderView::section {
            background: #252530; border: none; border-bottom: 1px solid #333;
            padding: 4px 8px; font-weight: bold; color: #aaa;
        }
        QLineEdit {
            background: #252530; border: 1px solid #444; border-radius: 4px;
            padding: 4px 8px; color: #ddd;
        }
        QLineEdit:focus { border-color: #5577aa; }
        QPushButton {
            background: #353540; border: 1px solid #444; border-radius: 4px;
            padding: 4px 8px; color: #ddd;
        }
        QPushButton:hover { background: #454550; }
        QPushButton:pressed { background: #555560; }
        QPushButton:checked { background: #3c5078; border-color: #5577aa; }
        QSlider::groove:horizontal {
            background: #333; height: 4px; border-radius: 2px;
        }
        QSlider::handle:horizontal {
            background: #5577aa; width: 12px; height: 12px; margin: -4px 0;
            border-radius: 6px;
        }
        QSlider::sub-page:horizontal { background: #5577aa; border-radius: 2px; }
        QProgressBar {
            background: #252530; border: 1px solid #444; border-radius: 3px;
            text-align: center; color: #aaa; font-size: 10px;
        }
        QProgressBar::chunk { background: #5577aa; border-radius: 2px; }
        QStatusBar { background: #1a1a20; color: #888; border-top: 1px solid #333; }
        QMenuBar { background: #252530; border-bottom: 1px solid #333; }
        QMenuBar::item { padding: 4px 10px; }
        QMenuBar::item:selected { background: #3c5078; }
        QMenu { background: #2a2a35; border: 1px solid #444; }
        QMenu::item { padding: 5px 20px; }
        QMenu::item:selected { background: #3c5078; }
        QScrollBar:vertical {
            background: #1a1a20; width: 10px; border: none;
        }
        QScrollBar::handle:vertical {
            background: #444; border-radius: 4px; min-height: 30px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        QScrollBar:horizontal {
            background: #1a1a20; height: 10px; border: none;
        }
        QScrollBar::handle:horizontal {
            background: #444; border-radius: 4px; min-width: 30px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
        QFrame#playerBar { border-top: 1px solid #333; background: #222228; }
        QGroupBox {
            border: 1px solid #444; border-radius: 4px; margin-top: 8px;
            padding: 12px 8px 8px; color: #aaa;
        }
        QGroupBox::title { padding: 0 6px; }
        QComboBox {
            background: #353540; border: 1px solid #444; border-radius: 4px;
            padding: 4px 8px; color: #ddd;
        }
        QComboBox::drop-down { border: none; }
        QComboBox QAbstractItemView { background: #2a2a35; color: #ddd; }
    """)

    # Initialize database
    import database
    from i18n import detect_language, T

    detect_language()

    # Migrate from old %APPDATA% location if needed (before database.init)
    migrate_from_appdata()

    database.init(str(DB_PATH))

    # Restore language preference
    lang_row = database.fetchone("SELECT value FROM config WHERE key = 'lang'")
    if lang_row:
        from i18n import set_lang
        set_lang(lang_row['value'])

    # Check crash report
    check_crash_report()

    # Check for updates (background)
    check_for_updates()

    # Auto-backup database at startup
    from backup_manager import backup_database
    backup_database(str(DB_PATH), str(BACKUP_DIR))

    # Create main window
    from main_window import MainWindow
    window = MainWindow()
    window.show()

    # First-launch: if library is empty, offer to add a music folder
    stats = database.get_library_stats()
    scan_folders = database.fetchall("SELECT path FROM scan_folders")
    if stats['tracks'] == 0 and not scan_folders:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle(T('welcome_title'))
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(T('welcome_message'))
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            window._on_add_folder()
    elif scan_folders:
        # Check for unreachable scan folders (multi-PC/NAS scenario)
        broken = [r['path'] for r in scan_folders if not os.path.isdir(r['path'])]
        if broken:
            from PyQt6.QtWidgets import QMessageBox
            folder_list = '\n'.join(f'  \u2022 {p}' for p in broken)
            QMessageBox.warning(
                window, T('folders_check_title'),
                T('folders_check_message', folders=folder_list)
            )

    # Offer desktop shortcut on first launch
    # (json already imported at top)
    _cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.shortcut_config.json')
    def _get_cfg(k):
        try:
            with open(_cfg_path, encoding='utf-8') as f:
                return json.load(f).get(k)
        except Exception:
            return None
    def _set_cfg(k, v):
        try:
            data = {}
            if os.path.exists(_cfg_path):
                with open(_cfg_path, encoding='utf-8') as f:
                    data = json.load(f)
            data[k] = v
            with open(_cfg_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass
    from shortcut_helper import offer_shortcut
    offer_shortcut("MusicOthèque", "musicotheque.py", "logo.ico",
                   get_config=_get_cfg, set_config=_set_cfg)

    logging.info("%s ready", APP_NAME)
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
