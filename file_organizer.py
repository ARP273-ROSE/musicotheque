"""File organizer for MusicOthèque.

Sorts music files into a clean Artist/Album/Track folder structure.
Handles filename sanitization, duplicate detection, and database path updates.
"""
import os
import re
import shutil
import logging
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

import database as db

log = logging.getLogger(__name__)

# Characters not allowed in filenames (Windows-safe)
_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MULTI_SPACE = re.compile(r'\s+')


def sanitize_filename(name, max_len=120):
    """Make a string safe for use as filename on all platforms."""
    if not name:
        return 'Unknown'
    name = _UNSAFE_RE.sub('', name)
    name = _MULTI_SPACE.sub(' ', name).strip()
    name = name.strip('.')  # Windows doesn't like trailing dots
    if len(name) > max_len:
        name = name[:max_len].rstrip()
    return name or 'Unknown'


def build_target_path(base_dir, artist, album, track_num, disc_num, title, ext):
    """Build the target file path: base/Artist/Album/DD-TT Title.ext"""
    artist_safe = sanitize_filename(artist or 'Unknown Artist')
    album_safe = sanitize_filename(album or 'Unknown Album')

    # Track filename
    if disc_num and disc_num > 1:
        prefix = f"{disc_num:01d}-{track_num:02d}" if track_num else f"{disc_num:01d}-00"
    else:
        prefix = f"{track_num:02d}" if track_num else "00"

    title_safe = sanitize_filename(title or 'Unknown')
    filename = f"{prefix} {title_safe}{ext}"

    return Path(base_dir) / artist_safe / album_safe / filename


class FileOrganizer(QObject):
    """Worker that organizes music files into Artist/Album/Track structure."""
    progress = pyqtSignal(int, int, str)  # current, total, filename
    finished = pyqtSignal(int, int)       # moved, errors
    error = pyqtSignal(str)

    def __init__(self, dest_dir, track_ids=None, dry_run=False):
        super().__init__()
        self._dest_dir = dest_dir
        self._track_ids = track_ids  # None = all tracks
        self._dry_run = dry_run
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        """Organize files."""
        try:
            if self._track_ids:
                placeholders = ','.join('?' * len(self._track_ids))
                tracks = db.fetchall(
                    f"SELECT t.*, a.name as artist_name, al.title as album_title "
                    f"FROM tracks t "
                    f"LEFT JOIN artists a ON t.album_artist_id = a.id "
                    f"LEFT JOIN albums al ON t.album_id = al.id "
                    f"WHERE t.id IN ({placeholders})",
                    tuple(self._track_ids)
                )
            else:
                tracks = db.fetchall(
                    "SELECT t.*, a.name as artist_name, al.title as album_title "
                    "FROM tracks t "
                    "LEFT JOIN artists a ON t.album_artist_id = a.id "
                    "LEFT JOIN albums al ON t.album_id = al.id"
                )

            total = len(tracks)
            moved = 0
            errors = 0

            for i, track in enumerate(tracks):
                if self._cancelled:
                    break

                src = track['file_path']
                self.progress.emit(i + 1, total, os.path.basename(src))

                if not os.path.exists(src):
                    errors += 1
                    continue

                ext = Path(src).suffix
                target = build_target_path(
                    self._dest_dir,
                    track['artist_name'],
                    track['album_title'],
                    track.get('track_number', 0),
                    track.get('disc_number', 1),
                    track.get('title', ''),
                    ext
                )

                # Path traversal protection
                if not str(target.resolve()).startswith(
                        str(Path(self._dest_dir).resolve())):
                    log.warning("Path traversal blocked: %s", target)
                    errors += 1
                    continue

                # Skip if already in correct location
                if os.path.normpath(src) == os.path.normpath(str(target)):
                    continue

                # Handle duplicate filenames
                if target.exists():
                    stem = target.stem
                    suffix = target.suffix
                    parent = target.parent
                    for n in range(2, 100):
                        candidate = parent / f"{stem} ({n}){suffix}"
                        if not candidate.exists():
                            target = candidate
                            break

                if not self._dry_run:
                    try:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src), str(target))

                        # Update database
                        db.execute(
                            "UPDATE tracks SET file_path = ? WHERE id = ?",
                            (str(target), track['id']), commit=False
                        )

                        # Update album folder_path
                        db.execute(
                            "UPDATE albums SET folder_path = ? WHERE id = ?",
                            (str(target.parent), track['album_id']), commit=False
                        )

                        moved += 1

                        # Batch commit
                        if moved % 50 == 0:
                            db.commit()

                    except Exception as e:
                        log.warning("Failed to move %s: %s", src, e)
                        errors += 1
                else:
                    moved += 1  # dry run counts as success

            if not self._dry_run:
                db.commit()

            log.info("File organizer: %d moved, %d errors", moved, errors)
            self.finished.emit(moved, errors)

        except Exception as e:
            log.exception("File organizer error")
            self.error.emit(str(e))
        finally:
            db.close_connection()
