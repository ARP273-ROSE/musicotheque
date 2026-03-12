"""Internationalization module for MusicOthèque."""
import locale

_LANG = 'en'

TX = {
    # App
    'app_name': {'en': 'MusicOthèque', 'fr': 'MusicOthèque'},
    'app_subtitle': {'en': 'Music Library & HiFi Player', 'fr': 'Bibliothèque Musicale & Lecteur HiFi'},

    # Menu
    'menu_file': {'en': '&File', 'fr': '&Fichier'},
    'menu_edit': {'en': '&Edit', 'fr': '&Édition'},
    'menu_view': {'en': '&View', 'fr': '&Affichage'},
    'menu_playback': {'en': '&Playback', 'fr': '&Lecture'},
    'menu_help': {'en': '&Help', 'fr': '&Aide'},

    # File menu
    'add_folder': {'en': 'Add Music Folder...', 'fr': 'Ajouter un dossier musical...'},
    'add_folder_tip': {'en': 'Scan a folder for music files', 'fr': 'Scanner un dossier pour trouver des fichiers audio'},
    'import_itunes': {'en': 'Import iTunes Library...', 'fr': 'Importer la bibliothèque iTunes...'},
    'import_itunes_tip': {'en': 'Import playlists and metadata from iTunes XML', 'fr': 'Importer les playlists et métadonnées depuis iTunes XML'},
    'rescan': {'en': 'Rescan Library', 'fr': 'Rescanner la bibliothèque'},
    'rescan_tip': {'en': 'Rescan all music folders for changes', 'fr': 'Rescanner tous les dossiers musicaux pour détecter les changements'},
    'settings': {'en': 'Settings...', 'fr': 'Paramètres...'},
    'settings_tip': {'en': 'Open application settings', 'fr': 'Ouvrir les paramètres de l\'application'},
    'quit': {'en': 'Quit', 'fr': 'Quitter'},
    'quit_tip': {'en': 'Exit MusicOthèque', 'fr': 'Quitter MusicOthèque'},

    # View
    'view_artists': {'en': 'Artists', 'fr': 'Artistes'},
    'view_albums': {'en': 'Albums', 'fr': 'Albums'},
    'view_tracks': {'en': 'Tracks', 'fr': 'Pistes'},
    'view_genres': {'en': 'Genres', 'fr': 'Genres'},
    'view_playlists': {'en': 'Playlists', 'fr': 'Playlists'},
    'view_now_playing': {'en': 'Now Playing', 'fr': 'En cours de lecture'},
    'view_all_tracks': {'en': 'All Tracks', 'fr': 'Toutes les pistes'},

    # Player
    'play': {'en': 'Play', 'fr': 'Lecture'},
    'pause': {'en': 'Pause', 'fr': 'Pause'},
    'stop': {'en': 'Stop', 'fr': 'Arrêt'},
    'previous': {'en': 'Previous', 'fr': 'Précédent'},
    'next': {'en': 'Next', 'fr': 'Suivant'},
    'shuffle': {'en': 'Shuffle', 'fr': 'Aléatoire'},
    'repeat': {'en': 'Repeat', 'fr': 'Répéter'},
    'repeat_off': {'en': 'Repeat Off', 'fr': 'Répétition désactivée'},
    'repeat_all': {'en': 'Repeat All', 'fr': 'Répéter tout'},
    'repeat_one': {'en': 'Repeat One', 'fr': 'Répéter un'},
    'volume': {'en': 'Volume', 'fr': 'Volume'},
    'mute': {'en': 'Mute', 'fr': 'Muet'},

    # Track table headers
    'col_title': {'en': 'Title', 'fr': 'Titre'},
    'col_artist': {'en': 'Artist', 'fr': 'Artiste'},
    'col_album': {'en': 'Album', 'fr': 'Album'},
    'col_duration': {'en': 'Duration', 'fr': 'Durée'},
    'col_track_num': {'en': '#', 'fr': '#'},
    'col_year': {'en': 'Year', 'fr': 'Année'},
    'col_genre': {'en': 'Genre', 'fr': 'Genre'},
    'col_format': {'en': 'Format', 'fr': 'Format'},
    'col_bitrate': {'en': 'Bitrate', 'fr': 'Débit'},
    'col_sample_rate': {'en': 'Sample Rate', 'fr': 'Échantillonnage'},
    'col_bit_depth': {'en': 'Bit Depth', 'fr': 'Profondeur'},
    'col_play_count': {'en': 'Plays', 'fr': 'Lectures'},
    'col_rating': {'en': 'Rating', 'fr': 'Note'},

    # Library
    'library': {'en': 'Library', 'fr': 'Bibliothèque'},
    'all_artists': {'en': 'All Artists', 'fr': 'Tous les artistes'},
    'all_albums': {'en': 'All Albums', 'fr': 'Tous les albums'},
    'unknown_artist': {'en': 'Unknown Artist', 'fr': 'Artiste inconnu'},
    'unknown_album': {'en': 'Unknown Album', 'fr': 'Album inconnu'},
    'various_artists': {'en': 'Various Artists', 'fr': 'Artistes Variés'},

    # Scanner
    'scanning': {'en': 'Scanning...', 'fr': 'Analyse en cours...'},
    'scan_complete': {'en': 'Scan complete: {added} added, {updated} updated, {removed} removed',
                      'fr': 'Analyse terminée : {added} ajoutés, {updated} mis à jour, {removed} supprimés'},
    'scan_progress': {'en': 'Scanning: {current}/{total} files...', 'fr': 'Analyse : {current}/{total} fichiers...'},

    # Search
    'search': {'en': 'Search...', 'fr': 'Rechercher...'},
    'search_tip': {'en': 'Search by title, artist, or album', 'fr': 'Rechercher par titre, artiste ou album'},
    'no_results': {'en': 'No results found', 'fr': 'Aucun résultat trouvé'},

    # Playlists
    'new_playlist': {'en': 'New Playlist', 'fr': 'Nouvelle playlist'},
    'delete_playlist': {'en': 'Delete Playlist', 'fr': 'Supprimer la playlist'},
    'rename_playlist': {'en': 'Rename Playlist', 'fr': 'Renommer la playlist'},
    'add_to_playlist': {'en': 'Add to Playlist', 'fr': 'Ajouter à la playlist'},
    'remove_from_playlist': {'en': 'Remove from Playlist', 'fr': 'Retirer de la playlist'},
    'playlist_tracks_count': {'en': '{count} tracks', 'fr': '{count} pistes'},

    # iTunes import
    'itunes_select_xml': {'en': 'Select iTunes Library XML...', 'fr': 'Sélectionner le fichier iTunes Library XML...'},
    'itunes_importing': {'en': 'Importing iTunes library...', 'fr': 'Import de la bibliothèque iTunes...'},
    'itunes_complete': {'en': 'iTunes import complete: {tracks} tracks, {playlists} playlists',
                        'fr': 'Import iTunes terminé : {tracks} pistes, {playlists} playlists'},

    # Metadata
    'fetch_metadata': {'en': 'Fetch Metadata Online', 'fr': 'Récupérer les métadonnées en ligne'},
    'fetch_metadata_tip': {'en': 'Look up track info on MusicBrainz', 'fr': 'Rechercher les informations sur MusicBrainz'},
    'fetching_metadata': {'en': 'Fetching metadata...', 'fr': 'Récupération des métadonnées...'},

    # Status
    'ready': {'en': 'Ready', 'fr': 'Prêt'},
    'total_tracks': {'en': '{count} tracks', 'fr': '{count} pistes'},
    'total_duration': {'en': 'Total: {duration}', 'fr': 'Durée totale : {duration}'},
    'total_size': {'en': 'Size: {size}', 'fr': 'Taille : {size}'},

    # Dialogs
    'confirm_delete': {'en': 'Are you sure you want to delete this playlist?',
                       'fr': 'Êtes-vous sûr de vouloir supprimer cette playlist ?'},
    'error': {'en': 'Error', 'fr': 'Erreur'},
    'warning': {'en': 'Warning', 'fr': 'Attention'},
    'info': {'en': 'Information', 'fr': 'Information'},
    'ok': {'en': 'OK', 'fr': 'OK'},
    'cancel': {'en': 'Cancel', 'fr': 'Annuler'},
    'yes': {'en': 'Yes', 'fr': 'Oui'},
    'no': {'en': 'No', 'fr': 'Non'},

    # Help
    'help_title': {'en': 'MusicOthèque Help', 'fr': 'Aide MusicOthèque'},
    'about': {'en': 'About MusicOthèque', 'fr': 'À propos de MusicOthèque'},
    'check_updates': {'en': 'Check for Updates', 'fr': 'Vérifier les mises à jour'},
    'report_bug': {'en': 'Report a Bug', 'fr': 'Signaler un bug'},

    # Audio quality
    'quality_lossless': {'en': 'Lossless', 'fr': 'Sans perte'},
    'quality_hires': {'en': 'Hi-Res', 'fr': 'Hi-Res'},
    'quality_lossy': {'en': 'Lossy', 'fr': 'Avec perte'},
    'quality_cd': {'en': 'CD Quality', 'fr': 'Qualité CD'},
}


def detect_language():
    """Detect system language, default to English."""
    global _LANG
    try:
        loc = locale.getdefaultlocale()[0] or ''
        _LANG = 'fr' if loc.startswith('fr') else 'en'
    except Exception:
        _LANG = 'en'
    return _LANG


def T(key, lang=None, **kwargs):
    """Translate a key."""
    l = lang or _LANG
    entry = TX.get(key, {})
    text = entry.get(l, entry.get('en', f'[{key}]'))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def get_lang():
    return _LANG


def set_lang(lang):
    global _LANG
    _LANG = lang


# Auto-detect on import
detect_language()
