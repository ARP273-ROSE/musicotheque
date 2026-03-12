"""Library file system watcher for MusicOthèque.

Monitors scan folders for file changes (add/modify/delete) and triggers
background re-scan. Also handles automatic path relocation when drive
letters change or when accessing the same library from different OS.

Cross-platform: uses polling (3-minute interval) to work on all OS
including network drives (NAS) where inotify/FSEvents don't work.
"""
import os
import time
import logging
import threading
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

import database as db

log = logging.getLogger(__name__)

# Polling interval in milliseconds
POLL_INTERVAL_MS = 3 * 60 * 1000  # 3 minutes
# Minimum interval between scans to avoid storms
MIN_SCAN_INTERVAL_S = 30


class LibraryWatcher(QObject):
    """Watches library folders for changes and detects path relocations.

    Uses polling (no OS-specific watchers) so it works reliably on:
    - Local drives, NAS/SMB shares, drive letter changes
    - Windows, Linux, macOS
    """

    # Emitted when changes are detected (added_count, modified_count, removed_count)
    changes_detected = pyqtSignal(int, int, int)
    # Emitted when paths were auto-relocated
    paths_relocated = pyqtSignal(str, str, int)  # old_prefix, new_prefix, count
    # Emitted to request a scan of specific folders
    scan_requested = pyqtSignal(list)  # folder paths

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._last_scan_time = 0
        self._running = False
        self._known_files = {}  # path -> mtime snapshot

    def start(self):
        """Start watching."""
        self._running = True
        # Initial snapshot in background
        threading.Thread(target=self._build_snapshot, daemon=True).start()
        self._timer.start(POLL_INTERVAL_MS)
        log.info("Library watcher started (poll interval: %ds)", POLL_INTERVAL_MS // 1000)

    def stop(self):
        """Stop watching."""
        self._running = False
        self._timer.stop()

    def _build_snapshot(self):
        """Build initial file snapshot from database."""
        try:
            rows = db.fetchall("SELECT file_path, file_mtime FROM tracks")
            snapshot = {}
            for row in rows:
                snapshot[row['file_path']] = row['file_mtime'] or 0
            self._known_files = snapshot
            log.debug("Watcher snapshot: %d tracks", len(snapshot))
        except Exception as e:
            log.warning("Watcher snapshot failed: %s", e)
        finally:
            db.close_connection()

    def _poll(self):
        """Poll scan folders for changes."""
        if not self._running:
            return

        now = time.time()
        if now - self._last_scan_time < MIN_SCAN_INTERVAL_S:
            return

        threading.Thread(target=self._check_changes, daemon=True).start()

    def _check_changes(self):
        """Background check for file system changes."""
        try:
            from scanner import AUDIO_EXTENSIONS
            folders = db.fetchall("SELECT path FROM scan_folders")
            if not folders:
                return

            added = 0
            modified = 0
            removed = 0
            changed_folders = set()

            # Check for new/modified files
            current_files = set()
            for folder_row in folders:
                folder_path = folder_row['path']
                if not os.path.isdir(folder_path):
                    # Try auto-relocation for this folder
                    self._try_auto_relocate(folder_path)
                    continue

                for root, dirs, files in os.walk(folder_path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for f in files:
                        ext = os.path.splitext(f)[1].lower()
                        if ext not in AUDIO_EXTENSIONS:
                            continue
                        fpath = os.path.normpath(os.path.join(root, f))
                        current_files.add(fpath)

                        try:
                            mtime = os.path.getmtime(fpath)
                        except OSError:
                            continue

                        if fpath not in self._known_files:
                            added += 1
                            changed_folders.add(folder_path)
                        elif abs(self._known_files[fpath] - mtime) > 1:
                            modified += 1
                            changed_folders.add(folder_path)

            # Check for removed files
            for known_path in list(self._known_files.keys()):
                # Only check files that should be in scanned folders
                if known_path not in current_files and not os.path.exists(known_path):
                    removed += 1

            if added > 0 or modified > 0 or removed > 0:
                log.info("Watcher detected changes: +%d ~%d -%d", added, modified, removed)
                self._last_scan_time = time.time()
                # Emit signal on main thread via QTimer
                QTimer.singleShot(0, lambda: self.changes_detected.emit(added, modified, removed))
                if changed_folders:
                    QTimer.singleShot(0, lambda: self.scan_requested.emit(list(changed_folders)))

                # Update snapshot
                self._build_snapshot()

        except Exception as e:
            log.warning("Watcher check failed: %s", e)
        finally:
            db.close_connection()

    def _try_auto_relocate(self, missing_folder):
        """Try to find a relocated folder and fix paths automatically.

        Handles common cases:
        - Drive letter change on Windows (D: -> E:, P: -> Q:)
        - Linux/macOS mount point change (/mnt/nas -> /media/nas)
        - Same NAS accessed from different OS (P:/Musique -> /mnt/nas/Musique)
        """
        try:
            # Get all known root paths from scan_folders
            all_folders = db.fetchall("SELECT path FROM scan_folders")
            missing_norm = missing_folder.replace('\\', '/')

            # Strategy 1: Try other drive letters (Windows)
            if len(missing_norm) >= 2 and missing_norm[1] == ':':
                tail = missing_norm[2:]  # everything after drive letter
                for letter in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                    candidate = f"{letter}:{tail}"
                    if os.path.isdir(candidate):
                        count = self._do_relocate(missing_folder, candidate)
                        if count > 0:
                            log.info("Auto-relocated: %s -> %s (%d tracks)",
                                     missing_folder, candidate, count)
                            QTimer.singleShot(0, lambda mf=missing_folder, c=candidate, n=count:
                                              self.paths_relocated.emit(mf, c, n))
                        return

            # Strategy 2: Check if the folder tail exists under other scan folders
            # e.g., missing = "F:/iTunes/Music", another folder = "P:/"
            # -> check if "P:/iTunes/Music" exists
            parts = Path(missing_norm).parts
            for folder_row in all_folders:
                other = folder_row['path'].replace('\\', '/')
                if other == missing_norm:
                    continue
                # Try appending tail parts of missing path to the other folder
                for i in range(1, len(parts)):
                    tail = '/'.join(parts[i:])
                    candidate = os.path.join(other, tail)
                    if os.path.isdir(candidate):
                        count = self._do_relocate(missing_folder, candidate)
                        if count > 0:
                            log.info("Auto-relocated via common root: %s -> %s (%d tracks)",
                                     missing_folder, candidate, count)
                            QTimer.singleShot(0, lambda mf=missing_folder, c=candidate, n=count:
                                              self.paths_relocated.emit(mf, c, n))
                        return

        except Exception as e:
            log.debug("Auto-relocate failed for %s: %s", missing_folder, e)
        finally:
            db.close_connection()

    def _do_relocate(self, old_prefix, new_prefix):
        """Relocate paths in database and update scan_folders."""
        count = db.relocate_paths(old_prefix, new_prefix)
        if count > 0:
            # Update scan_folders entry
            db.execute(
                "UPDATE scan_folders SET path = ? WHERE path = ?",
                (new_prefix, old_prefix), commit=True
            )
        return count

    def force_check(self):
        """Force an immediate check (called after user actions)."""
        self._last_scan_time = 0
        threading.Thread(target=self._check_changes, daemon=True).start()


def normalize_path_for_comparison(path):
    """Normalize a path for cross-platform comparison.

    Strips drive letter, normalizes separators, lowercases on Windows.
    Used to match tracks across OS changes.
    """
    p = path.replace('\\', '/')
    # Strip drive letter (C:, D:, etc.)
    if len(p) >= 2 and p[1] == ':':
        p = p[2:]
    # Strip common mount prefixes
    for prefix in ('/mnt/', '/media/', '/Volumes/'):
        if p.startswith(prefix):
            # Remove mount + first component (mount point name)
            rest = p[len(prefix):]
            slash = rest.find('/')
            if slash >= 0:
                p = rest[slash:]
            break
    return p.lower()
