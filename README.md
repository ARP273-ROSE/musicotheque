![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20|%20Linux%20|%20macOS-lightgrey)

**MusicOthèque** — A powerful music library manager and HiFi audio player built with Python and PyQt6. Scan your music collection, play any format, import iTunes libraries, manage podcasts, rip CDs, harmonize metadata, and fetch info online.

---

### Features

#### Music Library Management
- **Automatic scanning** of music folders with metadata extraction (mutagen)
- **21+ audio formats** supported: FLAC, MP3, OGG, Opus, M4A, AAC, WAV, AIFF, ALAC, APE, WavPack, DSD (DSF/DFF), MKA, TTA, SPX, MPC, WMA, and more
- **Full-text search** (FTS5) across titles, artists, albums, genres, and composers
- Browse by **Artists**, **Albums**, **Genres**, or **Playlists**
- **Cover art extraction** from embedded tags (ID3, FLAC pictures, MP4 covr)
- **Audio quality indicators**: Hi-Res, CD Quality, Lossless, Lossy badges
- **Unicode support**: Latin, Greek, Cyrillic, Arabic, Chinese, Japanese, Korean

#### HiFi Audio Player
- **QMediaPlayer**-based playback with broad codec support via platform decoders
- **Gapless playback** with pre-buffering
- Playback queue with **shuffle** and **repeat** modes (off / all / one)
- **Volume control** with mute toggle
- **Smart play count**: tracks listened for at least 30 seconds (skipped tracks don't count)

#### Podcast Manager
- **Subscribe** to podcasts by RSS feed URL
- **Search podcasts** online via iTunes directory
- **Download episodes** for offline listening
- Browse shows and episodes with playback position tracking
- **iTunes podcast import** from Library XML

#### CD Audio Import
- **Rip audio CDs** to FLAC format
- **MusicBrainz lookup** for automatic track names, album, artist, and cover art
- Configurable output directory
- Requires ffmpeg

#### Metadata Harmonization
- **Normalize artist names** (fuzzy matching, merge duplicates)
- **Clean album titles** (remove junk suffixes like "Remastered", "Deluxe")
- **Normalize composers** (classical music composer dictionary)
- **Merge genres** (consolidate similar genres)
- **Preview changes** before applying, with undo support

#### iTunes Import
- Import **iTunes Library XML** files
- Preserves **playlists**, play counts, and ratings
- Separate import for podcasts
- Path remapping for relocated libraries
- Smart duplicate detection

#### Online Metadata
- **MusicBrainz** integration for track identification
- **Cover Art Archive** for album artwork
- Rate-limited API access (respects MusicBrainz guidelines)

#### Library Statistics (Ctrl+I)
- Comprehensive overview: tracks, albums, artists, playlists, podcasts
- **Format distribution** with size and duration per format
- **Audio quality breakdown**: Hi-Res, CD Quality, Lossless, Lossy percentages
- **Top artists** and **genres** with visual bar charts
- **Most played** tracks
- Total size and duration for every view (playlist, folder, genre, artist)

#### Cross-Platform
- **Windows**, **Linux**, and **macOS** support
- OS-appropriate data directories (APPDATA / XDG_DATA_HOME / Library)
- **Path relocation** tool for migrated libraries (e.g., `J:/Music` → `/mnt/nas/Music`)
- Broken path detection and reporting

#### Data Safety
- **Auto-backup** every 30 minutes + on exit
- Backup rotation: 5 daily + 4 weekly
- **Atomic saves** (write-tmp-then-rename)
- **SQLite WAL mode** with thread-safe access
- Export library to portable JSON

#### Bilingual Interface
- Full **English / French** interface with 300+ translation keys
- Automatic system language detection
- All tooltips, menus, dialogs, and help in both languages

---

### Installation

#### Using Launcher (Recommended)

**Windows:**
```
launch.bat
```

**Linux / macOS:**
```bash
chmod +x launch.sh
./launch.sh
```

The launcher automatically creates a virtual environment and installs dependencies.

#### Manual Installation

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

pip install -r requirements.txt
python musicotheque.py
```

### Requirements

- Python 3.10+
- PyQt6 (with QtMultimedia)
- mutagen (metadata reading)
- requests (MusicBrainz API, podcast search)
- feedparser (RSS podcast feeds)
- ffmpeg (optional, for CD ripping)

---

### Usage

1. **Add music folders**: File → Add Music Folder (Ctrl+O)
2. **Browse**: Use the sidebar to navigate by artist, album, genre, or playlist
3. **Play**: Double-click any track, or use the transport controls
4. **Search**: Ctrl+F for full-text search across your library
5. **Import iTunes**: File → Import iTunes Library
6. **Fetch metadata**: View → Fetch Metadata Online (MusicBrainz)
7. **Podcasts**: View → Subscribe to Podcast / Search Podcasts Online
8. **Rip CD**: File → Import Audio CD
9. **Harmonize**: Tools → Harmonize Metadata
10. **Statistics**: Tools → Library Statistics (Ctrl+I)

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Space` | Play / Pause |
| `Ctrl+Right` | Next track |
| `Ctrl+Left` | Previous track |
| `Ctrl+Up/Down` | Volume up/down |
| `Ctrl+.` | Stop |
| `Ctrl+O` | Add folder |
| `Ctrl+F` | Search |
| `F5` | Rescan library |
| `Ctrl+I` | Library Statistics |
| `Ctrl+,` | Settings |
| `Ctrl+Q` | Quit |
| `F1` | Help |

---

### Architecture

| File | Purpose |
|------|---------|
| `musicotheque.py` | Entry point, crash handler, dark theme, hardware detection |
| `main_window.py` | Full UI: sidebar, track table, player bar, menus, dialogs, stats |
| `player.py` | QMediaPlayer audio engine with queue, shuffle, repeat |
| `scanner.py` | Folder scanner with mutagen metadata extraction |
| `database.py` | SQLite WAL, FTS5 full-text search, thread-safe, path relocation |
| `i18n.py` | Bilingual translation system (300+ keys) |
| `itunes_import.py` | iTunes Library XML parser (music + podcasts) |
| `metadata_fetch.py` | MusicBrainz API integration |
| `podcast_manager.py` | RSS feed parser, episode downloader, iTunes podcast search |
| `cd_ripper.py` | CD drive detection, ffmpeg ripping, MusicBrainz lookup |
| `harmonizer.py` | Metadata normalization (artists, composers, albums, genres) |
| `backup_manager.py` | Auto-backup with rotation and atomic restore |

### Data Location

| OS | Path |
|----|------|
| Windows | `%APPDATA%\MusicOtheque\` |
| Linux | `~/.local/share/MusicOtheque/` |
| macOS | `~/Library/Application Support/MusicOtheque/` |

---

### License

MIT License — © 2026 Kevin
