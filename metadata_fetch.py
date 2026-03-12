"""Online metadata fetcher using MusicBrainz API."""
import logging
import time

from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

import database as db

log = logging.getLogger(__name__)

# MusicBrainz rate limit: 1 request per second
_RATE_LIMIT = 1.1
_last_request = 0.0
def _get_user_agent():
    try:
        from musicotheque import VERSION
        return f'MusicOtheque/{VERSION} (https://github.com/ARP273-ROSE/musicotheque)'
    except Exception:
        return 'MusicOtheque/2.2.0 (https://github.com/ARP273-ROSE/musicotheque)'

_USER_AGENT = _get_user_agent()


def _mb_request(endpoint, params=None):
    """Make a rate-limited MusicBrainz API request."""
    import requests

    global _last_request
    now = time.time()
    wait = _RATE_LIMIT - (now - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()

    url = f"https://musicbrainz.org/ws/2/{endpoint}"
    headers = {'User-Agent': _USER_AGENT, 'Accept': 'application/json'}
    if params is None:
        params = {}
    params['fmt'] = 'json'

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.warning("MusicBrainz request failed: %s", e)
        return None


def search_recording(title, artist='', album='', limit=5):
    """Search MusicBrainz for a recording."""
    query_parts = []
    if title:
        query_parts.append(f'recording:"{title}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')
    if album:
        query_parts.append(f'release:"{album}"')

    if not query_parts:
        return []

    query = ' AND '.join(query_parts)
    data = _mb_request('recording', {'query': query, 'limit': limit})

    if not data or 'recordings' not in data:
        return []

    results = []
    for rec in data['recordings']:
        result = {
            'mbid': rec.get('id', ''),
            'title': rec.get('title', ''),
            'score': rec.get('score', 0),
            'artist': '',
            'album': '',
            'year': None,
            'track_number': 0,
            'duration_ms': rec.get('length', 0) or 0,
        }

        # Artist
        credits = rec.get('artist-credit', [])
        if credits:
            result['artist'] = credits[0].get('name', '') if credits else ''

        # Release info
        releases = rec.get('releases', [])
        if releases:
            rel = releases[0]
            result['album'] = rel.get('title', '')
            date = rel.get('date', '')
            if date and len(date) >= 4:
                try:
                    result['year'] = int(date[:4])
                except ValueError:
                    pass
            # Track number from media
            media = rel.get('media', [])
            if media:
                tracks_list = media[0].get('track', [])
                if tracks_list:
                    try:
                        result['track_number'] = int(tracks_list[0].get('number', 0))
                    except (ValueError, TypeError):
                        pass

        results.append(result)

    return results


def fetch_cover_art(mbid_release):
    """Fetch cover art from Cover Art Archive."""
    import requests

    if not mbid_release:
        return None

    try:
        url = f"https://coverartarchive.org/release/{mbid_release}/front-250"
        headers = {'User-Agent': _USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code == 200 and resp.content:
            return resp.content
    except Exception as e:
        log.debug("Cover art fetch failed for %s: %s", mbid_release, e)
    return None


def search_release(album, artist='', limit=5):
    """Search MusicBrainz for a release (album)."""
    query_parts = []
    if album:
        query_parts.append(f'release:"{album}"')
    if artist:
        query_parts.append(f'artist:"{artist}"')

    if not query_parts:
        return []

    query = ' AND '.join(query_parts)
    data = _mb_request('release', {'query': query, 'limit': limit})

    if not data or 'releases' not in data:
        return []

    results = []
    for rel in data['releases']:
        result = {
            'mbid': rel.get('id', ''),
            'title': rel.get('title', ''),
            'score': rel.get('score', 0),
            'artist': '',
            'year': None,
            'track_count': 0,
        }

        credits = rel.get('artist-credit', [])
        if credits:
            result['artist'] = credits[0].get('name', '')

        date = rel.get('date', '')
        if date and len(date) >= 4:
            try:
                result['year'] = int(date[:4])
            except ValueError:
                pass

        media = rel.get('media', [])
        if media:
            result['track_count'] = sum(m.get('track-count', 0) for m in media)

        results.append(result)

    return results


class MetadataFetchWorker(QObject):
    """Worker that fetches metadata from MusicBrainz for tracks."""
    progress = pyqtSignal(int, int, str)  # current, total, description
    finished = pyqtSignal(int)            # updated count
    error = pyqtSignal(str)

    def __init__(self, track_ids=None, fetch_covers=True):
        super().__init__()
        self._track_ids = track_ids  # None = all tracks without MBID
        self._fetch_covers = fetch_covers
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        """Fetch metadata for selected tracks."""
        try:
            if self._track_ids:
                placeholders = ','.join('?' * len(self._track_ids))
                tracks = db.fetchall(
                    f"SELECT t.*, a.name as artist_name, al.title as album_title "
                    f"FROM tracks t "
                    f"LEFT JOIN artists a ON t.artist_id = a.id "
                    f"LEFT JOIN albums al ON t.album_id = al.id "
                    f"WHERE t.id IN ({placeholders})",
                    tuple(self._track_ids)
                )
            else:
                tracks = db.fetchall(
                    "SELECT t.*, a.name as artist_name, al.title as album_title "
                    "FROM tracks t "
                    "LEFT JOIN artists a ON t.artist_id = a.id "
                    "LEFT JOIN albums al ON t.album_id = al.id "
                    "WHERE t.musicbrainz_id IS NULL "
                    "LIMIT 500"
                )

            total = len(tracks)
            updated = 0

            for i, track in enumerate(tracks):
                if self._cancelled:
                    break

                self.progress.emit(i + 1, total, track['title'])

                results = search_recording(
                    track['title'],
                    track['artist_name'] or '',
                    track['album_title'] or ''
                )

                if not results:
                    continue

                best = results[0]
                if best['score'] < 80:
                    continue

                # Update track with MusicBrainz data
                db.execute("""
                    UPDATE tracks SET
                        musicbrainz_id = ?,
                        title = CASE WHEN title = '' OR title IS NULL THEN ? ELSE title END,
                        year = COALESCE(year, ?),
                        track_number = CASE WHEN track_number = 0 THEN ? ELSE track_number END,
                        duration_ms = CASE WHEN duration_ms = 0 THEN ? ELSE duration_ms END
                    WHERE id = ?
                """, (
                    best['mbid'], best['title'], best['year'],
                    best['track_number'], best['duration_ms'],
                    track['id']
                ), commit=False)
                updated += 1

                # Batch commit
                if updated % 20 == 0:
                    db.commit()

            db.commit()

            # Fetch cover art for albums without covers
            if self._fetch_covers and not self._cancelled:
                albums_no_cover = db.fetchall("""
                    SELECT al.id, al.title, a.name as artist_name
                    FROM albums al
                    LEFT JOIN artists a ON al.artist_id = a.id
                    WHERE al.cover_data IS NULL
                    LIMIT 100
                """)

                for j, album in enumerate(albums_no_cover):
                    if self._cancelled:
                        break

                    self.progress.emit(
                        total + j + 1, total + len(albums_no_cover),
                        f"Cover: {album['title']}"
                    )

                    releases = search_release(
                        album['title'],
                        album['artist_name'] or ''
                    )

                    if releases and releases[0]['score'] >= 80:
                        cover = fetch_cover_art(releases[0]['mbid'])
                        if cover:
                            db.execute(
                                "UPDATE albums SET cover_data = ?, musicbrainz_id = ? WHERE id = ?",
                                (cover, releases[0]['mbid'], album['id']),
                                commit=True
                            )

            log.info("Metadata fetch complete: %d tracks updated", updated)
            self.finished.emit(updated)

        except Exception as e:
            log.exception("Metadata fetch error")
            self.error.emit(str(e))
        finally:
            db.close_connection()
