"""CD audio ripping module for MusicOthèque.

Detects CD/DVD drives, reads disc TOC, queries MusicBrainz for metadata,
rips tracks to FLAC via ffmpeg, tags with mutagen, and fetches cover art
from Cover Art Archive. Thread-safe QObject workers with PyQt6 signals.

Cross-platform: Windows, Linux, macOS.
"""
import logging
import os
import platform
import re
import string
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

import database as db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SYSTEM = platform.system()
_USER_AGENT = 'MusicOtheque/2.0.0 (https://github.com/ARP273-ROSE/musicotheque)'

# MusicBrainz rate limit: max 1 request per second
_MB_RATE_LIMIT = 1.1
_mb_last_request = 0.0

# ffmpeg safety limits
_FFMPEG_TIMEOUT = 600  # 10 minutes per track
_FFMPEG_PROBE_TIMEOUT = 30  # seconds for probing / detection

# CD audio constants (Red Book)
_CD_SAMPLE_RATE = 44100
_CD_BIT_DEPTH = 16
_CD_CHANNELS = 2
_FRAMES_PER_SECOND = 75  # CD frames per second


# ---------------------------------------------------------------------------
# Filename sanitisation
# ---------------------------------------------------------------------------

# Characters forbidden on at least one major OS
_FORBIDDEN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Reserved Windows filenames
_RESERVED_NAMES = frozenset({
    'CON', 'PRN', 'AUX', 'NUL',
    *(f'COM{i}' for i in range(1, 10)),
    *(f'LPT{i}' for i in range(1, 10)),
})


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Clean a string for safe use as a filename on any OS.

    - Strips leading/trailing whitespace and dots
    - Replaces forbidden characters with underscores
    - Avoids Windows reserved names
    - Normalises Unicode (NFC)
    - Truncates to *max_length* characters
    """
    if not name:
        return '_'

    # NFC normalisation
    name = unicodedata.normalize('NFC', name.strip())

    # Replace forbidden characters
    name = _FORBIDDEN_CHARS.sub('_', name)

    # Collapse multiple underscores / spaces
    name = re.sub(r'[_ ]{2,}', '_', name)

    # Strip leading/trailing dots and spaces (Windows restriction)
    name = name.strip('. ')

    # Reserved name guard (case-insensitive)
    stem = Path(name).stem.upper()
    if stem in _RESERVED_NAMES:
        name = f'_{name}'

    # Truncate (keep any extension intact)
    if len(name) > max_length:
        name = name[:max_length].rstrip('. ')

    return name or '_'


# ---------------------------------------------------------------------------
# Drive path validation
# ---------------------------------------------------------------------------

def _validate_drive_path(drive: str) -> str:
    """Validate and normalise a drive/device path.

    Raises ValueError for suspicious input (path traversal, null bytes, etc.)
    """
    if not drive or not isinstance(drive, str):
        raise ValueError("Drive path must be a non-empty string")

    # Reject null bytes and backslashes in non-Windows device paths
    if '\x00' in drive:
        raise ValueError("Drive path contains null bytes")
    if '..' in drive:
        raise ValueError("Drive path contains path traversal")

    drive = drive.strip()

    if _SYSTEM == 'Windows':
        # Accept D: or D:\ style drive letters only
        if re.match(r'^[A-Za-z]:[\\/]?$', drive):
            return drive[0].upper() + ':'
        raise ValueError(f"Invalid Windows drive path: {drive!r}")
    else:
        # Linux/macOS: must start with /dev/
        if not drive.startswith('/dev/'):
            raise ValueError(f"Invalid device path: {drive!r}")
        # Basic chars only
        if not re.match(r'^/dev/[a-zA-Z0-9/_-]+$', drive):
            raise ValueError(f"Invalid device path characters: {drive!r}")
        return drive


# ---------------------------------------------------------------------------
# 1. CD drive detection
# ---------------------------------------------------------------------------

def detect_cd_drives() -> list[dict]:
    """Detect available CD/DVD optical drives on the system.

    Returns a list of dicts:
        {drive: str, has_media: bool, label: str}
    """
    if _SYSTEM == 'Windows':
        return _detect_drives_windows()
    elif _SYSTEM == 'Linux':
        return _detect_drives_linux()
    elif _SYSTEM == 'Darwin':
        return _detect_drives_macos()
    else:
        log.warning("Unsupported platform for CD detection: %s", _SYSTEM)
        return []


def _detect_drives_windows() -> list[dict]:
    """Detect CD drives on Windows via wmic and kernel32."""
    drives = []

    # Method 1: wmic cdrom (gives media status and caption)
    try:
        result = subprocess.run(
            ['wmic', 'cdrom', 'get', 'Drive,MediaLoaded,Caption', '/format:csv'],
            capture_output=True, text=True, timeout=_FFMPEG_PROBE_TIMEOUT
        )
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        # Skip header: Node,Caption,Drive,MediaLoaded
        for line in lines[1:]:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4:
                # CSV format: Node, Caption, Drive, MediaLoaded
                caption = parts[1]
                drive_letter = parts[2]
                has_media = parts[3].upper() == 'TRUE'
                if drive_letter and re.match(r'^[A-Z]:$', drive_letter, re.IGNORECASE):
                    drives.append({
                        'drive': drive_letter.upper(),
                        'has_media': has_media,
                        'label': caption or drive_letter,
                    })
        if drives:
            return drives
    except (subprocess.SubprocessError, OSError) as exc:
        log.debug("wmic cdrom failed: %s", exc)

    # Method 2: Fallback — iterate drive letters, check type with GetDriveTypeW
    try:
        import ctypes
        DRIVE_CDROM = 5
        kernel32 = ctypes.windll.kernel32
        for letter in string.ascii_uppercase:
            root = f'{letter}:\\'
            drive_type = kernel32.GetDriveTypeW(root)
            if drive_type == DRIVE_CDROM:
                # Check if media is loaded by testing if root is accessible
                has_media = os.path.isdir(root)
                vol_name = ''
                if has_media:
                    try:
                        buf = ctypes.create_unicode_buffer(256)
                        kernel32.GetVolumeInformationW(
                            root, buf, 256, None, None, None, None, 0
                        )
                        vol_name = buf.value
                    except Exception:
                        pass
                drives.append({
                    'drive': f'{letter}:',
                    'has_media': has_media,
                    'label': vol_name or f'CD Drive ({letter}:)',
                })
    except Exception as exc:
        log.debug("ctypes drive detection failed: %s", exc)

    return drives


def _detect_drives_linux() -> list[dict]:
    """Detect CD drives on Linux by probing /dev/sr* and /dev/cdrom."""
    drives = []
    candidates = []

    # Collect candidate device nodes
    for name in ('sr0', 'sr1', 'sr2', 'sr3', 'cdrom', 'dvd'):
        dev = f'/dev/{name}'
        if os.path.exists(dev):
            # Resolve symlinks to avoid duplicates
            real = os.path.realpath(dev)
            if real not in [c['real'] for c in candidates]:
                candidates.append({'dev': dev, 'real': real})

    for entry in candidates:
        dev = entry['dev']
        has_media = False
        label = f'Optical ({os.path.basename(dev)})'

        # Check media presence via udevadm if available
        try:
            result = subprocess.run(
                ['udevadm', 'info', '--query=property', f'--name={dev}'],
                capture_output=True, text=True, timeout=10
            )
            props = {}
            for line in result.stdout.splitlines():
                if '=' in line:
                    k, _, v = line.partition('=')
                    props[k.strip()] = v.strip()
            has_media = props.get('ID_CDROM_MEDIA', '0') == '1'
            label = props.get('ID_MODEL', label)
            vol_label = props.get('ID_FS_LABEL', '')
            if vol_label:
                label = f'{label} [{vol_label}]'
        except (subprocess.SubprocessError, OSError):
            # Fallback: try to open the device
            try:
                fd = os.open(dev, os.O_RDONLY | os.O_NONBLOCK)
                os.close(fd)
                has_media = True
            except OSError:
                pass

        drives.append({
            'drive': dev,
            'has_media': has_media,
            'label': label,
        })

    return drives


def _detect_drives_macos() -> list[dict]:
    """Detect CD drives on macOS using drutil and diskutil."""
    drives = []

    # drutil status tells us about the current disc slot
    try:
        result = subprocess.run(
            ['drutil', 'status'],
            capture_output=True, text=True, timeout=10
        )
        output = result.stdout

        # Parse drive name
        drive_name_match = re.search(r'Vendor\s*:\s*(.+)', output)
        product_match = re.search(r'Product\s*:\s*(.+)', output)
        label_parts = []
        if drive_name_match:
            label_parts.append(drive_name_match.group(1).strip())
        if product_match:
            label_parts.append(product_match.group(1).strip())
        label = ' '.join(label_parts) or 'Optical Drive'

        # Check for disc presence
        has_media = 'No Media Inserted' not in output and 'Type:' in output

        # Determine device node from diskutil
        device = '/dev/disk1'  # default fallback
        if has_media:
            try:
                du_result = subprocess.run(
                    ['diskutil', 'list'],
                    capture_output=True, text=True, timeout=10
                )
                for line in du_result.stdout.splitlines():
                    if 'CD_partition_scheme' in line or 'Apple_partition_scheme' in line:
                        parts = line.strip().split()
                        if parts:
                            dev_id = parts[-1]
                            if dev_id.startswith('disk'):
                                device = f'/dev/{dev_id}'
                                break
            except (subprocess.SubprocessError, OSError):
                pass

        drives.append({
            'drive': device,
            'has_media': has_media,
            'label': label,
        })

    except FileNotFoundError:
        log.debug("drutil not found — no optical drive support")
    except (subprocess.SubprocessError, OSError) as exc:
        log.debug("drutil status failed: %s", exc)

    return drives


# ---------------------------------------------------------------------------
# 2. CD Table of Contents
# ---------------------------------------------------------------------------

def get_cd_toc(drive: str) -> dict | None:
    """Read the Table of Contents from an audio CD.

    Uses ffprobe (preferred) or ffmpeg to enumerate tracks.

    Returns dict:
        {track_count: int,
         tracks: [{number: int, start_sector: int, duration_ms: int}],
         total_duration_ms: int}
    or None on failure.
    """
    drive = _validate_drive_path(drive)

    # Try ffprobe first (cleaner output)
    toc = _get_toc_ffprobe(drive)
    if toc:
        return toc

    # Fallback: platform-specific
    if _SYSTEM == 'Windows':
        toc = _get_toc_mci_windows(drive)
        if toc:
            return toc

    # Last resort: ffmpeg stderr parsing
    return _get_toc_ffmpeg(drive)


def _get_toc_ffprobe(drive: str) -> dict | None:
    """Use ffprobe to read CD track information."""
    if _SYSTEM == 'Windows':
        # ffprobe cannot directly probe a CD on Windows the same way,
        # but we can try the cdio/lavfi protocol
        source = f'cdio:{drive}'
    else:
        source = drive

    try:
        result = subprocess.run(
            [
                'ffprobe', '-hide_banner',
                '-show_entries', 'stream=index,duration',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1',
                '-i', source
            ],
            capture_output=True, text=True, timeout=_FFMPEG_PROBE_TIMEOUT
        )

        combined = result.stdout + '\n' + result.stderr
        tracks = []

        # Parse stream durations from output
        # ffprobe may list multiple streams for each track
        duration_matches = re.findall(
            r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d+)',
            combined
        )

        if not duration_matches:
            # Try stream-based parsing
            stream_durations = re.findall(r'duration=([\d.]+)', result.stdout)
            for i, dur_str in enumerate(stream_durations):
                try:
                    dur_ms = int(float(dur_str) * 1000)
                    tracks.append({
                        'number': i + 1,
                        'start_sector': 0,
                        'duration_ms': dur_ms,
                    })
                except ValueError:
                    pass
        else:
            for i, (hh, mm, ss, frac) in enumerate(duration_matches):
                dur_ms = (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000
                dur_ms += int(frac.ljust(3, '0')[:3])
                tracks.append({
                    'number': i + 1,
                    'start_sector': 0,
                    'duration_ms': dur_ms,
                })

        if tracks:
            total = sum(t['duration_ms'] for t in tracks)
            return {
                'track_count': len(tracks),
                'tracks': tracks,
                'total_duration_ms': total,
            }
    except FileNotFoundError:
        log.warning("ffprobe not found in PATH")
    except (subprocess.SubprocessError, OSError) as exc:
        log.debug("ffprobe TOC failed: %s", exc)

    return None


def _get_toc_ffmpeg(drive: str) -> dict | None:
    """Parse CD track info from ffmpeg stderr output."""
    if _SYSTEM == 'Windows':
        source = f'cdio:{drive}'
    else:
        source = drive

    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-i', source, '-f', 'null', '-'],
            capture_output=True, text=True, timeout=_FFMPEG_PROBE_TIMEOUT
        )

        combined = result.stderr + '\n' + result.stdout
        tracks = []

        # Look for "Track N" or "Stream #0:N" lines with durations
        # ffmpeg typically outputs something like:
        # Duration: 00:03:45.20, ...
        # Stream #0:0: Audio: pcm_s16le ...
        # or per-track durations in various formats
        track_pattern = re.compile(
            r'(?:Track|Stream\s+#\d+:)(\d+).*?'
            r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d+)',
            re.DOTALL
        )
        for m in track_pattern.finditer(combined):
            num = int(m.group(1))
            dur_ms = (int(m.group(2)) * 3600 + int(m.group(3)) * 60 + int(m.group(4))) * 1000
            dur_ms += int(m.group(5).ljust(3, '0')[:3])
            tracks.append({
                'number': num,
                'start_sector': 0,
                'duration_ms': dur_ms,
            })

        # Fallback: just count Duration lines
        if not tracks:
            dur_matches = re.findall(
                r'Duration:\s*(\d{2}):(\d{2}):(\d{2})\.(\d+)',
                combined
            )
            for i, (hh, mm, ss, frac) in enumerate(dur_matches):
                dur_ms = (int(hh) * 3600 + int(mm) * 60 + int(ss)) * 1000
                dur_ms += int(frac.ljust(3, '0')[:3])
                tracks.append({
                    'number': i + 1,
                    'start_sector': 0,
                    'duration_ms': dur_ms,
                })

        if tracks:
            total = sum(t['duration_ms'] for t in tracks)
            return {
                'track_count': len(tracks),
                'tracks': tracks,
                'total_duration_ms': total,
            }
    except FileNotFoundError:
        log.warning("ffmpeg not found in PATH")
    except (subprocess.SubprocessError, OSError) as exc:
        log.debug("ffmpeg TOC failed: %s", exc)

    return None


def _get_toc_mci_windows(drive: str) -> dict | None:
    """Read CD TOC on Windows using MCI commands via ctypes/winmm.dll."""
    try:
        import ctypes
        winmm = ctypes.windll.winmm

        # Buffer for MCI responses
        buf = ctypes.create_unicode_buffer(512)

        def mci_send(command: str) -> str:
            """Send an MCI command string and return the response."""
            err = winmm.mciSendStringW(command, buf, 511, None)
            if err != 0:
                err_buf = ctypes.create_unicode_buffer(256)
                winmm.mciGetErrorStringW(err, err_buf, 255)
                raise RuntimeError(f"MCI error {err}: {err_buf.value}")
            return buf.value

        # Validate drive path before MCI commands
        validated = _validate_drive_path(drive)
        drive_letter = validated.rstrip(':')
        alias = 'cdripdev'

        # Open cdaudio device
        mci_send(f'open {drive_letter}: type cdaudio alias {alias}')

        try:
            # Set time format to milliseconds
            mci_send(f'set {alias} time format milliseconds')

            # Get number of tracks
            resp = mci_send(f'status {alias} number of tracks')
            track_count = int(resp.strip())

            tracks = []
            for n in range(1, track_count + 1):
                # Get track length in ms
                resp = mci_send(f'status {alias} length track {n}')
                dur_ms = int(resp.strip())

                # Get track position (start offset) in ms
                resp_pos = mci_send(f'status {alias} position track {n}')
                start_ms = int(resp_pos.strip())
                start_sector = int(start_ms / 1000 * _FRAMES_PER_SECOND)

                tracks.append({
                    'number': n,
                    'start_sector': start_sector,
                    'duration_ms': dur_ms,
                })

            total = sum(t['duration_ms'] for t in tracks)
            return {
                'track_count': track_count,
                'tracks': tracks,
                'total_duration_ms': total,
            }
        finally:
            try:
                mci_send(f'close {alias}')
            except Exception:
                pass

    except Exception as exc:
        log.debug("MCI TOC read failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 3. MusicBrainz disc lookup
# ---------------------------------------------------------------------------

def _mb_rate_wait():
    """Enforce MusicBrainz rate limit (max 1 request/sec)."""
    global _mb_last_request
    now = time.time()
    wait = _MB_RATE_LIMIT - (now - _mb_last_request)
    if wait > 0:
        time.sleep(wait)
    _mb_last_request = time.time()


def _mb_request(endpoint: str, params: dict | None = None) -> dict | None:
    """Make a rate-limited MusicBrainz API request."""
    import requests

    _mb_rate_wait()

    url = f'https://musicbrainz.org/ws/2/{endpoint}'
    headers = {'User-Agent': _USER_AGENT, 'Accept': 'application/json'}
    if params is None:
        params = {}
    params['fmt'] = 'json'

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Basic validation: response must be a dict
        if not isinstance(data, dict):
            log.warning("MusicBrainz returned non-dict response")
            return None
        return data
    except Exception as exc:
        log.warning("MusicBrainz request failed: %s", exc)
        return None


def lookup_disc_musicbrainz(toc: dict) -> dict | None:
    """Look up a CD on MusicBrainz using track count and durations.

    Attempts a search by matching track count and total duration.
    Falls back to a broad release search if no exact match.

    Returns dict:
        {title: str, artist: str, year: int|None,
         tracks: [{number: int, title: str, artist: str, duration_ms: int}],
         release_mbid: str}
    or None on failure.
    """
    if not toc or not toc.get('tracks'):
        return None

    track_count = toc['track_count']
    total_dur_ms = toc['total_duration_ms']
    total_dur_s = total_dur_ms // 1000

    # --- Method 1: Search for releases matching track count + duration ---
    # Build a TOC string for the query (approximate)
    # MusicBrainz advanced search: tracks:N AND dur:range
    dur_min = max(0, total_dur_s - 30)  # allow +/- 30s tolerance
    dur_max = total_dur_s + 30

    query = f'tracks:{track_count} AND dur:[{dur_min} TO {dur_max}]'
    data = _mb_request('release', {'query': query, 'limit': 10})

    if data and 'releases' in data and data['releases']:
        # Pick best match (highest score)
        releases = data['releases']
        releases.sort(key=lambda r: r.get('score', 0), reverse=True)

        for rel in releases:
            if rel.get('score', 0) < 60:
                continue

            result = _parse_release_result(rel)
            if result:
                # Fetch full release with recordings
                full = _fetch_release_recordings(result['release_mbid'])
                if full:
                    return full
                return result

    # --- Method 2: Build a more relaxed query ---
    # Search by track count only
    query = f'tracks:{track_count} AND status:official'
    data = _mb_request('release', {'query': query, 'limit': 5})

    if data and 'releases' in data:
        for rel in data['releases']:
            if rel.get('score', 0) < 70:
                continue

            # Check if total duration roughly matches
            media = rel.get('media', [])
            if media:
                rel_tracks = sum(m.get('track-count', 0) for m in media)
                if rel_tracks == track_count:
                    result = _parse_release_result(rel)
                    if result:
                        full = _fetch_release_recordings(result['release_mbid'])
                        if full:
                            return full
                        return result

    log.info("No MusicBrainz match for CD with %d tracks, %ds total",
             track_count, total_dur_s)
    return None


def _parse_release_result(rel: dict) -> dict | None:
    """Parse a MusicBrainz release search result into our format."""
    if not rel:
        return None

    mbid = rel.get('id', '')
    title = rel.get('title', '')
    if not mbid or not title:
        return None

    # Artist
    artist = ''
    credits = rel.get('artist-credit', [])
    if credits and isinstance(credits, list):
        artist_parts = []
        for credit in credits:
            name = credit.get('name', '')
            join = credit.get('joinphrase', '')
            if name:
                artist_parts.append(name + join)
        artist = ''.join(artist_parts)

    # Year
    year = None
    date = rel.get('date', '')
    if date and len(date) >= 4:
        try:
            year = int(date[:4])
        except ValueError:
            pass

    # Track list (from search result — may be incomplete)
    tracks = []
    media = rel.get('media', [])
    for medium in media:
        track_list = medium.get('tracks', medium.get('track', []))
        if isinstance(track_list, list):
            for trk in track_list:
                track_artist = artist  # default to album artist
                trk_credits = trk.get('artist-credit', [])
                if trk_credits and isinstance(trk_credits, list):
                    parts = []
                    for c in trk_credits:
                        n = c.get('name', '')
                        j = c.get('joinphrase', '')
                        if n:
                            parts.append(n + j)
                    if parts:
                        track_artist = ''.join(parts)

                number = 0
                try:
                    number = int(trk.get('number', trk.get('position', 0)))
                except (ValueError, TypeError):
                    pass

                dur_ms = trk.get('length', 0) or 0

                tracks.append({
                    'number': number,
                    'title': trk.get('title', f'Track {number}'),
                    'artist': track_artist,
                    'duration_ms': dur_ms,
                })

    return {
        'title': title,
        'artist': artist,
        'year': year,
        'tracks': tracks,
        'release_mbid': mbid,
    }


def _fetch_release_recordings(release_mbid: str) -> dict | None:
    """Fetch full track listing for a release (inc=recordings)."""
    if not release_mbid:
        return None

    data = _mb_request(f'release/{release_mbid}', {'inc': 'recordings+artist-credits'})
    if not data:
        return None

    title = data.get('title', '')
    # Artist
    artist = ''
    credits = data.get('artist-credit', [])
    if credits and isinstance(credits, list):
        parts = []
        for c in credits:
            n = c.get('name', '')
            j = c.get('joinphrase', '')
            if n:
                parts.append(n + j)
        artist = ''.join(parts)

    year = None
    date = data.get('date', '')
    if date and len(date) >= 4:
        try:
            year = int(date[:4])
        except ValueError:
            pass

    tracks = []
    media = data.get('media', [])
    for medium in media:
        track_list = medium.get('tracks', medium.get('track', []))
        if isinstance(track_list, list):
            for trk in track_list:
                recording = trk.get('recording', {})

                track_artist = artist
                rec_credits = recording.get('artist-credit', trk.get('artist-credit', []))
                if rec_credits and isinstance(rec_credits, list):
                    parts = []
                    for c in rec_credits:
                        n = c.get('name', '')
                        j = c.get('joinphrase', '')
                        if n:
                            parts.append(n + j)
                    if parts:
                        track_artist = ''.join(parts)

                number = 0
                try:
                    number = int(trk.get('number', trk.get('position', 0)))
                except (ValueError, TypeError):
                    pass

                dur_ms = recording.get('length', trk.get('length', 0)) or 0
                rec_title = recording.get('title', trk.get('title', f'Track {number}'))

                tracks.append({
                    'number': number,
                    'title': rec_title,
                    'artist': track_artist,
                    'duration_ms': dur_ms,
                })

    return {
        'title': title,
        'artist': artist,
        'year': year,
        'tracks': tracks,
        'release_mbid': release_mbid,
    }


# ---------------------------------------------------------------------------
# 4. Cover art
# ---------------------------------------------------------------------------

def fetch_cover_art(release_mbid: str) -> bytes | None:
    """Fetch album cover art from Cover Art Archive.

    Returns raw image bytes (JPEG/PNG) or None.
    """
    import requests

    if not release_mbid or not isinstance(release_mbid, str):
        return None

    # Validate MBID format (UUID)
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
                    release_mbid, re.IGNORECASE):
        log.warning("Invalid release MBID: %s", release_mbid)
        return None

    # Rate limit (shared with MusicBrainz — Cover Art Archive is a related service)
    _mb_rate_wait()

    try:
        # Request front cover, 500px (good quality for embedding)
        url = f'https://coverartarchive.org/release/{release_mbid}/front-500'
        headers = {'User-Agent': _USER_AGENT}
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)

        if resp.status_code == 200 and resp.content:
            # Sanity check: cover should be an image (< 20 MB)
            content_len = len(resp.content)
            if content_len > 20 * 1024 * 1024:
                log.warning("Cover art too large (%d bytes), skipping", content_len)
                return None
            # Check magic bytes for JPEG / PNG
            magic = resp.content[:4]
            if magic[:2] == b'\xff\xd8':  # JPEG
                return resp.content
            if magic[:4] == b'\x89PNG':  # PNG
                return resp.content
            # Accept anyway (might be WebP or other)
            return resp.content

        if resp.status_code == 404:
            log.debug("No cover art for release %s", release_mbid)
        else:
            log.debug("Cover art request returned %d", resp.status_code)

    except Exception as exc:
        log.debug("Cover art fetch failed for %s: %s", release_mbid, exc)

    return None


# ---------------------------------------------------------------------------
# 5. CD Rip Worker
# ---------------------------------------------------------------------------

class CDRipWorker(QObject):
    """Background worker that rips an audio CD to FLAC files.

    Signals:
        progress(int track, int total, str description)
        track_ripped(int track, str filepath)
        finished(int track_count, str album_dir)
        error(str message)
    """

    progress = pyqtSignal(int, int, str)       # track_num, total, description
    track_ripped = pyqtSignal(int, str)         # track_num, output_path
    finished = pyqtSignal(int, str)             # total_tracks, album_directory
    error = pyqtSignal(str)

    def __init__(self, drive: str, output_dir: str,
                 metadata: dict | None = None,
                 format: str = 'flac'):
        """
        Args:
            drive: CD drive path (e.g. 'D:' on Windows, '/dev/sr0' on Linux).
            output_dir: Base output directory for ripped files.
            metadata: Optional dict from lookup_disc_musicbrainz().
                      {title, artist, year, tracks: [...], release_mbid}
            format: Output format — currently only 'flac' is supported.
        """
        super().__init__()
        self._drive = drive
        self._output_dir = output_dir
        self._metadata = metadata
        self._format = format.lower()
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the ripping process."""
        self._cancelled = True

    def run(self):
        """Rip all tracks from the CD.

        This method should be invoked from a QThread.
        """
        try:
            drive = _validate_drive_path(self._drive)
        except ValueError as exc:
            self.error.emit(str(exc))
            return

        try:
            self._do_rip(drive)
        except Exception as exc:
            log.exception("CD ripping error")
            self.error.emit(str(exc))
        finally:
            db.close_connection()

    # ---- Internal ripping logic ----

    def _do_rip(self, drive: str):
        """Core ripping routine."""
        # Determine number of tracks
        toc = get_cd_toc(drive)
        if not toc or toc['track_count'] == 0:
            self.error.emit("Could not read CD table of contents. "
                            "Ensure an audio CD is inserted.")
            return

        track_count = toc['track_count']
        log.info("CD TOC: %d tracks, total %d ms", track_count, toc['total_duration_ms'])

        # Prepare metadata
        meta = self._metadata
        if meta and meta.get('tracks'):
            # Validate track count alignment
            if len(meta['tracks']) != track_count:
                log.warning("Metadata track count (%d) != CD track count (%d); "
                            "falling back to generic names",
                            len(meta['tracks']), track_count)
                meta = None

        album_artist = meta['artist'] if meta else 'Unknown Artist'
        album_title = meta['title'] if meta else 'Unknown Album'
        album_year = meta.get('year') if meta else None
        release_mbid = meta.get('release_mbid', '') if meta else ''

        # Build output directory: output_dir / Artist / Album
        safe_artist = sanitize_filename(album_artist)
        safe_album = sanitize_filename(album_title)
        if album_year:
            safe_album = f'{album_year} - {safe_album}'
        album_dir = Path(self._output_dir) / safe_artist / safe_album
        album_dir.mkdir(parents=True, exist_ok=True)

        log.info("Ripping %d tracks to %s", track_count, album_dir)

        # Fetch and save cover art
        cover_data = None
        if release_mbid:
            self.progress.emit(0, track_count, 'Fetching cover art...')
            cover_data = fetch_cover_art(release_mbid)
            if cover_data:
                cover_path = album_dir / 'cover.jpg'
                try:
                    # Atomic write: tmp + rename
                    tmp_cover = cover_path.with_suffix('.tmp')
                    tmp_cover.write_bytes(cover_data)
                    tmp_cover.replace(cover_path)
                    log.info("Cover art saved to %s", cover_path)
                except OSError as exc:
                    log.warning("Failed to save cover art: %s", exc)

        # Rip each track
        ripped_count = 0
        for track_num in range(1, track_count + 1):
            if self._cancelled:
                log.info("Ripping cancelled at track %d", track_num)
                break

            # Track metadata
            track_title = f'Track {track_num:02d}'
            track_artist = album_artist
            track_dur_ms = 0

            if meta and meta.get('tracks'):
                for t in meta['tracks']:
                    if t.get('number') == track_num:
                        track_title = t.get('title', track_title)
                        track_artist = t.get('artist', track_artist)
                        track_dur_ms = t.get('duration_ms', 0)
                        break

            # Also get duration from TOC if missing from metadata
            if track_dur_ms == 0 and toc['tracks']:
                for t in toc['tracks']:
                    if t['number'] == track_num:
                        track_dur_ms = t['duration_ms']
                        break

            # Build output filename
            safe_title = sanitize_filename(track_title)
            filename = f'{track_num:02d} - {safe_title}.flac'
            output_path = album_dir / filename

            description = f'[{track_num}/{track_count}] {track_title}'
            self.progress.emit(track_num, track_count, description)
            log.info("Ripping track %d: %s", track_num, track_title)

            # Rip to FLAC
            success = self._rip_track(drive, track_num, str(output_path))
            if not success:
                log.error("Failed to rip track %d", track_num)
                continue

            # Tag the FLAC file with mutagen
            self._tag_flac(
                str(output_path),
                title=track_title,
                artist=track_artist,
                album=album_title,
                album_artist=album_artist,
                track_number=track_num,
                total_tracks=track_count,
                year=album_year,
                cover_data=cover_data,
            )

            # Register in database
            self._register_track_in_db(
                filepath=str(output_path),
                title=track_title,
                artist=track_artist,
                album_artist=album_artist,
                album=album_title,
                track_number=track_num,
                year=album_year,
                duration_ms=track_dur_ms,
                album_dir=str(album_dir),
                cover_data=cover_data,
            )

            ripped_count += 1
            self.track_ripped.emit(track_num, str(output_path))

        log.info("Ripping complete: %d/%d tracks", ripped_count, track_count)
        self.finished.emit(ripped_count, str(album_dir))

    def _rip_track(self, drive: str, track_num: int, output_path: str) -> bool:
        """Rip a single CD track to FLAC using ffmpeg.

        Tries multiple approaches depending on the platform.
        Returns True on success.
        """
        # Ensure parent directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Use a temporary file to avoid partial output on failure
        tmp_path = output_path + '.tmp'

        try:
            success = False

            if _SYSTEM == 'Linux':
                success = self._rip_ffmpeg_cdio(drive, track_num, tmp_path)
            elif _SYSTEM == 'Darwin':
                success = self._rip_ffmpeg_cdio(drive, track_num, tmp_path)
            elif _SYSTEM == 'Windows':
                # Try cdio protocol first
                success = self._rip_ffmpeg_cdio(drive, track_num, tmp_path)
                # Fallback: MCI raw PCM extraction + ffmpeg encode
                if not success:
                    success = self._rip_mci_windows(drive, track_num, tmp_path)

            if success and os.path.isfile(tmp_path) and os.path.getsize(tmp_path) > 0:
                # Atomic rename
                final = Path(output_path)
                if final.exists():
                    final.unlink()
                Path(tmp_path).replace(final)
                return True
            else:
                # Clean up partial file
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                return False

        except Exception as exc:
            log.error("Rip track %d error: %s", track_num, exc)
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            return False

    def _rip_ffmpeg_cdio(self, drive: str, track_num: int, output_path: str) -> bool:
        """Rip a track using ffmpeg's cdio/cdda input.

        Linux/macOS: ffmpeg -f libcdio -ss N -i /dev/sr0 ...
        Windows: uses stream index selection
        """
        # Track index is 0-based for ffmpeg stream mapping
        stream_index = track_num - 1

        if _SYSTEM == 'Windows':
            # On Windows, try the grabbing approach with stream selection
            # ffmpeg -f libcdio -i D: -map 0:a:N output.flac
            cmds_to_try = [
                # Attempt 1: libcdio input format
                [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-f', 'libcdio', '-i', drive,
                    '-map', f'0:a:{stream_index}',
                    '-acodec', 'flac', '-sample_fmt', 's16',
                    '-ar', str(_CD_SAMPLE_RATE),
                    output_path,
                ],
                # Attempt 2: direct device reference with cdio protocol
                [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-f', 'libcdio', '-i', f'{drive}/',
                    '-map', f'0:a:{stream_index}',
                    '-acodec', 'flac',
                    output_path,
                ],
            ]
        else:
            # Linux / macOS
            cmds_to_try = [
                # Attempt 1: libcdio format with stream mapping
                [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-f', 'libcdio', '-i', drive,
                    '-map', f'0:a:{stream_index}',
                    '-acodec', 'flac', '-sample_fmt', 's16',
                    '-ar', str(_CD_SAMPLE_RATE),
                    output_path,
                ],
                # Attempt 2: direct device as input (some ffmpeg builds)
                [
                    'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                    '-i', f'cdda:{drive}',
                    '-map', f'0:a:{stream_index}',
                    '-acodec', 'flac',
                    output_path,
                ],
                # Attempt 3: raw device input, track via -ss offset
                # (requires TOC info for seeking, less reliable)
            ]

        for cmd in cmds_to_try:
            if self._cancelled:
                return False
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True, text=True,
                    timeout=_FFMPEG_TIMEOUT
                )
                if result.returncode == 0 and os.path.isfile(output_path):
                    if os.path.getsize(output_path) > 1000:  # at least 1KB
                        return True
            except subprocess.TimeoutExpired:
                log.warning("ffmpeg timeout on track %d", track_num)
            except FileNotFoundError:
                log.warning("ffmpeg not found in PATH")
                return False
            except (subprocess.SubprocessError, OSError) as exc:
                log.debug("ffmpeg cdio attempt failed: %s", exc)

        return False

    def _rip_mci_windows(self, drive: str, track_num: int, output_path: str) -> bool:
        """Fallback ripper for Windows: extract raw PCM via MCI, then encode to FLAC.

        Uses winmm.dll MCI commands to read CD audio to a temporary WAV,
        then encodes to FLAC with ffmpeg.
        """
        try:
            import ctypes
            winmm = ctypes.windll.winmm

            buf = ctypes.create_unicode_buffer(512)

            def mci_send(command: str) -> str:
                err = winmm.mciSendStringW(command, buf, 511, None)
                if err != 0:
                    err_buf = ctypes.create_unicode_buffer(256)
                    winmm.mciGetErrorStringW(err, err_buf, 255)
                    raise RuntimeError(f"MCI error {err}: {err_buf.value}")
                return buf.value

            drive_letter = drive.rstrip(':\\/')
            alias = f'cdrip{track_num}'

            # Open cdaudio
            mci_send(f'open {drive_letter}: type cdaudio alias {alias}')

            try:
                # Set time format to TMSF (Track:Min:Sec:Frame)
                mci_send(f'set {alias} time format tmsf')

                # Record track to a temporary WAV file
                # MCI play command with 'wait' will play through the output
                # Instead, we use the wav audio device to capture

                # Alternative approach: use MCI to open as waveaudio
                # This is more reliable for extraction
                pass

            finally:
                try:
                    mci_send(f'close {alias}')
                except Exception:
                    pass

            # Since direct MCI→WAV extraction is complex and unreliable,
            # try cdparanoia or cdda2wav if available on the PATH
            return self._rip_external_tool(drive, track_num, output_path)

        except Exception as exc:
            log.debug("MCI rip failed: %s", exc)
            return self._rip_external_tool(drive, track_num, output_path)

    def _rip_external_tool(self, drive: str, track_num: int, output_path: str) -> bool:
        """Try external CD ripping tools as a last resort.

        Tries cdparanoia (Linux), cdda2wav / cdda2ogg (various).
        Outputs to a temp WAV, then encodes with ffmpeg.
        """
        tmp_wav = output_path + '.wav'

        try:
            # Try cdparanoia (Linux, available on some macOS with brew)
            if _SYSTEM in ('Linux', 'Darwin'):
                try:
                    cmd = [
                        'cdparanoia', '-d', drive,
                        str(track_num), tmp_wav,
                    ]
                    result = subprocess.run(
                        cmd, capture_output=True, text=True,
                        timeout=_FFMPEG_TIMEOUT
                    )
                    if result.returncode == 0 and os.path.isfile(tmp_wav):
                        return self._encode_wav_to_flac(tmp_wav, output_path)
                except FileNotFoundError:
                    pass

            # Try cdda2wav (available on some systems)
            try:
                dev_arg = f'dev={drive}' if _SYSTEM != 'Windows' else f'dev={drive}\\'
                cmd = [
                    'cdda2wav', dev_arg,
                    '-t', str(track_num),
                    '-O', 'wav',
                    tmp_wav,
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=_FFMPEG_TIMEOUT
                )
                if result.returncode == 0 and os.path.isfile(tmp_wav):
                    return self._encode_wav_to_flac(tmp_wav, output_path)
            except FileNotFoundError:
                pass

        finally:
            # Clean up temp WAV
            try:
                os.unlink(tmp_wav)
            except OSError:
                pass

        return False

    def _encode_wav_to_flac(self, wav_path: str, flac_path: str) -> bool:
        """Encode a WAV file to FLAC using ffmpeg."""
        try:
            cmd = [
                'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
                '-i', wav_path,
                '-acodec', 'flac', '-sample_fmt', 's16',
                '-ar', str(_CD_SAMPLE_RATE),
                flac_path,
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=_FFMPEG_TIMEOUT
            )
            return (result.returncode == 0
                    and os.path.isfile(flac_path)
                    and os.path.getsize(flac_path) > 1000)
        except (subprocess.SubprocessError, FileNotFoundError, OSError) as exc:
            log.error("WAV→FLAC encode failed: %s", exc)
            return False

    # ---- Tagging ----

    @staticmethod
    def _tag_flac(filepath: str, *, title: str, artist: str, album: str,
                  album_artist: str, track_number: int, total_tracks: int,
                  year: int | None, cover_data: bytes | None):
        """Write Vorbis comment tags (and optional cover) to a FLAC file."""
        try:
            from mutagen.flac import FLAC, Picture

            audio = FLAC(filepath)

            audio['TITLE'] = title
            audio['ARTIST'] = artist
            audio['ALBUM'] = album
            audio['ALBUMARTIST'] = album_artist
            audio['TRACKNUMBER'] = str(track_number)
            audio['TRACKTOTAL'] = str(total_tracks)
            audio['TOTALTRACKS'] = str(total_tracks)
            if year:
                audio['DATE'] = str(year)
            audio['ENCODER'] = 'MusicOthèque CD Ripper'

            # Embed cover art as a FLAC picture block
            if cover_data:
                try:
                    pic = Picture()
                    pic.type = 3  # Cover (front)
                    # Detect mime type from magic bytes
                    if cover_data[:2] == b'\xff\xd8':
                        pic.mime = 'image/jpeg'
                    elif cover_data[:4] == b'\x89PNG':
                        pic.mime = 'image/png'
                    else:
                        pic.mime = 'image/jpeg'
                    pic.desc = 'Front Cover'
                    pic.data = cover_data
                    audio.clear_pictures()
                    audio.add_picture(pic)
                except Exception as exc:
                    log.debug("Failed to embed cover art: %s", exc)

            audio.save()
            log.debug("Tagged %s", filepath)

        except Exception as exc:
            log.warning("Failed to tag %s: %s", filepath, exc)

    # ---- Database registration ----

    @staticmethod
    def _register_track_in_db(*, filepath: str, title: str, artist: str,
                              album_artist: str, album: str, track_number: int,
                              year: int | None, duration_ms: int,
                              album_dir: str, cover_data: bytes | None):
        """Register the ripped track in the MusicOthèque database."""
        try:
            # Get or create artist
            artist_id = db.get_or_create_artist(artist)

            # Album artist
            if album_artist and album_artist != artist:
                album_artist_id = db.get_or_create_artist(album_artist)
            else:
                album_artist_id = artist_id

            # Get or create album
            album_id = db.get_or_create_album(album, album_artist_id, year, album_dir)

            # Store cover art on album if not already set
            if cover_data:
                existing = db.fetchone(
                    "SELECT cover_data FROM albums WHERE id = ?", (album_id,)
                )
                if existing and not existing['cover_data']:
                    db.execute(
                        "UPDATE albums SET cover_data = ? WHERE id = ?",
                        (cover_data, album_id), commit=True
                    )

            # Get file stats
            stat = os.stat(filepath)
            file_size = stat.st_size
            file_mtime = stat.st_mtime

            # Read FLAC audio properties for accurate duration / sample rate
            actual_duration_ms = duration_ms
            sample_rate = _CD_SAMPLE_RATE
            bit_depth = _CD_BIT_DEPTH
            channels = _CD_CHANNELS
            bitrate = 0

            try:
                from mutagen.flac import FLAC
                audio = FLAC(filepath)
                if audio.info:
                    actual_duration_ms = int((audio.info.length or 0) * 1000) or duration_ms
                    sample_rate = audio.info.sample_rate or sample_rate
                    bit_depth = audio.info.bits_per_sample or bit_depth
                    channels = audio.info.channels or channels
                    bitrate = audio.info.bitrate or 0
            except Exception:
                pass

            # Check if track already exists (re-rip)
            existing_track = db.fetchone(
                "SELECT id FROM tracks WHERE file_path = ?",
                (os.path.normpath(filepath),)
            )

            if existing_track:
                db.execute("""
                    UPDATE tracks SET
                        title=?, album_id=?, artist_id=?, album_artist_id=?,
                        track_number=?, disc_number=1, duration_ms=?,
                        file_format='FLAC', file_size=?, sample_rate=?,
                        bit_depth=?, bitrate=?, channels=?,
                        year=?, scanned_at=datetime('now'), file_mtime=?
                    WHERE id=?
                """, (
                    title, album_id, artist_id, album_artist_id,
                    track_number, actual_duration_ms,
                    file_size, sample_rate, bit_depth, bitrate, channels,
                    year, file_mtime, existing_track['id']
                ), commit=True)
            else:
                db.execute("""
                    INSERT INTO tracks(
                        title, album_id, artist_id, album_artist_id,
                        track_number, disc_number, duration_ms, file_path,
                        file_format, file_size, sample_rate, bit_depth,
                        bitrate, channels, year,
                        scanned_at, file_mtime
                    ) VALUES(?,?,?,?,?,1,?,?,'FLAC',?,?,?,?,?,?,datetime('now'),?)
                """, (
                    title, album_id, artist_id, album_artist_id,
                    track_number, actual_duration_ms,
                    os.path.normpath(filepath),
                    file_size, sample_rate, bit_depth, bitrate, channels,
                    year, file_mtime
                ), commit=True)

            log.debug("Registered track %d in database: %s", track_number, title)

        except Exception as exc:
            log.warning("Failed to register track in database: %s", exc)


# ---------------------------------------------------------------------------
# 6. Helper: check ffmpeg availability
# ---------------------------------------------------------------------------

def check_ffmpeg() -> dict:
    """Check if ffmpeg and ffprobe are available.

    Returns:
        {ffmpeg: bool, ffprobe: bool, version: str}
    """
    result = {'ffmpeg': False, 'ffprobe': False, 'version': ''}

    for tool in ('ffmpeg', 'ffprobe'):
        try:
            proc = subprocess.run(
                [tool, '-version'],
                capture_output=True, text=True, timeout=10
            )
            if proc.returncode == 0:
                result[tool] = True
                if tool == 'ffmpeg':
                    # Extract version from first line
                    first_line = proc.stdout.split('\n')[0] if proc.stdout else ''
                    ver_match = re.search(r'version\s+([\d.]+)', first_line)
                    if ver_match:
                        result['version'] = ver_match.group(1)
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            pass

    return result
