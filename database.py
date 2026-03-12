"""Thread-safe SQLite database for MusicOthèque."""
import sqlite3
import threading
import os
import logging

log = logging.getLogger(__name__)

_local = threading.local()
_db_path = None
_lock = threading.Lock()

SCHEMA_VERSION = 1

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
    file_mtime REAL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album_id);
CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist_id);
CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(file_path);
CREATE INDEX IF NOT EXISTS idx_tracks_genre ON tracks(genre);

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

-- Full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title, artist_name, album_title, genre, composer,
    content=tracks,
    content_rowid=id,
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
    # Set schema version
    conn.execute("INSERT OR REPLACE INTO config(key, value) VALUES('schema_version', ?)",
                 (str(SCHEMA_VERSION),))
    conn.commit()
    log.info("Database initialized at %s", db_path)


def get_connection():
    """Get thread-local database connection."""
    if not hasattr(_local, 'conn') or _local.conn is None:
        if _db_path is None:
            raise RuntimeError("Database not initialized. Call database.init() first.")
        conn = sqlite3.connect(_db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA cache_size=-8000")  # 8MB cache
        conn.execute("PRAGMA synchronous=NORMAL")
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
    """Execute SQL with thread safety."""
    conn = get_connection()
    with _lock:
        cursor = conn.execute(sql, params)
        if commit:
            conn.commit()
        return cursor


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
    return execute(sql, params).fetchone()


def fetchall(sql, params=()):
    """Fetch all rows."""
    return execute(sql, params).fetchall()


def search_tracks(query, limit=200):
    """Full-text search on tracks."""
    if not query or len(query.strip()) < 2:
        return []
    # Escape FTS special chars
    safe_q = query.replace('"', '""').strip()
    sql = """
        SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
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
        # Fallback to LIKE search
        like = f"%{query}%"
        return fetchall("""
            SELECT t.*, a.name as artist_name, al.title as album_title, al.cover_data
            FROM tracks t
            LEFT JOIN artists a ON t.artist_id = a.id
            LEFT JOIN albums al ON t.album_id = al.id
            WHERE t.title LIKE ? OR a.name LIKE ? OR al.title LIKE ?
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
    """Get library statistics."""
    stats = {}
    row = fetchone("SELECT COUNT(*) as c FROM tracks")
    stats['tracks'] = row['c'] if row else 0
    row = fetchone("SELECT COUNT(*) as c FROM albums")
    stats['albums'] = row['c'] if row else 0
    row = fetchone("SELECT COUNT(*) as c FROM artists")
    stats['artists'] = row['c'] if row else 0
    row = fetchone("SELECT SUM(duration_ms) as d FROM tracks")
    stats['total_duration_ms'] = row['d'] or 0 if row else 0
    row = fetchone("SELECT SUM(file_size) as s FROM tracks")
    stats['total_size'] = row['s'] or 0 if row else 0
    row = fetchone("SELECT COUNT(*) as c FROM playlists")
    stats['playlists'] = row['c'] if row else 0
    return stats
