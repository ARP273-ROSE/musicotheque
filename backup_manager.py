"""Database backup manager for MusicOthèque.

Auto-backup with rotation and atomic restore.
"""
import os
import shutil
import time
import logging
from pathlib import Path

log = logging.getLogger(__name__)

MAX_DAILY_BACKUPS = 5
MAX_WEEKLY_BACKUPS = 4


def backup_database(db_path, backup_dir, label='auto'):
    """Create a timestamped backup of the database.

    Uses atomic copy (write to tmp then rename) to prevent corruption.
    Maintains rotation: 5 daily + 4 weekly backups max.
    """
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)

    if not db_path.exists():
        log.debug("No database to backup yet")
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime('%Y%m%d_%H%M%S')
    backup_name = f"musicotheque_{label}_{timestamp}.db"
    backup_path = backup_dir / backup_name
    tmp_path = backup_dir / f".tmp_{backup_name}"

    try:
        # Atomic copy: write to temp, then rename
        shutil.copy2(str(db_path), str(tmp_path))

        # Verify copy integrity (size match)
        if tmp_path.stat().st_size != db_path.stat().st_size:
            tmp_path.unlink(missing_ok=True)
            log.error("Backup size mismatch, aborted")
            return None

        # Also copy WAL and SHM if present (for consistency)
        wal_path = Path(str(db_path) + '-wal')
        if wal_path.exists():
            shutil.copy2(str(wal_path), str(backup_dir / f".tmp_{backup_name}-wal"))

        # Atomic rename
        os.replace(str(tmp_path), str(backup_path))

        # Clean up WAL copy
        tmp_wal = backup_dir / f".tmp_{backup_name}-wal"
        tmp_wal.unlink(missing_ok=True)

        log.info("Database backed up: %s (%.1f KB)",
                 backup_name, backup_path.stat().st_size / 1024)

        # Rotate old backups
        _rotate_backups(backup_dir, label)

        return str(backup_path)

    except Exception as e:
        log.error("Backup failed: %s", e)
        tmp_path.unlink(missing_ok=True)
        return None


def _rotate_backups(backup_dir, label):
    """Keep only MAX_DAILY_BACKUPS recent + MAX_WEEKLY_BACKUPS weekly backups."""
    backups = sorted(
        backup_dir.glob(f"musicotheque_{label}_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )

    # Keep first MAX_DAILY_BACKUPS as-is
    # Beyond that, keep one per week up to MAX_WEEKLY_BACKUPS
    kept = 0
    weekly_kept = 0
    seen_weeks = set()

    for bp in backups:
        if kept < MAX_DAILY_BACKUPS:
            kept += 1
            continue

        # Check week number
        mtime = bp.stat().st_mtime
        week = time.strftime('%Y-W%W', time.localtime(mtime))

        if week not in seen_weeks and weekly_kept < MAX_WEEKLY_BACKUPS:
            seen_weeks.add(week)
            weekly_kept += 1
            continue

        # Delete old backup
        try:
            bp.unlink()
            log.debug("Rotated old backup: %s", bp.name)
        except Exception:
            pass


def restore_database(backup_path, db_path):
    """Restore database from backup (atomic).

    Returns True on success, False on failure.
    """
    backup_path = Path(backup_path)
    db_path = Path(db_path)

    if not backup_path.exists():
        log.error("Backup not found: %s", backup_path)
        return False

    tmp_path = db_path.parent / f".tmp_restore_{db_path.name}"

    try:
        # Copy backup to temp
        shutil.copy2(str(backup_path), str(tmp_path))

        # Remove WAL/SHM from current DB
        for ext in ['-wal', '-shm']:
            p = Path(str(db_path) + ext)
            p.unlink(missing_ok=True)

        # Atomic replace
        os.replace(str(tmp_path), str(db_path))

        log.info("Database restored from: %s", backup_path.name)
        return True

    except Exception as e:
        log.error("Restore failed: %s", e)
        tmp_path.unlink(missing_ok=True)
        return False


def list_backups(backup_dir):
    """List available backups sorted by date (newest first)."""
    backup_dir = Path(backup_dir)
    if not backup_dir.exists():
        return []

    backups = []
    for bp in sorted(backup_dir.glob("musicotheque_*.db"),
                     key=lambda p: p.stat().st_mtime, reverse=True):
        backups.append({
            'path': str(bp),
            'name': bp.name,
            'size': bp.stat().st_size,
            'date': time.strftime('%Y-%m-%d %H:%M:%S',
                                  time.localtime(bp.stat().st_mtime)),
        })
    return backups
