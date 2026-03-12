"""iTunes Library XML importer for MusicOthèque."""
import os
import logging
import plistlib
from pathlib import Path
from urllib.parse import unquote, urlparse

from PyQt6.QtCore import QObject, pyqtSignal

import database as db

log = logging.getLogger(__name__)


def parse_itunes_location(location):
    """Convert iTunes file:// URL to local path."""
    if not location:
        return None
    try:
        parsed = urlparse(location)
        # iTunes uses file://localhost/path or file:///path
        path = unquote(parsed.path)
        # Windows: remove leading / from /C:/...
        if len(path) > 2 and path[0] == '/' and path[2] == ':':
            path = path[1:]
        # Normalize
        return os.path.normpath(path)
    except Exception:
        return None


def parse_itunes_xml(xml_path):
    """Parse iTunes Library XML and return (tracks_dict, playlists_list).

    Returns:
        tracks: dict of track_id -> track_info
        playlists: list of {name, tracks: [track_ids]}
    """
    log.info("Parsing iTunes XML: %s", xml_path)

    with open(xml_path, 'rb') as f:
        plist = plistlib.load(f)

    # Parse tracks
    raw_tracks = plist.get('Tracks', {})
    tracks = {}

    for track_id_str, info in raw_tracks.items():
        try:
            track_id = int(track_id_str)
        except (ValueError, TypeError):
            continue

        # Skip podcasts (Podcast=True key or Genre=Podcast)
        if info.get('Podcast'):
            continue
        if (info.get('Genre') or '').lower() == 'podcast':
            continue

        # Skip non-audio (movies, streams, etc.) — handles localized Kind (e.g. French "vidéo")
        kind = info.get('Kind', '')
        kind_lower = kind.lower()
        if any(x in kind_lower for x in ['video', 'vidéo', 'movie', 'pdf', 'book', 'flux', 'stream']):
            continue

        # Skip URL-based entries (no local file)
        track_type = info.get('Track Type', '')
        if track_type == 'URL':
            continue

        location = parse_itunes_location(info.get('Location', ''))

        tracks[track_id] = {
            'track_id': track_id,
            'name': info.get('Name', ''),
            'artist': info.get('Artist', ''),
            'album_artist': info.get('Album Artist', ''),
            'album': info.get('Album', ''),
            'genre': info.get('Genre', ''),
            'composer': info.get('Composer', ''),
            'year': info.get('Year'),
            'track_number': info.get('Track Number', 0),
            'disc_number': info.get('Disc Number', 1),
            'total_time_ms': info.get('Total Time', 0),
            'sample_rate': info.get('Sample Rate', 0),
            'bit_rate': info.get('Bit Rate', 0),
            'file_size': info.get('Size', 0),
            'play_count': info.get('Play Count', 0),
            'rating': info.get('Rating', 0) // 20,  # iTunes 0-100 -> 0-5
            'location': location,
            'date_added': info.get('Date Added'),
        }

    # Parse playlists
    raw_playlists = plist.get('Playlists', [])
    playlists = []

    # System playlists to skip
    skip_names = {
        'Library', 'Music', 'Movies', 'TV Shows', 'Podcasts',
        'Audiobooks', 'Downloaded', 'Genius',
    }

    for pl in raw_playlists:
        name = pl.get('Name', '')

        # Skip system playlists
        if pl.get('Master') or pl.get('Distinguished Kind') is not None:
            continue
        if name in skip_names:
            continue
        if pl.get('Smart Info'):
            # Smart playlists - include but note they're static snapshots
            pass

        track_ids = []
        for item in pl.get('Playlist Items', []):
            tid = item.get('Track ID')
            if tid and tid in tracks:
                track_ids.append(tid)

        if track_ids:
            playlists.append({
                'name': name,
                'track_ids': track_ids,
            })

    log.info("Parsed %d tracks, %d playlists from iTunes XML", len(tracks), len(playlists))
    return tracks, playlists


class ITunesImportWorker(QObject):
    """Worker that imports iTunes library into database."""
    progress = pyqtSignal(int, int, str)  # current, total, description
    finished = pyqtSignal(int, int)       # tracks_imported, playlists_imported
    error = pyqtSignal(str)

    def __init__(self, xml_path, remap_paths=None):
        super().__init__()
        self._xml_path = xml_path
        self._remap_paths = remap_paths or {}  # {old_prefix: new_prefix}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _remap_path(self, path):
        """Apply path remapping for moved libraries."""
        if not path:
            return path
        for old, new in self._remap_paths.items():
            if path.startswith(old):
                return path.replace(old, new, 1)
        return path

    def run(self):
        """Import iTunes library."""
        try:
            tracks, playlists = parse_itunes_xml(self._xml_path)
            total = len(tracks) + len(playlists)
            imported_tracks = 0
            imported_playlists = 0

            # Import tracks
            itunes_to_db = {}  # map iTunes track_id -> db track_id

            for i, (tid, tinfo) in enumerate(tracks.items()):
                if self._cancelled:
                    break

                self.progress.emit(i + 1, total, tinfo.get('name', ''))

                location = self._remap_path(tinfo['location'])

                # Skip if file doesn't exist
                if not location or not os.path.exists(location):
                    log.debug("Skipping missing file: %s", location)
                    continue

                # Check if already in DB
                existing = db.fetchone(
                    "SELECT id FROM tracks WHERE file_path = ?",
                    (os.path.normpath(location),)
                )
                if existing:
                    itunes_to_db[tid] = existing['id']
                    # Update play count and rating from iTunes
                    if tinfo['play_count'] or tinfo['rating']:
                        db.execute("""
                            UPDATE tracks SET
                                play_count = MAX(play_count, ?),
                                rating = CASE WHEN rating = 0 THEN ? ELSE rating END
                            WHERE id = ?
                        """, (tinfo['play_count'], tinfo['rating'], existing['id']),
                            commit=False)
                    continue

                # Create artist
                artist_name = tinfo['artist'] or 'Unknown Artist'
                artist_id = db.get_or_create_artist(artist_name)

                # Album artist
                album_artist_name = tinfo['album_artist'] or artist_name
                album_artist_id = (
                    db.get_or_create_artist(album_artist_name)
                    if album_artist_name != artist_name else artist_id
                )

                # Create album
                album_title = tinfo['album'] or 'Unknown Album'
                album_id = db.get_or_create_album(
                    album_title, album_artist_id, tinfo['year'],
                    os.path.dirname(location)
                )

                # Determine format
                ext = Path(location).suffix.lstrip('.').upper()

                # Insert track
                norm_path = os.path.normpath(location)
                db.execute("""
                    INSERT OR IGNORE INTO tracks(
                        title, album_id, artist_id, album_artist_id,
                        track_number, disc_number, duration_ms, file_path,
                        file_format, file_size, sample_rate, bitrate,
                        genre, year, composer, play_count, rating,
                        scanned_at, file_mtime
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)
                """, (
                    tinfo['name'] or Path(location).stem,
                    album_id, artist_id, album_artist_id,
                    tinfo['track_number'], tinfo['disc_number'],
                    tinfo['total_time_ms'], norm_path, ext,
                    tinfo['file_size'], tinfo['sample_rate'],
                    tinfo['bit_rate'] * 1000 if tinfo['bit_rate'] else 0,
                    tinfo['genre'], tinfo['year'], tinfo['composer'],
                    tinfo['play_count'], tinfo['rating'],
                    os.path.getmtime(location) if os.path.exists(location) else 0
                ), commit=False)

                row = db.fetchone("SELECT last_insert_rowid() as id")
                if row and row['id']:
                    itunes_to_db[tid] = row['id']
                    imported_tracks += 1

                # Batch commit
                if imported_tracks % 100 == 0:
                    db.commit()

            db.commit()

            # Import playlists
            base = len(tracks)
            for j, pl in enumerate(playlists):
                if self._cancelled:
                    break

                self.progress.emit(base + j + 1, total, pl['name'])

                # Check existing playlist
                existing_pl = db.fetchone(
                    "SELECT id FROM playlists WHERE name = ? AND source = 'itunes'",
                    (pl['name'],)
                )
                if existing_pl:
                    playlist_id = existing_pl['id']
                    # Clear and reimport tracks
                    db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?",
                               (playlist_id,), commit=False)
                else:
                    db.execute(
                        "INSERT INTO playlists(name, source) VALUES(?, 'itunes')",
                        (pl['name'],), commit=True
                    )
                    playlist_id = db.fetchone("SELECT last_insert_rowid() as id")['id']

                # Add tracks to playlist
                position = 0
                for track_id in pl['track_ids']:
                    db_id = itunes_to_db.get(track_id)
                    if db_id:
                        db.execute("""
                            INSERT OR IGNORE INTO playlist_tracks(playlist_id, track_id, position)
                            VALUES(?, ?, ?)
                        """, (playlist_id, db_id, position), commit=False)
                        position += 1

                if position > 0:
                    imported_playlists += 1

                db.commit()

            log.info("iTunes import: %d tracks, %d playlists", imported_tracks, imported_playlists)
            self.finished.emit(imported_tracks, imported_playlists)

        except Exception as e:
            log.exception("iTunes import error")
            self.error.emit(str(e))
        finally:
            db.close_connection()


def parse_itunes_podcasts(xml_path):
    """Parse podcast entries from iTunes Library XML.

    Returns:
        podcasts: dict of show_name -> {episodes: [{name, artist, location, duration_ms, ...}]}
    """
    log.info("Parsing iTunes podcasts from: %s", xml_path)

    with open(xml_path, 'rb') as f:
        plist = plistlib.load(f)

    raw_tracks = plist.get('Tracks', {})
    shows = {}

    for track_id_str, info in raw_tracks.items():
        # Only podcasts
        is_podcast = info.get('Podcast') or (info.get('Genre') or '').lower() == 'podcast'
        if not is_podcast:
            continue

        # Skip URL-only entries (RSS feeds, no file)
        track_type = info.get('Track Type', '')
        if track_type == 'URL':
            continue

        location = parse_itunes_location(info.get('Location', ''))
        if not location:
            continue

        show_name = info.get('Album', info.get('Artist', 'Unknown Podcast'))
        if show_name not in shows:
            shows[show_name] = {
                'title': show_name,
                'author': info.get('Artist', ''),
                'genre': info.get('Genre', 'Podcast'),
                'episodes': [],
            }

        shows[show_name]['episodes'].append({
            'title': info.get('Name', ''),
            'artist': info.get('Artist', ''),
            'location': location,
            'duration_ms': info.get('Total Time', 0),
            'file_size': info.get('Size', 0),
            'play_count': info.get('Play Count', 0),
            'date_added': info.get('Date Added'),
        })

    log.info("Parsed %d podcast shows, %d episodes",
             len(shows), sum(len(s['episodes']) for s in shows.values()))
    return shows


class ITunesPodcastImportWorker(QObject):
    """Worker that imports iTunes podcasts into the database."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int, int)  # shows_imported, episodes_imported
    error = pyqtSignal(str)

    def __init__(self, xml_path, remap_paths=None):
        super().__init__()
        self._xml_path = xml_path
        self._remap_paths = remap_paths or {}
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _remap_path(self, path):
        if not path:
            return path
        for old, new in self._remap_paths.items():
            if path.startswith(old):
                return path.replace(old, new, 1)
        return path

    def run(self):
        try:
            shows = parse_itunes_podcasts(self._xml_path)
            total = sum(len(s['episodes']) for s in shows.values())
            imported_shows = 0
            imported_episodes = 0
            current = 0

            for show_name, show_data in shows.items():
                if self._cancelled:
                    break

                # Get or create podcast
                podcast_id = db.get_or_create_podcast(
                    show_data['title'],
                    author=show_data['author']
                )
                imported_shows += 1

                for ep in show_data['episodes']:
                    if self._cancelled:
                        break

                    current += 1
                    self.progress.emit(current, total, ep.get('title', ''))

                    location = self._remap_path(ep['location'])
                    if not location:
                        continue

                    norm_path = os.path.normpath(location)
                    ext = Path(location).suffix.lstrip('.').upper()

                    # Check if already imported
                    existing = db.fetchone(
                        "SELECT id FROM podcast_episodes WHERE podcast_id = ? AND file_path = ?",
                        (podcast_id, norm_path)
                    )
                    if existing:
                        continue

                    db.execute("""
                        INSERT OR IGNORE INTO podcast_episodes(
                            podcast_id, title, file_path, file_size,
                            file_format, duration_ms, guid
                        ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    """, (
                        podcast_id, ep['title'], norm_path,
                        ep['file_size'], ext, ep['duration_ms'],
                        norm_path  # Use path as guid for local files
                    ), commit=False)
                    imported_episodes += 1

                    if imported_episodes % 100 == 0:
                        db.commit()

            db.commit()
            log.info("iTunes podcast import: %d shows, %d episodes",
                     imported_shows, imported_episodes)
            self.finished.emit(imported_shows, imported_episodes)

        except Exception as e:
            log.exception("iTunes podcast import error")
            self.error.emit(str(e))
        finally:
            db.close_connection()
