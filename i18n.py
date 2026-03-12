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

    # Backup & Restore
    'backup': {'en': 'Backup Database', 'fr': 'Sauvegarder la base de données'},
    'backup_tip': {'en': 'Create a backup of the music database', 'fr': 'Créer une sauvegarde de la base de données musicale'},
    'backup_done': {'en': 'Database backed up successfully', 'fr': 'Base de données sauvegardée avec succès'},
    'restore': {'en': 'Restore Database...', 'fr': 'Restaurer la base de données...'},
    'restore_tip': {'en': 'Restore database from a previous backup', 'fr': 'Restaurer la base de données depuis une sauvegarde précédente'},
    'restore_confirm': {'en': 'Restore database from backup?\nCurrent data will be replaced.',
                        'fr': 'Restaurer la base de données depuis la sauvegarde ?\nLes données actuelles seront remplacées.'},
    'restore_done': {'en': 'Database restored. Restart required.', 'fr': 'Base de données restaurée. Redémarrage nécessaire.'},
    'auto_backup': {'en': 'Auto-backup every 30 minutes', 'fr': 'Sauvegarde automatique toutes les 30 minutes'},

    # Path relocation
    'relocate_paths': {'en': 'Relocate Music Paths...', 'fr': 'Déplacer les chemins musicaux...'},
    'relocate_paths_tip': {'en': 'Update file paths when music library has moved',
                           'fr': 'Mettre à jour les chemins quand la bibliothèque a été déplacée'},
    'relocate_old': {'en': 'Old path prefix (e.g. J:/Musique)', 'fr': 'Ancien préfixe de chemin (ex. J:/Musique)'},
    'relocate_new': {'en': 'New path prefix (e.g. /mnt/nas/Musique)', 'fr': 'Nouveau préfixe de chemin (ex. /mnt/nas/Musique)'},
    'relocate_done': {'en': '{count} paths updated', 'fr': '{count} chemins mis à jour'},
    'broken_paths': {'en': 'Check Broken Paths', 'fr': 'Vérifier les chemins cassés'},
    'broken_paths_tip': {'en': 'Find tracks whose files no longer exist', 'fr': 'Trouver les pistes dont les fichiers n\'existent plus'},
    'broken_paths_result': {'en': '{count} broken paths found', 'fr': '{count} chemins cassés trouvés'},
    'no_broken_paths': {'en': 'All paths valid', 'fr': 'Tous les chemins sont valides'},

    # Export
    'export_library': {'en': 'Export Library...', 'fr': 'Exporter la bibliothèque...'},
    'export_library_tip': {'en': 'Export library metadata to JSON (portable)', 'fr': 'Exporter les métadonnées en JSON (portable)'},
    'export_done': {'en': '{count} tracks exported', 'fr': '{count} pistes exportées'},

    # Context menu
    'play_now': {'en': 'Play Now', 'fr': 'Lire maintenant'},
    'play_next': {'en': 'Play Next', 'fr': 'Lire ensuite'},
    'add_to_queue': {'en': 'Add to Queue', 'fr': 'Ajouter à la file'},
    'show_in_explorer': {'en': 'Show in File Explorer', 'fr': 'Afficher dans l\'explorateur'},
    'track_info': {'en': 'Track Info...', 'fr': 'Informations de la piste...'},

    # Sidebar tooltips
    'sidebar_library_tip': {'en': 'Browse your music library', 'fr': 'Parcourir votre bibliothèque musicale'},
    'sidebar_all_tracks_tip': {'en': 'Show all tracks in the library', 'fr': 'Afficher toutes les pistes de la bibliothèque'},
    'sidebar_artists_tip': {'en': 'Browse by artist name', 'fr': 'Parcourir par nom d\'artiste'},
    'sidebar_albums_tip': {'en': 'Browse by album', 'fr': 'Parcourir par album'},
    'sidebar_genres_tip': {'en': 'Browse by musical genre', 'fr': 'Parcourir par genre musical'},
    'sidebar_playlists_tip': {'en': 'Manage your playlists', 'fr': 'Gérer vos playlists'},

    # Player bar tooltips
    'seek_tip': {'en': 'Seek position in current track', 'fr': 'Position de lecture dans la piste actuelle'},
    'cover_tip': {'en': 'Album cover art', 'fr': 'Pochette de l\'album'},
    'quality_tip': {'en': 'Audio quality indicator', 'fr': 'Indicateur de qualité audio'},

    # Tools menu
    'menu_tools': {'en': '&Tools', 'fr': '&Outils'},

    # Podcasts
    'podcasts': {'en': 'Podcasts', 'fr': 'Podcasts'},
    'podcast_shows': {'en': 'Shows', 'fr': 'Émissions'},
    'podcast_episodes': {'en': 'Episodes', 'fr': 'Épisodes'},
    'podcast_subscribe': {'en': 'Subscribe to Podcast...', 'fr': 'S\'abonner à un podcast...'},
    'podcast_subscribe_tip': {'en': 'Add a podcast by RSS feed URL', 'fr': 'Ajouter un podcast par URL de flux RSS'},
    'podcast_subscribed': {'en': 'Podcast subscribed successfully', 'fr': 'Abonnement au podcast réussi'},
    'podcast_search': {'en': 'Search Podcasts Online...', 'fr': 'Chercher des podcasts en ligne...'},
    'podcast_search_tip': {'en': 'Search iTunes podcast directory', 'fr': 'Chercher dans le répertoire de podcasts iTunes'},
    'podcast_refresh': {'en': 'Refresh Feeds', 'fr': 'Actualiser les flux'},
    'podcast_refresh_tip': {'en': 'Check all feeds for new episodes', 'fr': 'Vérifier les nouveaux épisodes de tous les flux'},
    'podcast_download': {'en': 'Download Episode', 'fr': 'Télécharger l\'épisode'},
    'podcast_download_tip': {'en': 'Download this episode for offline listening', 'fr': 'Télécharger cet épisode pour écoute hors ligne'},
    'podcast_download_all': {'en': 'Download All New', 'fr': 'Tout télécharger'},
    'podcast_mark_listened': {'en': 'Mark as Listened', 'fr': 'Marquer comme écouté'},
    'podcast_mark_new': {'en': 'Mark as New', 'fr': 'Marquer comme nouveau'},
    'podcast_delete': {'en': 'Unsubscribe', 'fr': 'Se désabonner'},
    'podcast_delete_confirm': {'en': 'Unsubscribe from this podcast?\nDownloaded episodes will be deleted.',
                               'fr': 'Se désabonner de ce podcast ?\nLes épisodes téléchargés seront supprimés.'},
    'podcast_feed_url': {'en': 'Feed URL:', 'fr': 'URL du flux :'},
    'podcast_importing': {'en': 'Importing podcasts...', 'fr': 'Import des podcasts...'},
    'podcast_import_done': {'en': '{shows} shows, {episodes} episodes imported',
                            'fr': '{shows} émissions, {episodes} épisodes importés'},
    'podcast_downloading': {'en': 'Downloading episodes...', 'fr': 'Téléchargement des épisodes...'},
    'podcast_stats': {'en': '{podcasts} podcasts, {episodes} episodes', 'fr': '{podcasts} podcasts, {episodes} épisodes'},
    'sidebar_podcasts_tip': {'en': 'Browse and manage podcasts', 'fr': 'Parcourir et gérer les podcasts'},
    'col_podcast': {'en': 'Podcast', 'fr': 'Podcast'},
    'col_published': {'en': 'Published', 'fr': 'Date'},
    'col_listened': {'en': 'Listened', 'fr': 'Écouté'},
    'col_downloaded': {'en': 'Downloaded', 'fr': 'Téléchargé'},

    # CD Ripping
    'cd_rip': {'en': 'Import Audio CD...', 'fr': 'Importer un CD audio...'},
    'cd_rip_tip': {'en': 'Rip audio CD to FLAC and add to library', 'fr': 'Extraire un CD audio en FLAC et ajouter à la bibliothèque'},
    'cd_no_drive': {'en': 'No CD drive detected', 'fr': 'Aucun lecteur CD détecté'},
    'cd_no_disc': {'en': 'No audio CD in drive', 'fr': 'Pas de CD audio dans le lecteur'},
    'cd_detecting': {'en': 'Detecting CD...', 'fr': 'Détection du CD...'},
    'cd_ripping': {'en': 'Ripping CD: {track}/{total}...', 'fr': 'Extraction du CD : {track}/{total}...'},
    'cd_rip_done': {'en': 'CD ripped: {tracks} tracks to {dir}', 'fr': 'CD extrait : {tracks} pistes vers {dir}'},
    'cd_rip_error': {'en': 'CD rip failed: {error}', 'fr': 'Échec de l\'extraction : {error}'},
    'cd_lookup': {'en': 'Looking up CD on MusicBrainz...', 'fr': 'Recherche du CD sur MusicBrainz...'},
    'cd_output_dir': {'en': 'Output directory:', 'fr': 'Dossier de destination :'},
    'cd_format': {'en': 'Output format:', 'fr': 'Format de sortie :'},

    # Harmonization
    'harmonize': {'en': 'Harmonize Metadata...', 'fr': 'Harmoniser les métadonnées...'},
    'harmonize_tip': {'en': 'Normalize artist names, composers, album titles', 'fr': 'Normaliser les noms d\'artistes, compositeurs, titres d\'albums'},
    'harmonize_preview': {'en': 'Preview Changes', 'fr': 'Aperçu des changements'},
    'harmonize_apply': {'en': 'Apply Changes', 'fr': 'Appliquer les changements'},
    'harmonize_running': {'en': 'Harmonizing: {current}/{total}...', 'fr': 'Harmonisation : {current}/{total}...'},
    'harmonize_done': {'en': 'Harmonization complete: {artists} artists, {albums} albums, {composers} composers, {genres} genres normalized',
                       'fr': 'Harmonisation terminée : {artists} artistes, {albums} albums, {composers} compositeurs, {genres} genres normalisés'},
    'harmonize_artists': {'en': 'Normalize Artists', 'fr': 'Normaliser les artistes'},
    'harmonize_composers': {'en': 'Normalize Composers', 'fr': 'Normaliser les compositeurs'},
    'harmonize_albums': {'en': 'Clean Album Titles', 'fr': 'Nettoyer les titres d\'albums'},
    'harmonize_genres': {'en': 'Normalize Genres', 'fr': 'Normaliser les genres'},
    'harmonize_duplicates': {'en': 'Find Duplicates', 'fr': 'Chercher les doublons'},
    'harmonize_merge': {'en': 'Merge Selected', 'fr': 'Fusionner la sélection'},
    'harmonize_undo': {'en': 'Undo Last Harmonization', 'fr': 'Annuler la dernière harmonisation'},

    # Import general
    'import_podcasts': {'en': 'Import iTunes Podcasts...', 'fr': 'Importer les podcasts iTunes...'},
    'import_podcasts_tip': {'en': 'Import podcasts from iTunes library', 'fr': 'Importer les podcasts depuis la bibliothèque iTunes'},

    # Enhanced search
    'search_all': {'en': 'All', 'fr': 'Tout'},
    'search_music': {'en': 'Music', 'fr': 'Musique'},
    'search_podcasts': {'en': 'Podcasts', 'fr': 'Podcasts'},
    'search_advanced': {'en': 'Advanced Search...', 'fr': 'Recherche avancée...'},
    'search_advanced_tip': {'en': 'Search with filters (artist, album, year, genre...)',
                            'fr': 'Rechercher avec filtres (artiste, album, année, genre...)'},

    # Content tabs
    'tab_music': {'en': 'Music', 'fr': 'Musique'},
    'tab_podcasts': {'en': 'Podcasts', 'fr': 'Podcasts'},
    'tab_audiobooks': {'en': 'Audiobooks', 'fr': 'Livres audio'},

    # Now playing
    'now_playing': {'en': 'Now Playing', 'fr': 'En cours de lecture'},
    'queue_clear': {'en': 'Clear Queue', 'fr': 'Vider la file'},
    'queue_count': {'en': '{count} tracks in queue', 'fr': '{count} pistes en file'},

    # Statistics
    'stats_title': {'en': 'Library Statistics', 'fr': 'Statistiques de la bibliothèque'},
    'stats_menu': {'en': 'Library Statistics...', 'fr': 'Statistiques de la bibliothèque...'},
    'stats_menu_tip': {'en': 'Show detailed library statistics', 'fr': 'Afficher les statistiques détaillées de la bibliothèque'},
    'stats_overview': {'en': 'Overview', 'fr': 'Vue d\'ensemble'},
    'stats_tracks': {'en': 'Tracks', 'fr': 'Pistes'},
    'stats_albums': {'en': 'Albums', 'fr': 'Albums'},
    'stats_artists': {'en': 'Artists', 'fr': 'Artistes'},
    'stats_playlists': {'en': 'Playlists', 'fr': 'Playlists'},
    'stats_podcasts': {'en': 'Podcasts', 'fr': 'Podcasts'},
    'stats_episodes': {'en': 'Episodes', 'fr': 'Épisodes'},
    'stats_episodes_dl': {'en': 'Downloaded', 'fr': 'Téléchargés'},
    'stats_total_duration': {'en': 'Total Duration', 'fr': 'Durée totale'},
    'stats_total_size': {'en': 'Total Size on Disk', 'fr': 'Taille totale sur le disque'},
    'stats_avg_duration': {'en': 'Average Duration', 'fr': 'Durée moyenne'},
    'stats_avg_bitrate': {'en': 'Average Bitrate', 'fr': 'Débit moyen'},
    'stats_formats': {'en': 'Format Distribution', 'fr': 'Répartition par format'},
    'stats_quality': {'en': 'Audio Quality', 'fr': 'Qualité audio'},
    'stats_top_artists': {'en': 'Top Artists (by tracks)', 'fr': 'Artistes principaux (par pistes)'},
    'stats_top_genres': {'en': 'Top Genres', 'fr': 'Genres principaux'},
    'stats_top_played': {'en': 'Most Played', 'fr': 'Les plus écoutés'},
    'stats_year_range': {'en': 'Year Range', 'fr': 'Période'},
    'stats_lossless': {'en': 'Lossless', 'fr': 'Sans perte'},
    'stats_lossy': {'en': 'Lossy', 'fr': 'Avec perte'},
    'stats_hires': {'en': 'Hi-Res', 'fr': 'Hi-Res'},
    'stats_cd_quality': {'en': 'CD Quality', 'fr': 'Qualité CD'},
    'stats_scan_folders': {'en': 'Scan Folders', 'fr': 'Dossiers scannés'},
    'stats_db_size': {'en': 'Database Size', 'fr': 'Taille de la base'},
    'stats_last_scan': {'en': 'Last Scan', 'fr': 'Dernier scan'},
}


def detect_language():
    """Detect system language, default to English."""
    global _LANG
    try:
        # getlocale() is preferred over deprecated getdefaultlocale()
        loc = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ''
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
