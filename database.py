"""Thread-safe SQLite database for MusicOthèque."""
import sqlite3
import threading
import os
import logging

log = logging.getLogger(__name__)

_local = threading.local()
_db_path = None
_lock = threading.Lock()

SCHEMA_VERSION = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    sort_name TEXT,
    musicbrainz_id TEXT UNIQUE,
    image_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);
CREATE INDEX IF NOT EXISTS idx_artists_sort ON artists(sort_name);

CREATE TABLE IF NOT EXISTS albums (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    artist_id INTEGER REFERENCES artists(id) ON DELETE SET NULL,
    year INTEGER,
    genre TEXT,
    musicbrainz_id TEXT UNIQUE,
    cover_path TEXT,
    cover_data BLOB,
    total_tracks INTEGER DEFAULT 0,
    total_discs INTEGER DEFAULT 1,
    folder_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_albums_title ON albums(title);
CREATE INDEX IF NOT EXISTS idx_albums_artist ON albums(artist_id);
CREATE INDEX IF NOT EXISTS idx_albums_year ON albums(year);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    album_id INTEGER REFERENCES albums(id) ON DELETE SET NULL,
    artist_id INTEGER REFERENCES artists(id) ON DELETE SET NULL,
    album_artist_id INTEGER REFERENCES artists(id) ON DELETE SET NULL,
    track_number INTEGER DEFAULT 0,
    disc_number INTEGER DEFAULT 1,
    duration_ms INTEGER DEFAULT 0,
    file_path TEXT NOT NULL UNIQUE,
    file_format TEXT,
    file_size INTEGER DEFAULT 0,
    sample_rate INTEGER DEFAULT 0,
    bit_depth INTEGER DEFAULT 0,
    bitrate INTEGER DEFAULT 0,
    channels INTEGER DEFAULT 2,
    genre TEXT,
    year INTEGER,
    composer TEXT,
    musicbrainz_id TEXT,
    lyrics TEXT,
    play_count INTEGER DEFAULT 0,
    last_played TIMESTAMP,
    rating INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scanned_at TIMESTAMP,
    file_mtime REAL DEFAULT 0,
    -- Classification (music_classifier)
    period TEXT,
    form TEXT,
    catalogue TEXT,
    instruments TEXT,
    music_key TEXT,
    movement TEXT,
    sub_period TEXT
);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album_id);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(file_path);
CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);
CREATE INDEX IF NOT EXISTS idx_tracks_album_artist ON tracks(album_artist_id);

CREATE TABLE IF NOT EXISTS playlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    source TEXT DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL REFERENCES tracks(id) ON DELETE CASCADE,
    position INTEGER DEFAULT 0,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(playlist_id, track_id)
);
CREATE INDEX IF NOT EXISTS idx_pt_playlist ON playlist_tracks(playlist_id);
CREATE INDEX IF NOT EXISTS idx_pt_track ON playlist_tracks(track_id);

CREATE TABLE IF NOT EXISTS scan_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    last_scan TIMESTAMP,
    auto_scan INTEGER DEFAULT 1
);

-- Full-text search (contentless: triggers maintain data, rebuild via rebuild_fts)
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title, artist_name, album_title, genre, composer,
    content='',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
    INSERT INTO tracks_fts(rowid, title, artist_name, album_title, genre, composer)
    VALUES (
        new.id, new.title,
        COALESCE((SELECT name FROM artists WHERE id = new.artist_id), ''),
        COALESCE((SELECT title FROM albums WHERE id = new.album_id), ''),
        COALESCE(new.genre, ''),
        COALESCE(new.composer, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist_name, album_title, genre, composer)
    VALUES (
        'delete', old.id, old.title,
        COALESCE((SELECT name FROM artists WHERE id = old.artist_id), ''),
        COALESCE((SELECT title FROM albums WHERE id = old.album_id), ''),
        COALESCE(old.genre, ''),
        COALESCE(old.composer, '')
    );
END;

CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, title, artist_name, album_title, genre, composer)
    VALUES (
        'delete', old.id, old.title,
        COALESCE((SELECT name FROM artists WHERE id = old.artist_id), ''),
        COALESCE((SELECT title FROM albums WHERE id = old.album_id), ''),
        COALESCE(old.genre, ''),
        COALESCE(old.composer, '')
    );
    INSERT INTO tracks_fts(rowid, title, artist_name, album_title, genre, composer)
    VALUES (
        new.id, new.title,
        COALESCE((SELECT name FROM artists WHERE id = new.artist_id), ''),
        COALESCE((SELECT title FROM albums WHERE id = new.album_id), ''),
        COALESCE(new.genre, ''),
        COALESCE(new.composer, '')
    );
END;

-- Podcasts
CREATE TABLE IF NOT EXISTS podcasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    description TEXT,
    feed_url TEXT UNIQUE,
    image_url TEXT,
    image_data BLOB,
    link TEXT,
    category TEXT,
    language TEXT,
    last_checked TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_podcasts_title ON podcasts(title);

CREATE TABLE IF NOT EXISTS podcast_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    podcast_id INTEGER NOT NULL REFERENCES podcasts(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    guid TEXT,
    published_at TIMESTAMP,
    duration_ms INTEGER DEFAULT 0,
    file_url TEXT,
    file_path TEXT,
    file_size INTEGER DEFAULT 0,
    file_format TEXT,
    episode_type TEXT,
    listened INTEGER DEFAULT 0,
    listened_at TIMESTAMP,
    downloaded INTEGER DEFAULT 0,
    downloaded_at TIMESTAMP,
    position_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(podcast_id, guid)
);
CREATE INDEX IF NOT EXISTS idx_episodes_podcast ON podcast_episodes(podcast_id);
CREATE INDEX IF NOT EXISTS idx_episodes_date ON podcast_episodes(published_at);

-- Full-text search for podcast episodes
CREATE VIRTUAL TABLE IF NOT EXISTS episodes_fts USING fts5(
    title, podcast_title, description,
    content=podcast_episodes,
    content_rowid=id,
    tokenize='unicode61 remove_diacritics 2'
);

-- Harmonization log (track changes for undo)
CREATE TABLE IF NOT EXISTS harmonization_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_harm_log_table ON harmonization_log(table_name, record_id);

-- CD rip history
CREATE TABLE IF NOT EXISTS cd_rip_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    disc_id TEXT,
    album_title TEXT,
    artist TEXT,
    track_count INTEGER,
    output_dir TEXT,
    ripped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def init(db_path):
    """Initialize database path."""
    global _db_path
    _db_path = db_path
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA)
    # Schema migrations
    _migrate(conn)
    # Set schema version
    conn.execute("INSERT OR REPLACE INTO config(key, value) VALUES('schema_version', ?)",
                 (str(SCHEMA_VERSION),))
    conn.commit()
    # Optimize query planner statistics
    try:
        conn.execute("PRAGMA optimize")
    except Exception:
        pass
    log.info("Database initialized at %s (schema v%d)", db_path, SCHEMA_VERSION)


def _migrate(conn):
    """Run schema migrations for existing databases."""
    # Check existing columns in tracks table
    cursor = conn.execute("PRAGMA table_info(tracks)")
    columns = {row[1] for row in cursor.fetchall()}

    # v3: Add classification columns
    # v4: Add movement and sub_period columns
    new_cols = {
        'period': 'TEXT',
        'form': 'TEXT',
        'catalogue': 'TEXT',
        'instruments': 'TEXT',
        'music_key': 'TEXT',
        'movement': 'TEXT',
        'sub_period': 'TEXT',
    }
    # SAFETY: col and typ are from hardcoded new_cols dict above — never user input.
    # SQLite does not support parameterized DDL (column names), so f-string is required here.
    for col, typ in new_cols.items():
        if col not in columns:
            conn.execute(f"ALTER TABLE tracks ADD COLUMN {col} {typ}")
            log.info("Migration: added column tracks.%s", col)
    conn.commit()


def get_connection():
    """Get thread-local database connection."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        if _db_path is None:
            raise RuntimeError("Database not initialized. Call database.init() first.")
        conn = sqlite3.connect(_db_path, timeout=120)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-16000")  # 16MB cache (improved from 8MB)
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")   # Temp tables in memory
        conn.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
        conn.execute("PRAGMA busy_timeout=120000")  # 120s busy timeout
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return _local.conn


def close_connection():
    """Close thread-local connection."""
    if hasattr(_local, 'conn') and _local.conn is not None:
        try:
            _local.conn.close()
        except Exception:
            pass
        _local.conn = None


def execute(sql, params=(), commit=False):
    """Execute SQL with thread safety and automatic retry on lock."""
    import time
    for attempt in range(3):
        try:
            conn = get_connection()
            with _lock:
                cursor = conn.execute(sql, params)
                if commit:
                    conn.commit()
                return cursor
        except sqlite3.OperationalError as e:
            if 'locked' in str(e) and attempt < 2:
                log.warning("DB locked (attempt %d/3), retrying in 2s...", attempt + 1)
                time.sleep(2)
            else:
                raise


def executemany(sql, params_list, commit=True):
    """Execute many with thread safety."""
    conn = get_connection()
    with _lock:
        cursor = conn.executemany(sql, params_list)
        if commit:
            conn.commit()
        return cursor


def commit():
    """Commit current transaction."""
    conn = get_connection()
    with _lock:
        conn.commit()


def fetchone(sql, params=()):
    """Fetch one row."""
    cursor = execute(sql, params)
    return cursor.fetchone() if cursor else None


def fetchall(sql, params=()):
    """Fetch all rows."""
    cursor = execute(sql, params)
    return cursor.fetchall() if cursor else []


def rebuild_fts():
    """Rebuild the FTS5 search index from scratch.

    Contentless FTS5 tables (content='') do not support DELETE.
    Must DROP + CREATE + re-INSERT to rebuild.
    """
    conn = get_connection()
    with _lock:
        # Drop triggers, FTS table, then recreate
        conn.execute("DROP TRIGGER IF EXISTS tracks_ai")
        conn.execute("DROP TRIGGER IF EXISTS tracks_ad")
        conn.execute("DROP TRIGGER IF EXISTS tracks_au")
        conn.execute("DROP TABLE IF EXISTS tracks_fts")
        conn.execute("""
            CREATE VIRTUAL TABLE tracks_fts USING fts5(
                title, artist_name, album_title, genre, composer,
                content='',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        # Recreate triggers
        conn.execute("""
            CREATE TRIGGER tracks_ai AFTER INSERT ON tracks BEGIN
                INSERT INTO tracks_fts(rowid, title, artist_name, album_title, genre, composer)
                VALUES (
                    new.id, new.title,
                    COALESCE((SELECT name FROM artists WHERE id = new.artist_id), ''),
                    COALESCE((SELECT title FROM albums WHERE id = new.album_id), ''),
                    COALESCE(new.genre, ''),
                    COALESCE(new.composer, '')
                );
            END
        """)
        conn.execute("""
            CREATE TRIGGER tracks_ad AFTER DELETE ON tracks BEGIN
                INSERT INTO tracks_fts(tracks_fts, rowid, title, artist_name, album_title, genre, composer)
                VALUES (
                    'delete', old.id, old.title,
                    COALESCE((SELECT name FROM artists WHERE id = old.artist_id), ''),
                    COALESCE((SELECT title FROM albums WHERE id = old.album_id), ''),
                    COALESCE(old.genre, ''),
                    COALESCE(old.composer, '')
                );
            END
        """)
        conn.execute("""
            CREATE TRIGGER tracks_au AFTER UPDATE ON tracks BEGIN
                INSERT INTO tracks_fts(tracks_fts, rowid, title, artist_name, album_title, genre, composer)
                VALUES (
                    'delete', old.id, old.title,
                    COALESCE((SELECT name FROM artists WHERE id = old.artist_id), ''),
                    COALESCE((SELECT title FROM albums WHERE id = old.album_id), ''),
                    COALESCE(old.genre, ''),
                    COALESCE(old.composer, '')
                );
                INSERT INTO tracks_fts(rowid, title, artist_name, album_title, genre, composer)
                VALUES (
                    new.id, new.title,
                    COALESCE((SELECT name FROM artists WHERE id = new.artist_id), ''),
                    COALESCE((SELECT title FROM albums WHERE id = new.album_id), ''),
                    COALESCE(new.genre, ''),
                    COALESCE(new.composer, '')
                );
            END
        """)
        # Re-populate index from joined data
        conn.execute("""
            INSERT INTO tracks_fts(rowid, title, artist_name, album_title, genre, composer)
            SELECT t.id, COALESCE(t.title, ''),
                   COALESCE(a.name, ''),
                   COALESCE(al.title, ''),
                   COALESCE(t.genre, ''),
                   COALESCE(t.composer, '')
            FROM tracks t
            LEFT JOIN artists a ON t.artist_id = a.id
            LEFT JOIN albums al ON t.album_id = al.id
        """)
        conn.commit()
    log.info("FTS5 index rebuilt")


def search_tracks(query, limit=200):
    """Full-text search on tracks."""
    if not query or len(query.strip()) < 2:
        return []
    # Sanitize limit
    limit = max(1, min(1000, int(limit)))
    # Escape FTS special chars (prevent FTS injection)
    safe_q = query.replace('"', '""').replace("'", "''").strip()
    # Remove FTS operators that could cause errors
    for char in ['*', '(', ')', '{', '}', '^', '~']:
        safe_q = safe_q.replace(char, '')
    if not safe_q:
        return []
    sql = """
        SELECT t.*, a.name as artist_name, al.title as album_title, al.id as _album_id
        FROM tracks_fts fts
        JOIN tracks t ON t.id = fts.rowid
        LEFT JOIN artists a ON t.artist_id = a.id
        LEFT JOIN albums al ON t.album_id = al.id
        WHERE tracks_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """
    try:
        return fetchall(sql, (f'"{safe_q}"*', limit))
    except sqlite3.OperationalError:
        # Fallback to LIKE search — escape wildcards in user input
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        like = f"%{escaped}%"
        return fetchall("""
            SELECT t.*, a.name as artist_name, al.title as album_title, al.id as _album_id
            FROM tracks t
            LEFT JOIN artists a ON t.artist_id = a.id
            LEFT JOIN albums al ON t.album_id = al.id
            WHERE t.title LIKE ? ESCAPE '\\' OR a.name LIKE ? ESCAPE '\\' OR al.title LIKE ? ESCAPE '\\'
            ORDER BY a.name, al.year, t.disc_number, t.track_number
            LIMIT ?
        """, (like, like, like, limit))


# --- High-level helpers ---

def get_or_create_artist(name):
    """Get artist ID by name, create if not exists."""
    if not name:
        name = "Unknown Artist"
    row = fetchone("SELECT id FROM artists WHERE name = ?", (name,))
    if row:
        return row['id']
    # Create sort name (Last, First for western names)
    sort_name = name
    parts = name.split()
    if len(parts) == 2 and all(p[0].isupper() for p in parts if p):
        sort_name = f"{parts[-1]}, {' '.join(parts[:-1])}"
    execute("INSERT INTO artists(name, sort_name) VALUES(?, ?)", (name, sort_name), commit=True)
    return fetchone("SELECT last_insert_rowid() as id")['id']


def get_or_create_album(title, artist_id, year=None, folder_path=None):
    """Get album ID, create if not exists."""
    if not title:
        title = "Unknown Album"
    row = fetchone(
        "SELECT id FROM albums WHERE title = ? AND artist_id = ?",
        (title, artist_id)
    )
    if row:
        return row['id']
    execute(
        "INSERT INTO albums(title, artist_id, year, folder_path) VALUES(?, ?, ?, ?)",
        (title, artist_id, year, folder_path), commit=True
    )
    return fetchone("SELECT last_insert_rowid() as id")['id']


def get_library_stats():
    """Get library statistics (single query)."""
    row = fetchone("""
        SELECT
            (SELECT COUNT(*) FROM tracks) as tracks,
            (SELECT COUNT(*) FROM albums) as albums,
            (SELECT COUNT(*) FROM artists) as artists,
            (SELECT COALESCE(SUM(duration_ms), 0) FROM tracks) as total_duration_ms,
            (SELECT COALESCE(SUM(file_size), 0) FROM tracks) as total_size,
            (SELECT COUNT(*) FROM playlists) as playlists,
            (SELECT COUNT(*) FROM podcasts) as podcasts,
            (SELECT COUNT(*) FROM podcast_episodes) as episodes,
            (SELECT COUNT(*) FROM podcast_episodes WHERE file_path IS NOT NULL) as episodes_downloaded
    """)
    if row:
        return dict(row)
    return {
        'tracks': 0, 'albums': 0, 'artists': 0,
        'total_duration_ms': 0, 'total_size': 0,
        'playlists': 0, 'podcasts': 0, 'episodes': 0,
        'episodes_downloaded': 0
    }


def get_or_create_podcast(title, feed_url=None, author=None):
    """Get podcast ID by title, create if not exists."""
    if feed_url:
        row = fetchone("SELECT id FROM podcasts WHERE feed_url = ?", (feed_url,))
        if row:
            return row['id']
    row = fetchone("SELECT id FROM podcasts WHERE title = ?", (title,))
    if row:
        return row['id']
    execute(
        "INSERT INTO podcasts(title, feed_url, author) VALUES(?, ?, ?)",
        (title, feed_url, author), commit=True
    )
    return fetchone("SELECT last_insert_rowid() as id")['id']


def search_episodes(query, limit=200):
    """Full-text search on podcast episodes."""
    if not query or len(query.strip()) < 2:
        return []
    # Sanitize limit
    limit = max(1, min(1000, int(limit)))
    # Escape FTS special chars
    safe_q = query.replace('"', '""').replace("'", "''").strip()
    for char in ['*', '(', ')', '{', '}', '^', '~']:
        safe_q = safe_q.replace(char, '')
    if not safe_q:
        return []
    try:
        return fetchall("""
            SELECT e.*, p.title as podcast_title, p.image_data
            FROM episodes_fts fts
            JOIN podcast_episodes e ON e.id = fts.rowid
            LEFT JOIN podcasts p ON e.podcast_id = p.id
            WHERE episodes_fts MATCH ?
            ORDER BY rank LIMIT ?
        """, (f'"{safe_q}"*', limit))
    except Exception:
        escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        like = f"%{escaped}%"
        return fetchall("""
            SELECT e.*, p.title as podcast_title, p.image_data
            FROM podcast_episodes e
            LEFT JOIN podcasts p ON e.podcast_id = p.id
            WHERE e.title LIKE ? ESCAPE '\\' OR p.title LIKE ? ESCAPE '\\'
            ORDER BY e.published_at DESC LIMIT ?
        """, (like, like, limit))


# --- Path relocation ---

def relocate_paths(old_prefix, new_prefix):
    """Relocate all file paths matching old_prefix to new_prefix.

    Useful when music library moves (e.g., Windows→Linux, drive letter change).
    Uses parameterized queries for safety.
    Returns count of updated rows.
    """
    # Normalize separators
    old_prefix = old_prefix.replace('\\', '/')
    new_prefix = new_prefix.replace('\\', '/')

    # Update tracks — escape LIKE wildcards in prefix, then match
    like_prefix = old_prefix.replace('%', '\\%').replace('_', '\\_') + '%'
    rows = fetchall(
        "SELECT id, file_path FROM tracks WHERE replace(file_path, '\\', '/') LIKE ? ESCAPE '\\'",
        (like_prefix,)
    )
    count = 0
    for row in rows:
        fp = row['file_path'].replace('\\', '/')
        if fp.startswith(old_prefix):
            new_path = new_prefix + fp[len(old_prefix):]
            # Convert back to OS-native separators
            new_path = os.path.normpath(new_path)
            execute(
                "UPDATE tracks SET file_path = ? WHERE id = ?",
                (new_path, row['id']), commit=False
            )
            count += 1

    # Update albums folder_path
    album_rows = fetchall(
        "SELECT id, folder_path FROM albums WHERE folder_path IS NOT NULL"
    )
    for row in album_rows:
        fp = (row['folder_path'] or '').replace('\\', '/')
        if fp.startswith(old_prefix):
            new_path = new_prefix + fp[len(old_prefix):]
            new_path = os.path.normpath(new_path)
            execute(
                "UPDATE albums SET folder_path = ? WHERE id = ?",
                (new_path, row['id']), commit=False
            )

    # Update scan_folders
    folder_rows = fetchall("SELECT id, path FROM scan_folders")
    for row in folder_rows:
        fp = (row['path'] or '').replace('\\', '/')
        if fp.startswith(old_prefix):
            new_path = new_prefix + fp[len(old_prefix):]
            new_path = os.path.normpath(new_path)
            execute(
                "UPDATE scan_folders SET path = ? WHERE id = ?",
                (new_path, row['id']), commit=False
            )

    if count:
        commit()
    log.info("Relocated %d track paths: %s -> %s", count, old_prefix, new_prefix)
    return count


def find_broken_paths():
    """Find tracks whose files no longer exist on disk.

    Uses parallel file existence checks for performance on large libraries.
    """
    from concurrent.futures import ThreadPoolExecutor
    rows = fetchall("SELECT id, file_path, title FROM tracks")
    if not rows:
        return []

    def _check(row):
        if not os.path.exists(row['file_path']):
            return {'id': row['id'], 'file_path': row['file_path'], 'title': row['title']}
        return None

    broken = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for result in pool.map(_check, rows):
            if result:
                broken.append(result)
    return broken


def export_library(output_path):
    """Export library metadata to JSON for portability."""
    import json
    # Validate output path (anti path traversal)
    output_path = os.path.normpath(os.path.abspath(output_path))
    if '..' in output_path.split(os.sep):
        raise ValueError("Path traversal detected in output path")
    data = {
        'tracks': [],
        'playlists': [],
        'scan_folders': [],
    }

    tracks = fetchall("""
        SELECT t.*, a.name as artist_name, al.title as album_title
        FROM tracks t
        LEFT JOIN artists a ON t.artist_id = a.id
        LEFT JOIN albums al ON t.album_id = al.id
        ORDER BY t.id
    """)
    for t in tracks:
        data['tracks'].append({
            'title': t['title'],
            'artist': t['artist_name'],
            'album': t['album_title'],
            'file_path': t['file_path'],
            'track_number': t['track_number'],
            'disc_number': t['disc_number'],
            'genre': t['genre'],
            'year': t['year'],
            'play_count': t['play_count'],
            'rating': t['rating'],
        })

    playlists = fetchall("SELECT * FROM playlists ORDER BY name")
    for pl in playlists:
        pl_tracks = fetchall(
            "SELECT t.file_path FROM playlist_tracks pt "
            "JOIN tracks t ON pt.track_id = t.id "
            "WHERE pt.playlist_id = ? ORDER BY pt.position",
            (pl['id'],)
        )
        data['playlists'].append({
            'name': pl['name'],
            'source': pl['source'],
            'tracks': [t['file_path'] for t in pl_tracks],
        })

    folders = fetchall("SELECT path FROM scan_folders")
    data['scan_folders'] = [f['path'] for f in folders]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info("Library exported to %s (%d tracks)", output_path, len(data['tracks']))
    return len(data['tracks'])
