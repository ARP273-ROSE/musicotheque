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
- Browse by **Artists**, **Albums**, **Genres**, or **Playlists** (create, rename, delete)
- **Cover art extraction** from embedded tags (ID3, FLAC pictures, MP4 covr)
- **Audio quality indicators**: Hi-Res, CD Quality, Lossless, Lossy badges
- **Unicode support**: Latin, Greek, Cyrillic, Arabic, Chinese, Japanese, Korean

#### Playlist Management
- **Create** new playlists from the sidebar context menu or when adding tracks
- **Rename** and **delete** playlists via right-click on any playlist in the sidebar
- **Drag & drop** tracks onto playlists in the sidebar to add them
- Drop badge shows how many tracks are being added
- **Remove tracks** from a playlist via right-click context menu (only when viewing a playlist)

#### Drag & Drop
- **Drag tracks** from the library to any folder on your desktop, Explorer, Finder, or Nautilus
- **Drag tracks to playlists** in the sidebar to add them instantly
- **Multi-selection** with Ctrl+click and Shift+click — drag multiple files at once
- Cross-platform: works on Windows, macOS, and Linux file managers
- Badge shows the number of files being dragged

#### Metadata Editing
- **iTunes-style metadata editor** via right-click context menu
- **Single track mode**: edit all 16 fields (title, artist, album, genre, year, track#, disc#, composer, period, movement, sub-period, form, catalogue, instruments, key)
- **Multi-track batch mode**: edit shared fields across many tracks at once — mixed values show "(keep original)", only changed fields are applied
- Changes saved to **both database and audio files** (ID3/FLAC/OGG/MP4 tags via mutagen)
- Adaptive context menu: play, queue, add to playlist, edit metadata, track info, reset play count — all multi-selection aware

#### HiFi Audio Player
- **QMediaPlayer**-based playback with broad codec support via platform decoders
- **Audio device selection**: choose your DAC, USB headphones, or speakers from Settings
- **Live audio chain display**: format, sample rate, bit depth, and output device shown in player bar
- **Device capabilities**: sample rate range, channel count, and supported bit formats
- **Gapless playback** with pre-buffering
- Playback queue with **shuffle** and **repeat** modes (off / all / one)
- **Volume control** with mute toggle
- **Smart play count**: tracks listened for at least 30 seconds (skipped tracks don't count)
- **Reset play counts** for privacy (all tracks or individual via context menu)
- Selected audio device **remembered across sessions**

#### Smart Radio (Ctrl+R)
- **Play random tracks** with intelligent, combinable filters
- Filter by **genre**, **artist**, **composer**, **album** — all combinable
- Filter by **era**: Medieval, Renaissance, Baroque, Classical, Romantic, Modern, Contemporary, Recent, or custom year range
- Filter by **audio quality**: Hi-Res, CD Quality, Lossless, Lossy
- Filter by **minimum rating** and **unplayed only**
- **Live counter** shows matching tracks, with optional track limit
- All filters combine with AND logic for precise selection

#### Podcast Manager
- **Subscribe** to podcasts by RSS feed URL
- **Search podcasts** online via iTunes directory
- **Download episodes** for offline listening
- Browse shows and episodes with playback position tracking
- **iTunes podcast import** from Library XML

#### Web Radio
- **30+ curated internet radio stations** from around the world
- **Classical music**: France Musique (8 channels), Radio Classique, BBC Radio 3, Rai Radio 3 Classica, RTS Espace 2, WQXR, BR-Klassik, Concertzender, ABC Classic
- **Culture**: France Culture, France Inter
- **News**: Franceinfo, BBC World Service, NPR (WNYC)
- **Eclectic**: FIP and 7 themed channels (Rock, Jazz, Electro, World, Groove, Pop, Nouveautés)
- Live streaming with LIVE badge in player bar
- Browse by category in sidebar

#### Audio Visualizer (Ctrl+V)
- **Spectrum Analyzer** — 64-bar real-time frequency display with per-bar gradient, cyan peak hold (1s hold, 10 dB/s decay), dB scale labels, professional ballistics (0.8 attack, 15 dB/s decay)
- **VU Meter** — True stereo RMS level meter with separate L/R channels and peak markers, IEC 60268-17 ballistics (300ms attack, 13.3 dB/s decay), dB labels and real-time level readout
- **Spectrogram** — Optimized waterfall frequency display with perceptually-uniform inferno colormap, frequency axis labels (20 Hz–20 kHz), numpy-accelerated rendering
- Uses `QAudioBufferOutput` for zero-copy PCM access (no external capture needed)
- Lightweight: < 4% CPU total via QPainter rendering at 10-20 fps
- Designed for HiFi setups with DAC and high-end headphones
- Toggle on/off anytime during playback

#### CD Audio Import
- **Rip audio CDs** to FLAC format
- **MusicBrainz lookup** for automatic track names, album, artist, and cover art
- Configurable output directory
- Requires ffmpeg

#### Metadata Harmonization
- **Normalize artist names** (fuzzy matching, merge duplicates) — written back to file tags
- **Clean album titles** (remove junk suffixes like "Remastered", "Deluxe") — written back to file tags
- **Normalize composers** with 552 aliases for 100+ classical & film composers — written back to file tags
- **Merge genres** (consolidate similar genres) — written back to file tags
- **File-level metadata updates**: all corrections are written directly to audio file metadata (MP3/ID3, FLAC, OGG/Opus, M4A/MP4)
- **Preview changes** before applying, with undo support

#### iTunes Import
- Import **iTunes Library XML** files
- Preserves **playlists**, play counts, and ratings
- Separate import for podcasts
- Path remapping for relocated libraries
- Smart duplicate detection

#### Music Classification
- **Automatic period detection** from composer metadata: Medieval, Renaissance, Baroque, Classical, Romantic, Modern, Contemporary
- **419 composers** mapped to historical periods (with birth/death years)
- **Sub-period refinement**: Early/High/Late Baroque, Galant Style, Early/High/Late Romantic, Fin de Siècle, Interwar Modernism
- **19 musical movements/styles** detected: Impressionism, Expressionism, Neoclassicism, Serialism, Minimalism, Holy Minimalism, Nationalism, Late Romanticism, Neo-Romanticism, Avant-Garde, Film Music, Verismo, Bel Canto, Spectralism, Ars Nova/Antiqua, Venetian/Roman/Franco-Flemish Schools
- **70+ musical forms** detected from titles: Symphony, Concerto, Sonata, Fugue, Nocturne, Opera, Requiem, String Quartet, Bagatelle, Elegy, Romance, Pavane, Czárdás, etc.
- **Catalogue number extraction**: BWV (Bach), K./KV (Mozart), Op., D. (Schubert), RV (Vivaldi), HWV (Handel), and more
- **Instrumentation detection**: Piano, Violin, Orchestra, Chamber, Choir, etc.
- **Key detection**: e.g., "C minor", "E-flat major"
- **File metadata writing**: classification data written directly to audio file tags (ID3 TXXX, Vorbis comments, MP4 atoms)
- Batch classification of entire library with period/form/movement statistics
- Per-track classification visible in track info dialog

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

#### File Organizer
- **Organize files on disk** into clean `Artist / Album / Track` folder structure
- Smart filename sanitization (cross-platform safe)
- Disc/track number prefixes for correct sort order
- Automatic database path updates after moving files
- Duplicate detection with automatic renaming

#### Library Watcher
- **Automatic monitoring** of scan folders for file changes
- Polling-based (works on NAS/SMB shares, network drives — no inotify dependency)
- **Auto-relocation**: detects drive letter changes and fixes paths automatically
- Cross-platform: handles Windows→Linux path translation transparently
- 3-minute poll interval, triggers background re-scan on changes

#### NAS Multi-PC Portability
- **Project-local data**: database, config, backups, and logs stored in the project directory (not APPDATA) — works from NAS, USB drive, or synced folder across multiple PCs
- **Per-PC virtual environment**: venv created in `%LOCALAPPDATA%\MusicOtheque\venv` (Windows) or `$XDG_DATA_HOME/MusicOtheque/venv` (Linux) — never synced
- **Portable launcher**: `launch.bat` (Windows) / `launch.sh` (Linux/macOS) — auto-detects Python, creates venv, installs deps
- **Desktop shortcut helper**: auto-creates a portable shortcut targeting the launcher (not the Python binary)
- **Migration**: on first launch, offers to migrate data from old APPDATA location to the project directory

#### Cross-Platform
- **Windows**, **Linux**, and **macOS** support
- **Path relocation** tool for migrated libraries (e.g., `J:/Music` → `/mnt/nas/Music`)
- **Automatic path relocation** on drive letter changes (transparent, no user action)
- Broken path detection and reporting

#### Data Safety
- **Continuous auto-backup** every 5 minutes (transparent, background thread)
- Additional backup on exit
- Backup rotation: 5 daily + 4 weekly
- **Atomic saves** (write-tmp-then-rename)
- **SQLite WAL mode** with thread-safe access
- Export library to portable JSON
- **Automatic crash reports**: saved locally as JSON on unhandled exceptions (anonymized — user paths replaced with `~`)
- **Bug report template**: Help menu opens a pre-filled GitHub issue with system info, version, and last log entries (all anonymized)

#### Bilingual Interface
- Full **English / French** interface with 450+ translation keys
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
- numpy (audio visualization FFT)
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
11. **Classify**: Tools → Classify Library (period, form, catalogue detection)
12. **Organize**: Tools → Organize Files on Disk (Artist/Album/Track structure)

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
| `Ctrl+R` | Smart Radio |
| `Ctrl+V` | Audio Visualizer |
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
| `player.py` | QMediaPlayer audio engine with queue, shuffle, repeat, device selection |
| `scanner.py` | Folder scanner with mutagen metadata extraction |
| `database.py` | SQLite WAL, FTS5 full-text search, thread-safe, path relocation |
| `i18n.py` | Bilingual translation system (410+ keys) |
| `itunes_import.py` | iTunes Library XML parser (music + podcasts) |
| `metadata_fetch.py` | MusicBrainz API integration |
| `podcast_manager.py` | RSS feed parser, episode downloader, iTunes podcast search |
| `cd_ripper.py` | CD drive detection, ffmpeg ripping, MusicBrainz lookup |
| `harmonizer.py` | Metadata normalization (artists, composers, albums, genres) |
| `backup_manager.py` | Auto-backup with rotation and atomic restore |
| `web_radio.py` | 30+ curated internet radio stations with streaming URLs |
| `music_classifier.py` | Classical music classifier (period, form, catalogue, instruments) |
| `audio_visualizer.py` | Real-time audio visualization (spectrum, VU meter, spectrogram) |
| `library_watcher.py` | File system watcher with auto-relocation |
| `file_organizer.py` | File organizer (Artist/Album/Track structure) |
| `shortcut_helper.py` | Cross-platform desktop shortcut creation (Windows .lnk, Linux .desktop) |
| `smart_library.py` | Standalone batch processor: scan, harmonize, classify, generate playlists |

### Data Location

All application data (database, config, backups, logs) is stored **in the project directory** — portable across PCs via NAS or synced folder.

| Data | Location |
|------|----------|
| Database | `./musicotheque.db` (project directory) |
| Backups | `./backups/` (project directory) |
| Logs | `./musicotheque.log` (project directory) |
| Virtual env | `%LOCALAPPDATA%\MusicOtheque\venv` (Windows) |
| Virtual env | `$XDG_DATA_HOME/MusicOtheque/venv` (Linux/macOS) |

---

### License

MIT License — © 2026 Kevin
