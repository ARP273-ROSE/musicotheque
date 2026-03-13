"""Smart Library Manager — autonomous scan, harmonize, classify, playlist.

Run standalone to process the entire music library:
  python smart_library.py [folder_path]

Performs:
1. Full scan with mutagen metadata extraction
2. Composer/artist/genre harmonization
3. Classical music classification (period, form, catalogue, instruments, key)
4. Smart playlist generation
5. FTS5 index rebuild
"""
import os
import sys
import time
import logging
import json
import sqlite3
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger(__name__)

# Setup standalone logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S',
    handlers=[logging.StreamHandler(sys.stdout)]
)


def scan_folder(folder, batch_size=200):
    """Scan a folder for audio files and import them into the database.

    Returns (added, updated, skipped, errors).
    """
    import database as db
    from scanner import read_metadata, AUDIO_EXTENSIONS, _SKIP_DIRS, _JUNK_WORDS

    # Collect all audio files
    log.info("Collecting audio files from %s ...", folder)
    all_files = []
    skip = _SKIP_DIRS | _JUNK_WORDS
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in skip]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in AUDIO_EXTENSIONS:
                fp = os.path.join(root, f)
                try:
                    if os.path.getsize(fp) < 10240:
                        continue
                except OSError:
                    continue
                all_files.append(fp)

    total = len(all_files)
    log.info("Found %d audio files", total)

    # Get existing tracks
    existing = {}
    for row in db.fetchall("SELECT file_path, file_mtime FROM tracks"):
        existing[os.path.normpath(row['file_path'])] = row['file_mtime']

    added = 0
    updated = 0
    skipped = 0
    errors = 0
    t0 = time.time()

    for i, fpath in enumerate(all_files):
        norm_path = os.path.normpath(fpath)

        # Skip unchanged
        try:
            mtime = os.path.getmtime(fpath)
        except OSError:
            errors += 1
            continue

        if norm_path in existing:
            if abs(existing[norm_path] - mtime) < 1:
                skipped += 1
                if (skipped + added + updated) % 5000 == 0:
                    log.info("  %d/%d (added=%d, skipped=%d) %.0fs",
                             i + 1, total, added, skipped, time.time() - t0)
                continue

        # Read metadata
        meta = read_metadata(fpath)
        if meta is None:
            errors += 1
            continue

        # Retry wrapper for DB operations (handles "database is locked")
        for _attempt in range(5):
            try:
                # Get or create artist
                artist_name = meta['artist'] or 'Unknown Artist'
                artist_id = db.get_or_create_artist(artist_name)

                # Album artist
                album_artist_name = meta['album_artist'] or artist_name
                album_artist_id = (db.get_or_create_artist(album_artist_name)
                                   if album_artist_name != artist_name else artist_id)

                # Album
                album_title = meta['album'] or 'Unknown Album'
                album_id = db.get_or_create_album(
                    album_title, album_artist_id, meta['year'],
                    os.path.dirname(fpath)
                )

                # Cover art
                if meta['cover_data']:
                    existing_cover = db.fetchone(
                        "SELECT cover_data FROM albums WHERE id = ?", (album_id,))
                    if existing_cover and not existing_cover['cover_data']:
                        db.execute("UPDATE albums SET cover_data = ? WHERE id = ?",
                                   (meta['cover_data'], album_id), commit=False)

                # Update album metadata
                db.execute("""
                    UPDATE albums SET
                        year = COALESCE(?, year),
                        genre = COALESCE(?, genre),
                        total_tracks = MAX(COALESCE(total_tracks, 0), ?),
                        total_discs = MAX(COALESCE(total_discs, 1), ?)
                    WHERE id = ?
                """, (meta['year'], meta['genre'], meta['track_number'],
                      meta['disc_number'], album_id), commit=False)

                # Insert or update track
                if norm_path in existing:
                    db.execute("""
                        UPDATE tracks SET
                            title=?, album_id=?, artist_id=?, album_artist_id=?,
                            track_number=?, disc_number=?, duration_ms=?,
                            file_format=?, file_size=?, sample_rate=?, bit_depth=?,
                            bitrate=?, channels=?, genre=?, year=?, composer=?,
                            scanned_at=datetime('now'), file_mtime=?
                        WHERE file_path=?
                    """, (
                        meta['title'], album_id, artist_id, album_artist_id,
                        meta['track_number'], meta['disc_number'], meta['duration_ms'],
                        meta['file_format'], meta['file_size'], meta['sample_rate'],
                        meta['bit_depth'], meta['bitrate'], meta['channels'],
                        meta['genre'], meta['year'], meta['composer'],
                        mtime, norm_path
                    ), commit=False)
                    updated += 1
                else:
                    try:
                        db.execute("""
                            INSERT INTO tracks(
                                title, album_id, artist_id, album_artist_id,
                                track_number, disc_number, duration_ms, file_path,
                                file_format, file_size, sample_rate, bit_depth,
                                bitrate, channels, genre, year, composer,
                                scanned_at, file_mtime
                            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),?)
                        """, (
                            meta['title'], album_id, artist_id, album_artist_id,
                            meta['track_number'], meta['disc_number'], meta['duration_ms'],
                            norm_path, meta['file_format'], meta['file_size'],
                            meta['sample_rate'], meta['bit_depth'], meta['bitrate'],
                            meta['channels'], meta['genre'], meta['year'], meta['composer'],
                            mtime
                        ), commit=False)
                        added += 1
                    except Exception:
                        # Duplicate path (case-insensitive match on Windows)
                        skipped += 1
                break  # Success, exit retry loop
            except sqlite3.OperationalError as e:
                if 'locked' in str(e) and _attempt < 4:
                    wait = 2 ** _attempt  # Exponential backoff: 1, 2, 4, 8s
                    log.warning("DB locked at %d/%d, retry %d/5 in %ds...",
                                i + 1, total, _attempt + 2, wait)
                    time.sleep(wait)
                else:
                    raise

        # Batch commit
        if (added + updated) % batch_size == 0:
            db.commit()
            if (added + updated) % 2000 == 0:
                log.info("  %d/%d (added=%d, updated=%d) %.0fs",
                         i + 1, total, added, updated, time.time() - t0)

    db.commit()
    elapsed = time.time() - t0
    log.info("Scan complete: added=%d, updated=%d, skipped=%d, errors=%d (%.0fs)",
             added, updated, skipped, errors, elapsed)
    return added, updated, skipped, errors


def harmonize_all(write_to_files=True):
    """Harmonize all composers, genres, and artist names in the database.

    Args:
        write_to_files: If True, also write corrected composer/genre back to
                        the audio files' metadata tags (mutagen).
    """
    import database as db
    from harmonizer import (normalize_composer, normalize_genre,
                            normalize_artist, normalize_album_title,
                            COMPOSER_ALIASES, _GENRE_MAP)
    if write_to_files:
        from scanner import write_metadata

    log.info("=== HARMONIZATION ===")
    total_fixed = 0
    files_written = 0

    # --- Phase 1: Composer normalization ---
    log.info("Phase 1: Composer normalization...")
    composers = db.fetchall(
        "SELECT DISTINCT composer FROM tracks WHERE composer IS NOT NULL AND composer != ''")
    comp_fixes = 0
    for row in composers:
        comp = row['composer']
        result = normalize_composer(comp)
        if result['changed']:
            # Get affected tracks for file writing
            affected = db.fetchall(
                'SELECT id, file_path FROM tracks WHERE composer = ?', (comp,))
            db.execute('UPDATE tracks SET composer = ? WHERE composer = ?',
                       (result['canonical'], comp), commit=False)
            comp_fixes += len(affected)
            # Write to files
            if write_to_files:
                for t in affected:
                    if write_metadata(t['file_path'], {'composer': result['canonical']}):
                        files_written += 1
    db.commit()
    log.info("  Composers: %d tracks fixed", comp_fixes)
    total_fixed += comp_fixes

    # --- Phase 2: Genre normalization ---
    log.info("Phase 2: Genre normalization...")
    genres = db.fetchall(
        "SELECT DISTINCT genre FROM tracks WHERE genre IS NOT NULL")
    genre_fixes = 0
    for row in genres:
        genre = row['genre']
        if not genre or not genre.strip():
            cnt = db.fetchone(
                'SELECT COUNT(*) as c FROM tracks WHERE genre = ?', (genre,))
            db.execute('UPDATE tracks SET genre = NULL WHERE genre = ?',
                       (genre,), commit=False)
            genre_fixes += cnt['c']
            continue
        result = normalize_genre(genre)
        if result['changed']:
            affected = db.fetchall(
                'SELECT id, file_path FROM tracks WHERE genre = ?', (genre,))
            db.execute('UPDATE tracks SET genre = ? WHERE genre = ?',
                       (result['normalized'], genre), commit=False)
            genre_fixes += len(affected)
            if write_to_files:
                for t in affected:
                    if write_metadata(t['file_path'], {'genre': result['normalized']}):
                        files_written += 1
    db.commit()
    log.info("  Genres: %d tracks fixed", genre_fixes)
    total_fixed += genre_fixes

    # --- Phase 3: Artist normalization ---
    log.info("Phase 3: Artist normalization...")
    artists = db.fetchall("SELECT id, name FROM artists")
    artist_fixes = 0
    for row in artists:
        result = normalize_artist(row['name'])
        if result['changed']:
            old_name = row['name']
            new_name = result['normalized']
            db.execute('UPDATE artists SET name = ? WHERE id = ?',
                       (new_name, row['id']), commit=False)
            artist_fixes += 1
            # Write to all tracks by this artist
            if write_to_files:
                affected_tracks = db.fetchall(
                    'SELECT file_path FROM tracks WHERE artist_id = ?',
                    (row['id'],))
                for t in affected_tracks:
                    if write_metadata(t['file_path'], {'artist': new_name}):
                        files_written += 1
    db.commit()
    log.info("  Artists: %d names fixed", artist_fixes)
    total_fixed += artist_fixes

    # --- Phase 4: Album title cleanup ---
    log.info("Phase 4: Album title cleanup...")
    albums = db.fetchall("SELECT id, title FROM albums")
    album_fixes = 0
    for row in albums:
        result = normalize_album_title(row['title'])
        if result['changed']:
            old_title = row['title']
            new_title = result['normalized']
            db.execute('UPDATE albums SET title = ? WHERE id = ?',
                       (new_title, row['id']), commit=False)
            album_fixes += 1
            # Write to all tracks in this album
            if write_to_files:
                affected_tracks = db.fetchall(
                    'SELECT file_path FROM tracks WHERE album_id = ?',
                    (row['id'],))
                for t in affected_tracks:
                    if write_metadata(t['file_path'], {'album': new_title}):
                        files_written += 1
    db.commit()
    log.info("  Albums: %d titles cleaned", album_fixes)
    total_fixed += album_fixes

    if write_to_files:
        log.info("  Files written: %d metadata tags updated", files_written)
    log.info("Harmonization complete: %d total fixes", total_fixed)
    return total_fixed


def classify_all(write_to_files=True):
    """Classify all tracks by period, form, catalogue, instruments, key,
    movement, and sub-period.

    Stores results in tracks table columns and optionally writes
    classification metadata to the audio files themselves.

    Args:
        write_to_files: If True, write classification tags to audio files.
    """
    import database as db
    from music_classifier import classify_track
    if write_to_files:
        from scanner import write_metadata

    log.info("=== CLASSIFICATION ===")

    # Get tracks that need classification (all, or only unclassified)
    tracks = db.fetchall("""
        SELECT t.id, t.title, t.composer, t.genre, t.year,
               al.title as album_title, t.file_path
        FROM tracks t
        LEFT JOIN albums al ON t.album_id = al.id
    """)

    total = len(tracks)
    classified = 0
    files_written = 0
    t0 = time.time()

    for i, track in enumerate(tracks):
        result = classify_track(
            title=track['title'] or '',
            composer=track['composer'] or '',
            genre=track['genre'] or '',
            album=track['album_title'] or '',
            year=track['year'],
        )

        # Only update if we found something
        has_data = (result['period'] or result['form'] or
                    result['catalogue'] or result['instruments'] or
                    result['key'] or result.get('movement') or
                    result.get('sub_period'))

        if has_data:
            instruments_str = ', '.join(result['instruments']) if result['instruments'] else None
            db.execute("""
                UPDATE tracks SET
                    period=?, form=?, catalogue=?, instruments=?, music_key=?,
                    movement=?, sub_period=?
                WHERE id=?
            """, (
                result['period'], result['form'], result['catalogue'],
                instruments_str, result['key'],
                result.get('movement'), result.get('sub_period'),
                track['id']
            ), commit=False)
            classified += 1

            # Write classification to file metadata
            if write_to_files and track['file_path']:
                file_updates = {}
                if result['period']:
                    file_updates['period'] = result['period']
                if result.get('movement'):
                    file_updates['movement'] = result['movement']
                if result.get('sub_period'):
                    file_updates['sub_period'] = result['sub_period']
                if result['form']:
                    file_updates['form'] = result['form']
                if result['catalogue']:
                    file_updates['catalogue'] = result['catalogue']
                if instruments_str:
                    file_updates['instruments'] = instruments_str
                if result['key']:
                    file_updates['music_key'] = result['key']
                if file_updates:
                    if write_metadata(track['file_path'], file_updates):
                        files_written += 1

        if (i + 1) % 5000 == 0:
            db.commit()
            log.info("  %d/%d classified (%.0fs)", i + 1, total, time.time() - t0)

    db.commit()
    elapsed = time.time() - t0
    log.info("Classification: %d/%d tracks classified (%.0fs)", classified, total, elapsed)
    if write_to_files:
        log.info("  Files written: %d metadata tags updated", files_written)

    # Stats
    period_stats = db.fetchall("""
        SELECT period, COUNT(*) as cnt FROM tracks
        WHERE period IS NOT NULL
        GROUP BY period ORDER BY cnt DESC
    """)
    log.info("Periods:")
    for p in period_stats:
        log.info("  %s: %d", p['period'], p['cnt'])

    form_stats = db.fetchall("""
        SELECT form, COUNT(*) as cnt FROM tracks
        WHERE form IS NOT NULL
        GROUP BY form ORDER BY cnt DESC LIMIT 15
    """)
    log.info("Top forms:")
    for f in form_stats:
        log.info("  %s: %d", f['form'], f['cnt'])

    # Movement stats
    movement_stats = db.fetchall("""
        SELECT movement, COUNT(*) as cnt FROM tracks
        WHERE movement IS NOT NULL
        GROUP BY movement ORDER BY cnt DESC
    """)
    if movement_stats:
        log.info("Movements/styles:")
        for m in movement_stats:
            log.info("  %s: %d", m['movement'], m['cnt'])

    return classified


def sync_metadata_to_files(batch_size=500):
    """Sync harmonized metadata from DB to audio files.

    Only writes to files where DB values differ from file tags.
    Processes in batches for efficiency and progress tracking.

    Returns (checked, written, errors, inaccessible).
    """
    import database as db
    from scanner import read_metadata, write_metadata

    log.info("=== SYNC METADATA → FILES ===")
    t0 = time.time()

    tracks = db.fetchall("""
        SELECT t.id, t.composer, t.genre, t.file_path
        FROM tracks t
        WHERE t.file_path IS NOT NULL
          AND (t.composer IS NOT NULL OR t.genre IS NOT NULL)
    """)

    total = len(tracks)
    checked = 0
    written = 0
    errors = 0
    inaccessible = 0

    for i, t in enumerate(tracks):
        path = t['file_path']
        if not os.path.exists(path):
            inaccessible += 1
            continue

        checked += 1
        try:
            meta = read_metadata(path)
            if not meta:
                errors += 1
                continue

            updates = {}
            if t['composer'] and meta.get('composer') and t['composer'] != meta['composer']:
                updates['composer'] = t['composer']
            if t['genre'] and meta.get('genre') and t['genre'] != meta['genre']:
                updates['genre'] = t['genre']

            if updates:
                if write_metadata(path, updates):
                    written += 1
                else:
                    errors += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                log.warning("  Error syncing %s: %s", os.path.basename(path), e)

        if (i + 1) % batch_size == 0:
            elapsed = time.time() - t0
            log.info("  %d/%d checked, %d written (%.0fs)", i + 1, total, written, elapsed)

    elapsed = time.time() - t0
    log.info("Sync complete: %d checked, %d written, %d errors, %d inaccessible (%.0fs)",
             checked, written, errors, inaccessible, elapsed)
    return checked, written, errors, inaccessible


def generate_smart_playlists():
    """Generate intelligent playlists based on metadata analysis.

    Creates playlists by:
    - Musical period (Baroque, Classical, Romantic, Modern, Contemporary)
    - Genre (Classical, Soundtrack, Jazz, etc.)
    - Composer (major composers with 50+ tracks)
    - Quality (Hi-Res, CD Quality, Lossless)
    - Musical form (Symphonies, Concertos, Sonatas, etc.)
    - Mood/theme (based on form + key analysis)
    """
    import database as db

    log.info("=== SMART PLAYLISTS ===")
    created = 0

    def _create_playlist(name, description, track_ids, source='auto'):
        """Create or update a playlist."""
        if not track_ids:
            return False
        # Check if exists
        existing = db.fetchone(
            "SELECT id FROM playlists WHERE name = ? AND source = ?",
            (name, source))
        if existing:
            # Clear and repopulate
            pl_id = existing['id']
            db.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?",
                       (pl_id,), commit=False)
        else:
            db.execute(
                "INSERT INTO playlists(name, description, source, updated_at) "
                "VALUES(?, ?, ?, datetime('now'))",
                (name, description, source), commit=False)
            db.commit()
            pl_id = db.fetchone("SELECT last_insert_rowid() as id")['id']

        # Add tracks
        for pos, tid in enumerate(track_ids):
            db.execute(
                "INSERT OR IGNORE INTO playlist_tracks(playlist_id, track_id, position) "
                "VALUES(?, ?, ?)",
                (pl_id, tid, pos), commit=False)
        db.commit()
        return True

    # --- Period playlists ---
    periods = ['Medieval', 'Renaissance', 'Baroque', 'Classical', 'Romantic',
               'Modern', 'Contemporary']
    period_descriptions = {
        'Medieval': 'Music from before 1400 — Gregorian chant, troubadours, ars nova',
        'Renaissance': 'Music 1400-1600 — Polyphony, madrigals, motets',
        'Baroque': 'Music 1600-1750 — Bach, Vivaldi, Handel — counterpoint, ornamentation',
        'Classical': 'Music 1750-1820 — Mozart, Haydn, Beethoven — clarity, balance',
        'Romantic': 'Music 1820-1900 — Chopin, Brahms, Wagner — emotion, virtuosity',
        'Modern': 'Music 1900-1950 — Debussy, Stravinsky, Bartók — innovation, new harmonies',
        'Contemporary': 'Music 1950-present — Glass, Pärt, Ligeti — minimalism, avant-garde',
    }
    for period in periods:
        tracks = db.fetchall(
            "SELECT id FROM tracks WHERE period = ? ORDER BY composer, year, title",
            (period,))
        ids = [t['id'] for t in tracks]
        if ids:
            name = f"♪ {period}"
            desc = period_descriptions.get(period, f"Music from the {period} period")
            if _create_playlist(name, desc, ids):
                log.info("  %s: %d tracks", name, len(ids))
                created += 1

    # --- Genre playlists ---
    genre_rows = db.fetchall("""
        SELECT genre, COUNT(*) as cnt FROM tracks
        WHERE genre IS NOT NULL
        GROUP BY genre HAVING cnt >= 20
        ORDER BY cnt DESC
    """)
    for row in genre_rows:
        genre = row['genre']
        tracks = db.fetchall(
            "SELECT id FROM tracks WHERE genre = ? ORDER BY artist_id, year, title",
            (genre,))
        ids = [t['id'] for t in tracks]
        if ids:
            name = f"⊕ {genre}"
            if _create_playlist(name, f"All {genre} tracks", ids):
                log.info("  %s: %d tracks", name, len(ids))
                created += 1

    # --- Major composer playlists ---
    composer_rows = db.fetchall("""
        SELECT composer, COUNT(*) as cnt FROM tracks
        WHERE composer IS NOT NULL AND composer != ''
        GROUP BY composer HAVING cnt >= 30
        ORDER BY cnt DESC
    """)
    for row in composer_rows:
        composer = row['composer']
        tracks = db.fetchall(
            "SELECT id FROM tracks WHERE composer = ? "
            "ORDER BY year, album_id, disc_number, track_number",
            (composer,))
        ids = [t['id'] for t in tracks]
        if ids:
            name = f"★ {composer}"
            if _create_playlist(name, f"Complete works by {composer}", ids):
                log.info("  %s: %d tracks", name, len(ids))
                created += 1

    # --- Movement/style playlists ---
    movement_descriptions = {
        'Impressionism': 'Debussy, Ravel, Satie — color, atmosphere, shimmering textures',
        'Expressionism': 'Schoenberg, Berg — intense emotion, dissonance, inner world',
        'Neoclassicism': 'Stravinsky, Hindemith, Poulenc — return to classical forms',
        'Serialism': 'Webern, Boulez — twelve-tone technique, structured composition',
        'Minimalism': 'Glass, Reich, Riley — repetition, gradual process, trance-like',
        'Holy Minimalism': 'Pärt, Górecki, Tavener — spiritual, meditative, tintinnabuli',
        'Nationalism': 'Dvořák, Smetana, Grieg, Sibelius — folk themes, national identity',
        'Late Romanticism': 'Mahler, R. Strauss, Rachmaninoff — grand, emotional, post-Wagnerian',
        'Neo-Romanticism': 'Richter, Einaudi, Arnalds — accessible, emotional, modern',
        'Avant-Garde': 'Stockhausen, Cage, Xenakis — experimental, boundary-pushing',
        'Film Music': 'Morricone, Zimmer, Williams — cinematic, narrative, orchestral',
        'Verismo': 'Puccini, Mascagni — realistic opera, everyday life drama',
        'Bel Canto': 'Rossini, Donizetti, Bellini — beautiful singing, vocal virtuosity',
        'Spectralism': 'Saariaho, Lindberg — sound spectra, overtone-based composition',
    }
    movement_rows = db.fetchall("""
        SELECT movement, COUNT(*) as cnt FROM tracks
        WHERE movement IS NOT NULL
        GROUP BY movement HAVING cnt >= 10
        ORDER BY cnt DESC
    """)
    for row in movement_rows:
        mov = row['movement']
        tracks = db.fetchall(
            "SELECT id FROM tracks WHERE movement = ? ORDER BY composer, year, title",
            (mov,))
        ids = [t['id'] for t in tracks]
        if ids:
            name = f"◊ {mov}"
            desc = movement_descriptions.get(mov, f"{mov} movement")
            if _create_playlist(name, desc, ids):
                log.info("  %s: %d tracks", name, len(ids))
                created += 1

    # --- Audio quality playlists ---
    # Hi-Res: >44100 Hz or >16 bit
    hires = db.fetchall("""
        SELECT id FROM tracks
        WHERE (sample_rate > 44100 OR bit_depth > 16) AND bit_depth > 0
        ORDER BY sample_rate DESC, bit_depth DESC
    """)
    if hires:
        ids = [t['id'] for t in hires]
        if _create_playlist("◆ Hi-Res Audio",
                            "Tracks with sample rate > 44.1kHz or bit depth > 16-bit",
                            ids):
            log.info("  Hi-Res Audio: %d tracks", len(ids))
            created += 1

    # CD Quality: 44100 Hz, 16 bit
    cdq = db.fetchall("""
        SELECT id FROM tracks
        WHERE sample_rate = 44100 AND bit_depth = 16
        ORDER BY artist_id, title
    """)
    if cdq:
        ids = [t['id'] for t in cdq]
        if _create_playlist("◆ CD Quality",
                            "Tracks at CD standard: 44.1kHz / 16-bit",
                            ids):
            log.info("  CD Quality: %d tracks", len(ids))
            created += 1

    # Lossless (FLAC, WAV, AIFF, ALAC, APE, WV, DSD)
    lossless = db.fetchall("""
        SELECT id FROM tracks
        WHERE file_format IN ('FLAC', 'WAV', 'AIFF', 'AIF', 'ALAC', 'APE', 'WV', 'DSF', 'DFF')
        ORDER BY sample_rate DESC, bit_depth DESC, artist_id
    """)
    if lossless:
        ids = [t['id'] for t in lossless]
        if _create_playlist("◆ Lossless",
                            "All lossless format tracks (FLAC, WAV, ALAC, etc.)",
                            ids):
            log.info("  Lossless: %d tracks", len(ids))
            created += 1

    # --- Musical form playlists ---
    form_rows = db.fetchall("""
        SELECT form, COUNT(*) as cnt FROM tracks
        WHERE form IS NOT NULL
        GROUP BY form HAVING cnt >= 15
        ORDER BY cnt DESC
    """)
    for row in form_rows:
        form = row['form']
        tracks = db.fetchall(
            "SELECT id FROM tracks WHERE form = ? ORDER BY composer, year, title",
            (form,))
        ids = [t['id'] for t in tracks]
        if ids:
            name = f"♫ {form}s" if not form.endswith('s') else f"♫ {form}"
            if _create_playlist(name, f"All {form} works", ids):
                log.info("  %s: %d tracks", name, len(ids))
                created += 1

    # --- Longest tracks (> 20 min, great for focused listening) ---
    long_tracks = db.fetchall("""
        SELECT id FROM tracks
        WHERE duration_ms > 1200000
        ORDER BY duration_ms DESC
    """)
    if long_tracks:
        ids = [t['id'] for t in long_tracks]
        if _create_playlist("◇ Long Works (20+ min)",
                            "Extended works over 20 minutes — symphonies, concertos, operas",
                            ids):
            log.info("  Long Works: %d tracks", len(ids))
            created += 1

    # --- Most played ---
    most_played = db.fetchall("""
        SELECT id FROM tracks
        WHERE play_count > 0
        ORDER BY play_count DESC
        LIMIT 200
    """)
    if most_played:
        ids = [t['id'] for t in most_played]
        if _create_playlist("▶ Most Played",
                            "Your most listened tracks",
                            ids):
            log.info("  Most Played: %d tracks", len(ids))
            created += 1

    # --- Recently added ---
    recent = db.fetchall("""
        SELECT id FROM tracks
        ORDER BY added_at DESC
        LIMIT 500
    """)
    if recent:
        ids = [t['id'] for t in recent]
        if _create_playlist("▷ Recently Added",
                            "Last 500 tracks added to your library",
                            ids):
            log.info("  Recently Added: %d tracks", len(ids))
            created += 1

    # --- Top rated ---
    top_rated = db.fetchall("""
        SELECT id FROM tracks
        WHERE rating >= 4
        ORDER BY rating DESC, play_count DESC
    """)
    if top_rated:
        ids = [t['id'] for t in top_rated]
        if _create_playlist("★ Top Rated",
                            "Tracks rated 4 stars and above",
                            ids):
            log.info("  Top Rated: %d tracks", len(ids))
            created += 1

    log.info("Smart playlists: %d created/updated", created)
    return created


def print_library_report():
    """Print a comprehensive library report."""
    import database as db

    stats = db.get_library_stats()
    total_ms = stats['total_duration_ms']
    hours = total_ms // 3600000
    mins = (total_ms % 3600000) // 60000
    size_gb = stats['total_size'] / (1024 ** 3)

    log.info("=" * 60)
    log.info("LIBRARY REPORT")
    log.info("=" * 60)
    log.info("  Tracks: %d", stats['tracks'])
    log.info("  Albums: %d", stats['albums'])
    log.info("  Artists: %d", stats['artists'])
    log.info("  Playlists: %d", stats['playlists'])
    log.info("  Duration: %dh %dm", hours, mins)
    log.info("  Size: %.1f GB", size_gb)

    # Format breakdown
    formats = db.fetchall("""
        SELECT file_format, COUNT(*) as cnt,
               SUM(file_size) as total_size,
               SUM(duration_ms) as total_duration
        FROM tracks
        GROUP BY file_format ORDER BY cnt DESC
    """)
    log.info("  Formats:")
    for f in formats:
        fmt_gb = (f['total_size'] or 0) / (1024 ** 3)
        fmt_h = (f['total_duration'] or 0) / 3600000
        log.info("    %s: %d tracks (%.1f GB, %.0fh)", f['file_format'], f['cnt'], fmt_gb, fmt_h)

    # Genre coverage
    with_genre = db.fetchone(
        "SELECT COUNT(*) as c FROM tracks WHERE genre IS NOT NULL")['c']
    log.info("  Genre coverage: %d/%d (%.1f%%)",
             with_genre, stats['tracks'],
             100 * with_genre / max(stats['tracks'], 1))

    # Composer coverage
    with_comp = db.fetchone(
        "SELECT COUNT(*) as c FROM tracks WHERE composer IS NOT NULL AND composer != ''")['c']
    log.info("  Composer coverage: %d/%d (%.1f%%)",
             with_comp, stats['tracks'],
             100 * with_comp / max(stats['tracks'], 1))

    # Classification coverage
    with_period = db.fetchone(
        "SELECT COUNT(*) as c FROM tracks WHERE period IS NOT NULL")['c']
    with_form = db.fetchone(
        "SELECT COUNT(*) as c FROM tracks WHERE form IS NOT NULL")['c']
    log.info("  Period classification: %d/%d (%.1f%%)",
             with_period, stats['tracks'],
             100 * with_period / max(stats['tracks'], 1))
    log.info("  Form classification: %d/%d (%.1f%%)",
             with_form, stats['tracks'],
             100 * with_form / max(stats['tracks'], 1))

    # Top genres
    top_genres = db.fetchall("""
        SELECT genre, COUNT(*) as cnt FROM tracks
        WHERE genre IS NOT NULL
        GROUP BY genre ORDER BY cnt DESC LIMIT 10
    """)
    log.info("  Top genres:")
    for g in top_genres:
        log.info("    %s: %d", g['genre'], g['cnt'])

    # Top composers
    top_comps = db.fetchall("""
        SELECT composer, COUNT(*) as cnt FROM tracks
        WHERE composer IS NOT NULL AND composer != ''
        GROUP BY composer ORDER BY cnt DESC LIMIT 10
    """)
    log.info("  Top composers:")
    for c in top_comps:
        log.info("    %s: %d", c['composer'], c['cnt'])


def main():
    """Main entry point — full autonomous library processing."""
    import database as db
    import platform

    # Determine folder
    if len(sys.argv) < 2:
        print("Usage: python smart_library.py <music_folder>")
        print("Example: python smart_library.py P:/Musique")
        sys.exit(1)
    folder = sys.argv[1]

    if not os.path.isdir(folder):
        log.error("Folder not found: %s", folder)
        sys.exit(1)

    # Init database
    system = platform.system()
    if system == 'Windows':
        base = Path(os.environ.get('APPDATA', str(Path.home())))
    elif system == 'Darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME',
                                   str(Path.home() / '.local' / 'share')))
    db_path = str(base / 'MusicOtheque' / 'musicotheque.db')

    log.info("=" * 60)
    log.info("SMART LIBRARY MANAGER")
    log.info("=" * 60)
    log.info("Folder: %s", folder)
    log.info("Database: %s", db_path)

    db.init(db_path)

    # Register scan folder if not already
    existing_folder = db.fetchone(
        "SELECT id FROM scan_folders WHERE path = ?", (folder,))
    if not existing_folder:
        db.execute(
            "INSERT INTO scan_folders(path, auto_scan) VALUES(?, 1)",
            (folder,), commit=True)

    t_start = time.time()

    # Step 1: Scan
    log.info("")
    added, updated, skipped, errors = scan_folder(folder)

    # Step 2: Harmonize
    log.info("")
    harmonize_all()

    # Step 3: Classify
    log.info("")
    classify_all()

    # Step 4: Rebuild FTS5
    log.info("")
    log.info("Rebuilding FTS5 search index...")
    db.rebuild_fts()
    log.info("FTS5 rebuilt")

    # Step 5: Smart playlists
    log.info("")
    generate_smart_playlists()

    # Step 6: Report
    log.info("")
    print_library_report()

    elapsed = time.time() - t_start
    log.info("")
    log.info("Total processing time: %.0f seconds (%.1f minutes)", elapsed, elapsed / 60)

    # Update scan timestamp
    db.execute(
        "UPDATE scan_folders SET last_scan = datetime('now') WHERE path = ?",
        (folder,), commit=True)


if __name__ == '__main__':
    main()
