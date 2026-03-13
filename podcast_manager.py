"""Podcast manager for MusicOthèque.

RSS feed parser, iTunes podcast search, and episode downloader
with thread-safe QObject workers and security hardening.
"""
import logging
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from PyQt6.QtCore import QObject, pyqtSignal

import database as db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Rate limiting: 1 request per second for external APIs
_RATE_LIMIT_SEC = 1.0
_last_request_time = 0.0
_rate_lock = threading.Lock()

# iTunes Search API base URL
_ITUNES_SEARCH_URL = "https://itunes.apple.com/search"

# HTTP request timeouts (connect, read) in seconds
_CONNECT_TIMEOUT = 30
_READ_TIMEOUT = 300
_TIMEOUT = (_CONNECT_TIMEOUT, _READ_TIMEOUT)

# Maximum allowed redirects
_MAX_REDIRECTS = 5

# Maximum download size per episode (500 MB)
_MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024

# Streaming download chunk size (64 KB)
_DOWNLOAD_CHUNK_SIZE = 65_536

# Maximum sanitized filename length (without extension)
_MAX_FILENAME_LENGTH = 200

# User-Agent for all HTTP requests
_USER_AGENT = "MusicOtheque/2.0.0 (https://github.com/ARP273-ROSE/musicotheque)"

# Allowed URL schemes
_ALLOWED_SCHEMES = {"http", "https"}

# Characters forbidden in filenames (cross-platform safe set)
_FILENAME_UNSAFE_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


# ---------------------------------------------------------------------------
# Security helpers
# ---------------------------------------------------------------------------

def _validate_url(url: str) -> str:
    """Validate and return a sanitized URL. Raises ValueError on failure."""
    if not url or not isinstance(url, str):
        raise ValueError("Empty or invalid URL")

    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise ValueError(f"Disallowed URL scheme: {parsed.scheme!r}")
    if not parsed.netloc:
        raise ValueError("URL has no host")

    return url


def _sanitize_filename(name: str, extension: str = "") -> str:
    """Sanitize a filename to be cross-platform safe.

    - Strips path separators and traversal sequences (..)
    - Removes null bytes and control characters
    - Replaces unsafe characters with underscores
    - Normalizes Unicode (NFC)
    - Limits total length
    """
    if not name:
        name = "untitled"

    # Normalize Unicode
    name = unicodedata.normalize("NFC", name)

    # Remove null bytes
    name = name.replace("\x00", "")

    # Strip any path components (anti path traversal)
    name = os.path.basename(name)
    name = name.replace("..", "")
    name = name.replace("/", "_")
    name = name.replace("\\", "_")

    # Remove unsafe characters
    name = _FILENAME_UNSAFE_RE.sub("_", name)

    # Collapse multiple underscores/spaces
    name = re.sub(r"[_\s]+", "_", name).strip("_. ")

    # Truncate to max length
    if len(name) > _MAX_FILENAME_LENGTH:
        name = name[:_MAX_FILENAME_LENGTH]

    # Fallback if empty after sanitization
    if not name:
        name = "untitled"

    # Append extension if provided
    if extension:
        if not extension.startswith("."):
            extension = f".{extension}"
        return f"{name}{extension}"

    return name


def _rate_limit():
    """Enforce rate limiting: wait if needed to respect 1 req/sec (thread-safe)."""
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < _RATE_LIMIT_SEC:
            time.sleep(_RATE_LIMIT_SEC - elapsed)
        _last_request_time = time.monotonic()


def _get_session():
    """Create a requests.Session with security defaults."""
    import requests

    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})
    session.max_redirects = _MAX_REDIRECTS
    return session


# ---------------------------------------------------------------------------
# RSS feed parsing
# ---------------------------------------------------------------------------

def parse_rss_feed(feed_url: str) -> dict:
    """Parse a podcast RSS feed and return podcast info + episodes.

    Args:
        feed_url: URL of the RSS feed (must be http/https).

    Returns:
        dict with keys:
            - title (str): Podcast title
            - author (str): Podcast author
            - description (str): Podcast description
            - image_url (str): Podcast artwork URL
            - link (str): Podcast website
            - language (str): Feed language code
            - feed_url (str): The feed URL itself
            - episodes (list[dict]): List of episode dicts, each with:
                - title (str)
                - description (str)
                - published (str): ISO 8601 date string or raw date
                - published_timestamp (float): Unix timestamp or 0
                - duration (str): Duration string from feed (e.g. "01:23:45")
                - duration_seconds (int): Duration in seconds (0 if unknown)
                - audio_url (str): Direct URL to audio file
                - file_size (int): File size in bytes (0 if unknown)
                - guid (str): Unique identifier for the episode
                - episode_type (str): "full", "trailer", "bonus", or ""

    Raises:
        ValueError: If feed_url is invalid.
        RuntimeError: If feed parsing fails entirely.
    """
    import feedparser

    feed_url = _validate_url(feed_url)
    _rate_limit()

    log.info("Parsing RSS feed: %s", feed_url)

    # feedparser handles HTTP internally; we pass user-agent
    feed = feedparser.parse(
        feed_url,
        agent=_USER_AGENT,
    )

    if feed.bozo and not feed.entries:
        bozo_msg = str(getattr(feed, "bozo_exception", "Unknown parse error"))
        raise RuntimeError(f"Failed to parse RSS feed: {bozo_msg}")

    channel = feed.feed

    podcast = {
        "title": getattr(channel, "title", ""),
        "author": (
            getattr(channel, "author", "")
            or getattr(channel, "itunes_author", "")
        ),
        "description": (
            getattr(channel, "summary", "")
            or getattr(channel, "subtitle", "")
        ),
        "image_url": "",
        "link": getattr(channel, "link", ""),
        "language": getattr(channel, "language", ""),
        "feed_url": feed_url,
        "episodes": [],
    }

    # Extract image URL (multiple possible locations)
    if hasattr(channel, "image") and hasattr(channel.image, "href"):
        podcast["image_url"] = channel.image.href
    elif hasattr(channel, "itunes_image"):
        # itunes_image can be a dict-like with 'href'
        img = channel.itunes_image
        if isinstance(img, dict):
            podcast["image_url"] = img.get("href", "")
        elif hasattr(img, "href"):
            podcast["image_url"] = img.href
        elif isinstance(img, str):
            podcast["image_url"] = img

    # Parse episodes
    for entry in feed.entries:
        episode = _parse_feed_entry(entry)
        if episode:
            podcast["episodes"].append(episode)

    # Sort episodes by published date (newest first)
    podcast["episodes"].sort(
        key=lambda e: e.get("published_timestamp", 0), reverse=True
    )

    log.info(
        "Parsed feed '%s': %d episodes", podcast["title"], len(podcast["episodes"])
    )
    return podcast


def _parse_feed_entry(entry) -> Optional[dict]:
    """Parse a single RSS feed entry into an episode dict."""
    # Find audio enclosure
    audio_url = ""
    file_size = 0

    enclosures = getattr(entry, "enclosures", [])
    for enc in enclosures:
        enc_type = getattr(enc, "type", "") or ""
        enc_url = getattr(enc, "href", "") or getattr(enc, "url", "") or ""
        if enc_type.startswith("audio/") or _looks_like_audio_url(enc_url):
            audio_url = enc_url
            try:
                file_size = int(getattr(enc, "length", 0) or 0)
            except (ValueError, TypeError):
                file_size = 0
            break

    # Also check media content
    if not audio_url:
        media_content = getattr(entry, "media_content", [])
        for mc in media_content:
            mc_type = mc.get("type", "") if isinstance(mc, dict) else ""
            mc_url = mc.get("url", "") if isinstance(mc, dict) else ""
            if mc_type.startswith("audio/") or _looks_like_audio_url(mc_url):
                audio_url = mc_url
                break

    # Skip entries without audio
    if not audio_url:
        return None

    # Validate audio URL
    try:
        audio_url = _validate_url(audio_url)
    except ValueError:
        log.debug("Skipping episode with invalid audio URL: %s", audio_url)
        return None

    # Published date
    published = ""
    published_ts = 0.0
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            published = dt.isoformat()
            published_ts = dt.timestamp()
        except (ValueError, TypeError, OverflowError):
            published = getattr(entry, "published", "")
    elif hasattr(entry, "published"):
        published = entry.published

    # Duration parsing
    duration_str = getattr(entry, "itunes_duration", "") or ""
    duration_seconds = _parse_duration(duration_str)

    # GUID
    guid = getattr(entry, "id", "") or audio_url

    return {
        "title": getattr(entry, "title", "Untitled"),
        "description": (
            getattr(entry, "summary", "")
            or getattr(entry, "subtitle", "")
        ),
        "published": published,
        "published_timestamp": published_ts,
        "duration": duration_str,
        "duration_seconds": duration_seconds,
        "audio_url": audio_url,
        "file_size": file_size,
        "guid": guid,
        "episode_type": getattr(entry, "itunes_episodetype", "") or "",
    }


def _looks_like_audio_url(url: str) -> bool:
    """Heuristic check if a URL likely points to an audio file."""
    if not url:
        return False
    lower = url.lower().split("?")[0]
    audio_exts = (".mp3", ".m4a", ".ogg", ".opus", ".aac", ".wav", ".flac", ".wma")
    return any(lower.endswith(ext) for ext in audio_exts)


def _parse_duration(duration_str: str) -> int:
    """Parse a duration string into seconds.

    Handles formats:
        - "3600" (seconds only)
        - "1:23:45" (HH:MM:SS)
        - "23:45" (MM:SS)
    Returns 0 if unparseable.
    """
    if not duration_str:
        return 0

    duration_str = duration_str.strip()

    # Pure integer = seconds
    if duration_str.isdigit():
        return int(duration_str)

    # HH:MM:SS or MM:SS
    parts = duration_str.split(":")
    try:
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        elif len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 1:
            return parts[0]
    except (ValueError, TypeError):
        pass

    return 0


# ---------------------------------------------------------------------------
# iTunes Podcast Search
# ---------------------------------------------------------------------------

def search_podcasts(query: str, limit: int = 20) -> list[dict]:
    """Search the iTunes podcast directory.

    Args:
        query: Search term.
        limit: Maximum number of results (1-200).

    Returns:
        List of dicts with keys:
            - name (str): Podcast title
            - author (str): Podcast author
            - feed_url (str): RSS feed URL
            - artwork_url (str): Artwork image URL
            - genre (str): Primary genre

    Raises:
        ValueError: If query is empty.
    """
    import requests

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    limit = max(1, min(200, limit))

    _rate_limit()

    log.info("Searching iTunes podcasts: %r (limit=%d)", query, limit)

    session = _get_session()
    try:
        resp = session.get(
            _ITUNES_SEARCH_URL,
            params={
                "term": query.strip(),
                "media": "podcast",
                "limit": limit,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        log.error("iTunes search failed: %s", e)
        raise RuntimeError(f"Podcast search failed: {e}") from e
    finally:
        session.close()

    results = []
    for item in data.get("results", []):
        feed_url = item.get("feedUrl", "")
        if not feed_url:
            continue  # Skip podcasts without a feed URL

        results.append({
            "name": item.get("collectionName", "") or item.get("trackName", ""),
            "author": item.get("artistName", ""),
            "feed_url": feed_url,
            "artwork_url": (
                item.get("artworkUrl600", "")
                or item.get("artworkUrl100", "")
                or item.get("artworkUrl60", "")
            ),
            "genre": (
                item.get("primaryGenreName", "")
            ),
        })

    log.info("iTunes search returned %d results", len(results))
    return results


# ---------------------------------------------------------------------------
# Feed refresh (detect new episodes)
# ---------------------------------------------------------------------------

def refresh_feed(feed_url: str) -> list[dict]:
    """Re-parse a feed and return only new episodes not yet in the database.

    Compares episode GUIDs against the podcast_episodes table.

    Args:
        feed_url: URL of the RSS feed.

    Returns:
        List of new episode dicts (same format as parse_rss_feed episodes).
    """
    feed_url = _validate_url(feed_url)

    # Get podcast ID from database
    row = db.fetchone(
        "SELECT id FROM podcasts WHERE feed_url = ?", (feed_url,)
    )
    if not row:
        log.warning("Podcast not found in database for feed: %s", feed_url)
        # If podcast is not in DB, all episodes are "new"
        parsed = parse_rss_feed(feed_url)
        return parsed.get("episodes", [])

    podcast_id = row["id"]

    # Get existing GUIDs from database
    existing_rows = db.fetchall(
        "SELECT guid FROM podcast_episodes WHERE podcast_id = ?", (podcast_id,)
    )
    existing_guids = {r["guid"] for r in existing_rows}

    # Parse feed
    parsed = parse_rss_feed(feed_url)
    episodes = parsed.get("episodes", [])

    # Filter to new episodes only
    new_episodes = [ep for ep in episodes if ep["guid"] not in existing_guids]

    log.info(
        "Feed refresh '%s': %d total, %d new",
        parsed.get("title", "?"), len(episodes), len(new_episodes),
    )
    return new_episodes


# ---------------------------------------------------------------------------
# Database helpers (parameterized queries)
# ---------------------------------------------------------------------------

def save_podcast(podcast: dict) -> int:
    """Insert or update a podcast in the database.

    Args:
        podcast: Dict with keys from parse_rss_feed (title, author, etc.)

    Returns:
        Podcast row ID.
    """
    feed_url = podcast.get("feed_url", "")
    if not feed_url:
        raise ValueError("Podcast must have a feed_url")

    existing = db.fetchone(
        "SELECT id FROM podcasts WHERE feed_url = ?", (feed_url,)
    )

    if existing:
        db.execute(
            """UPDATE podcasts SET
                title = ?, author = ?, description = ?,
                image_url = ?, link = ?, language = ?,
                last_checked = datetime('now'), updated_at = datetime('now')
            WHERE id = ?""",
            (
                podcast.get("title", ""),
                podcast.get("author", ""),
                podcast.get("description", ""),
                podcast.get("image_url", ""),
                podcast.get("link", ""),
                podcast.get("language", ""),
                existing["id"],
            ),
            commit=True,
        )
        return existing["id"]
    else:
        db.execute(
            """INSERT INTO podcasts(
                title, author, description, image_url, link,
                language, feed_url, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (
                podcast.get("title", ""),
                podcast.get("author", ""),
                podcast.get("description", ""),
                podcast.get("image_url", ""),
                podcast.get("link", ""),
                podcast.get("language", ""),
                feed_url,
            ),
            commit=True,
        )
        row = db.fetchone("SELECT last_insert_rowid() AS id")
        return row["id"]


def save_episodes(podcast_id: int, episodes: list[dict]) -> int:
    """Insert new episodes into the database (skip existing GUIDs).

    Args:
        podcast_id: ID of the parent podcast.
        episodes: List of episode dicts from parse_rss_feed.

    Returns:
        Number of episodes inserted.
    """
    if not episodes:
        return 0

    # Fetch existing GUIDs for this podcast
    existing = db.fetchall(
        "SELECT guid FROM podcast_episodes WHERE podcast_id = ?", (podcast_id,)
    )
    existing_guids = {r["guid"] for r in existing}

    inserted = 0
    for ep in episodes:
        guid = ep.get("guid", "")
        if not guid or guid in existing_guids:
            continue

        # Convert duration_seconds to duration_ms
        duration_ms = ep.get("duration_seconds", 0) * 1000

        db.execute(
            """INSERT INTO podcast_episodes(
                podcast_id, guid, title, description, published_at,
                duration_ms, file_url, file_size,
                episode_type, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                podcast_id,
                guid,
                ep.get("title", ""),
                ep.get("description", ""),
                ep.get("published", ""),
                duration_ms,
                ep.get("audio_url", ""),
                ep.get("file_size", 0),
                ep.get("episode_type", ""),
            ),
            commit=False,
        )
        existing_guids.add(guid)
        inserted += 1

        # Batch commit every 50 episodes
        if inserted % 50 == 0:
            db.commit()

    if inserted:
        db.commit()

    log.info("Saved %d new episodes for podcast_id=%d", inserted, podcast_id)
    return inserted


def mark_episode_downloaded(episode_id: int, file_path: str) -> None:
    """Mark an episode as downloaded in the database."""
    db.execute(
        """UPDATE podcast_episodes SET
            downloaded = 1, file_path = ?,
            downloaded_at = datetime('now')
        WHERE id = ?""",
        (file_path, episode_id),
        commit=True,
    )


def get_subscribed_podcasts() -> list[dict]:
    """Return all subscribed podcasts from the database."""
    rows = db.fetchall(
        "SELECT * FROM podcasts ORDER BY title COLLATE NOCASE"
    )
    return [dict(r) for r in rows]


def get_podcast_episodes(podcast_id: int, limit: int = 200) -> list[dict]:
    """Return episodes for a podcast, newest first."""
    rows = db.fetchall(
        "SELECT * FROM podcast_episodes WHERE podcast_id = ? "
        "ORDER BY published DESC LIMIT ?",
        (podcast_id, limit),
    )
    return [dict(r) for r in rows]


def delete_podcast(podcast_id: int) -> None:
    """Delete a podcast and all its episodes from the database."""
    db.execute(
        "DELETE FROM podcast_episodes WHERE podcast_id = ?",
        (podcast_id,), commit=False,
    )
    db.execute(
        "DELETE FROM podcasts WHERE id = ?",
        (podcast_id,), commit=True,
    )
    log.info("Deleted podcast_id=%d and its episodes", podcast_id)


# ---------------------------------------------------------------------------
# Episode download worker
# ---------------------------------------------------------------------------

class PodcastDownloadWorker(QObject):
    """Worker for downloading podcast episodes in a background thread.

    Designed to be moved to a QThread. Emits progress/finished/error signals.

    Signals:
        progress(int, int, str): (current_index, total_count, description)
        finished(int): total number of successfully downloaded episodes
        error(str): error message on fatal failure

    Usage:
        worker = PodcastDownloadWorker(episodes, output_dir)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        thread.start()
    """

    progress = pyqtSignal(int, int, str)   # current, total, description
    finished = pyqtSignal(int)             # downloaded count
    error = pyqtSignal(str)                # error message

    def __init__(
        self,
        episodes: list[dict],
        output_dir: str,
        parent: QObject = None,
    ):
        """Initialize the download worker.

        Args:
            episodes: List of dicts, each must have:
                - audio_url (str): URL to download
                - filename (str): Desired filename (will be sanitized)
                Optionally:
                - episode_id (int): Database ID for marking as downloaded
                - file_size (int): Expected file size for validation
            output_dir: Directory to save downloaded files.
        """
        super().__init__(parent)
        self._episodes = list(episodes)
        self._output_dir = Path(output_dir)
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the download."""
        self._cancelled = True

    def run(self):
        """Download all queued episodes. Call from a worker thread."""
        import requests

        downloaded = 0

        try:
            # Ensure output directory exists
            self._output_dir.mkdir(parents=True, exist_ok=True)

            total = len(self._episodes)
            if total == 0:
                self.finished.emit(0)
                return

            session = _get_session()

            try:
                for i, episode in enumerate(self._episodes):
                    if self._cancelled:
                        log.info("Download cancelled at %d/%d", i, total)
                        break

                    audio_url = episode.get("audio_url", "")
                    raw_filename = episode.get("filename", "")

                    # Generate progress description
                    desc = episode.get("title", raw_filename or f"Episode {i + 1}")
                    self.progress.emit(i + 1, total, desc)

                    # Validate URL
                    try:
                        audio_url = _validate_url(audio_url)
                    except ValueError as e:
                        log.warning("Skipping invalid URL: %s (%s)", audio_url, e)
                        continue

                    # Sanitize filename
                    if not raw_filename:
                        # Derive filename from URL
                        url_path = urlparse(audio_url).path
                        raw_filename = os.path.basename(url_path) or "episode"

                    # Split name and extension
                    name_part, ext_part = os.path.splitext(raw_filename)
                    if not ext_part:
                        ext_part = ".mp3"  # Default extension
                    safe_filename = _sanitize_filename(name_part, ext_part)

                    # Build full output path and verify it's inside output_dir
                    target_path = self._output_dir / safe_filename
                    try:
                        resolved = target_path.resolve()
                        output_resolved = self._output_dir.resolve()
                        # Anti path traversal: ensure target is inside output_dir
                        if not str(resolved).startswith(str(output_resolved)):
                            log.warning(
                                "Path traversal blocked: %s -> %s",
                                safe_filename, resolved,
                            )
                            continue
                    except (OSError, ValueError):
                        log.warning("Invalid path: %s", target_path)
                        continue

                    # Skip if file already exists and has non-zero size
                    if target_path.exists() and target_path.stat().st_size > 0:
                        log.debug("Already downloaded: %s", safe_filename)
                        # Still mark as downloaded in DB if episode_id is present
                        ep_id = episode.get("episode_id")
                        if ep_id:
                            mark_episode_downloaded(ep_id, str(target_path))
                        downloaded += 1
                        continue

                    # Download with streaming
                    success = self._download_file(
                        session, audio_url, target_path, episode
                    )
                    if success:
                        downloaded += 1

                        # Mark in database
                        ep_id = episode.get("episode_id")
                        if ep_id:
                            mark_episode_downloaded(ep_id, str(target_path))
            finally:
                session.close()
                db.close_connection()

            log.info("Download complete: %d/%d episodes", downloaded, total)
            self.finished.emit(downloaded)

        except Exception as e:
            log.exception("Download worker fatal error")
            self.error.emit(str(e))

    def _download_file(
        self, session, url: str, target_path: Path, episode: dict
    ) -> bool:
        """Download a single file with streaming and size validation.

        Args:
            session: requests.Session to use.
            url: Validated audio URL.
            target_path: Destination file path (already sanitized).
            episode: Episode dict for expected file_size.

        Returns:
            True if download succeeded, False otherwise.
        """
        import requests

        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        expected_size = episode.get("file_size", 0)

        try:
            _rate_limit()

            resp = session.get(
                url,
                stream=True,
                timeout=_TIMEOUT,
                allow_redirects=True,
            )
            resp.raise_for_status()

            # Check content-length against size limit
            content_length = int(resp.headers.get("content-length", 0))
            if content_length > _MAX_DOWNLOAD_BYTES:
                log.warning(
                    "Episode too large (%d bytes > %d max): %s",
                    content_length, _MAX_DOWNLOAD_BYTES, url,
                )
                resp.close()
                return False

            # Stream to temp file
            bytes_written = 0
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=_DOWNLOAD_CHUNK_SIZE):
                    if self._cancelled:
                        resp.close()
                        tmp_path.unlink(missing_ok=True)
                        return False

                    if chunk:
                        bytes_written += len(chunk)

                        # Enforce size limit during streaming
                        if bytes_written > _MAX_DOWNLOAD_BYTES:
                            log.warning(
                                "Download exceeded size limit at %d bytes: %s",
                                bytes_written, url,
                            )
                            resp.close()
                            tmp_path.unlink(missing_ok=True)
                            return False

                        f.write(chunk)

                # Flush to disk
                f.flush()
                os.fsync(f.fileno())

            # Validate downloaded size
            if bytes_written == 0:
                log.warning("Downloaded 0 bytes: %s", url)
                tmp_path.unlink(missing_ok=True)
                return False

            if expected_size > 0:
                # Allow 5% tolerance for content-encoding differences
                tolerance = max(1024, int(expected_size * 0.05))
                if abs(bytes_written - expected_size) > tolerance:
                    log.warning(
                        "Size mismatch: expected %d, got %d for %s",
                        expected_size, bytes_written, url,
                    )
                    # Still keep the file — size from RSS can be inaccurate

            # Atomic rename: tmp -> final
            os.replace(str(tmp_path), str(target_path))

            log.info(
                "Downloaded: %s (%.1f MB)",
                target_path.name, bytes_written / (1024 * 1024),
            )
            return True

        except requests.Timeout:
            log.warning("Download timed out: %s", url)
            tmp_path.unlink(missing_ok=True)
            return False
        except requests.RequestException as e:
            log.warning("Download failed for %s: %s", url, e)
            tmp_path.unlink(missing_ok=True)
            return False
        except OSError as e:
            log.error("File I/O error downloading %s: %s", url, e)
            tmp_path.unlink(missing_ok=True)
            return False


# ---------------------------------------------------------------------------
# Feed subscription worker (parse + save to DB)
# ---------------------------------------------------------------------------

class PodcastSubscribeWorker(QObject):
    """Worker to subscribe to a podcast feed (parse + save to DB).

    Signals:
        progress(int, int, str): (step, total_steps, description)
        finished(int): podcast_id on success
        error(str): error message on failure
    """

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, feed_url: str, parent: QObject = None):
        super().__init__(parent)
        self._feed_url = feed_url

    def run(self):
        """Parse the feed, save podcast and episodes to the database."""
        try:
            self.progress.emit(1, 3, "Parsing feed...")

            parsed = parse_rss_feed(self._feed_url)

            self.progress.emit(2, 3, "Saving podcast...")
            podcast_id = save_podcast(parsed)

            self.progress.emit(3, 3, "Saving episodes...")
            save_episodes(podcast_id, parsed.get("episodes", []))

            log.info(
                "Subscribed to '%s' (id=%d, %d episodes)",
                parsed.get("title", "?"),
                podcast_id,
                len(parsed.get("episodes", [])),
            )
            self.finished.emit(podcast_id)

        except Exception as e:
            log.exception("Subscription failed for %s", self._feed_url)
            self.error.emit(str(e))
        finally:
            db.close_connection()


# ---------------------------------------------------------------------------
# Feed refresh worker
# ---------------------------------------------------------------------------

class PodcastRefreshWorker(QObject):
    """Worker to refresh all subscribed podcast feeds.

    Signals:
        progress(int, int, str): (current_podcast, total_podcasts, podcast_title)
        finished(int): total new episodes found across all feeds
        error(str): error message on fatal failure
    """

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, podcast_ids: list[int] = None, parent: QObject = None):
        """Initialize refresh worker.

        Args:
            podcast_ids: List of podcast IDs to refresh (None = all).
        """
        super().__init__(parent)
        self._podcast_ids = podcast_ids
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        """Refresh feeds and save new episodes."""
        try:
            if self._podcast_ids:
                # Fetch only selected podcasts
                placeholders = ",".join("?" * len(self._podcast_ids))
                podcasts = db.fetchall(
                    f"SELECT id, feed_url, title FROM podcasts "
                    f"WHERE id IN ({placeholders})",
                    tuple(self._podcast_ids),
                )
            else:
                podcasts = db.fetchall(
                    "SELECT id, feed_url, title FROM podcasts ORDER BY title"
                )

            total = len(podcasts)
            total_new = 0

            for i, pod in enumerate(podcasts):
                if self._cancelled:
                    break

                title = pod["title"] or pod["feed_url"]
                self.progress.emit(i + 1, total, title)

                try:
                    new_episodes = refresh_feed(pod["feed_url"])
                    if new_episodes:
                        count = save_episodes(pod["id"], new_episodes)
                        total_new += count
                        # Update podcast metadata too
                        parsed = parse_rss_feed(pod["feed_url"])
                        save_podcast(parsed)
                except Exception as e:
                    log.warning("Failed to refresh '%s': %s", title, e)
                    # Continue with other feeds

            log.info("Feed refresh complete: %d new episodes", total_new)
            self.finished.emit(total_new)

        except Exception as e:
            log.exception("Feed refresh worker fatal error")
            self.error.emit(str(e))
        finally:
            db.close_connection()
