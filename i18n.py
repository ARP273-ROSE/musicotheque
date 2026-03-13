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
    'view_periods': {'en': 'Periods', 'fr': 'Époques'},
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
    'col_disc_num': {'en': 'Disc', 'fr': 'CD'},
    'col_composer': {'en': 'Composer', 'fr': 'Compositeur'},
    'col_period': {'en': 'Period', 'fr': 'Période'},
    'col_movement': {'en': 'Movement', 'fr': 'Mouvement'},
    'col_sub_period': {'en': 'Sub-period', 'fr': 'Sous-période'},
    'col_form': {'en': 'Form', 'fr': 'Forme'},
    'col_catalogue': {'en': 'Catalogue', 'fr': 'Catalogue'},
    'col_instruments': {'en': 'Instruments', 'fr': 'Instruments'},
    'col_music_key': {'en': 'Key', 'fr': 'Tonalité'},
    'col_channels': {'en': 'Channels', 'fr': 'Canaux'},
    'col_file_size': {'en': 'Size', 'fr': 'Taille'},
    'col_file_path': {'en': 'Path', 'fr': 'Chemin'},
    'col_added_at': {'en': 'Added', 'fr': 'Ajouté'},
    'choose_columns': {'en': 'Choose Columns...', 'fr': 'Choisir les colonnes...'},
    'show_all_columns': {'en': 'Show All', 'fr': 'Tout afficher'},
    'reset_columns': {'en': 'Reset to Default', 'fr': 'Colonnes par défaut'},

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
    'create_shortcut': {'en': 'Create Desktop Shortcut', 'fr': 'Créer raccourci bureau'},
    'create_shortcut_tip': {'en': 'Create or update the desktop shortcut', 'fr': 'Créer ou mettre à jour le raccourci sur le bureau'},

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
    'sidebar_periods_tip': {'en': 'Browse by musical period (Baroque, Classical, Romantic...)',
                            'fr': 'Parcourir par époque musicale (Baroque, Classique, Romantique...)'},
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

    # Smart Radio
    'smart_radio': {'en': 'Smart Radio', 'fr': 'Radio intelligente'},
    'smart_radio_tip': {'en': 'Play random tracks with smart filters', 'fr': 'Lire des pistes aléatoires avec filtres intelligents'},
    'smart_radio_title': {'en': 'Smart Radio', 'fr': 'Radio Intelligente'},
    'filter_genre': {'en': 'Genre:', 'fr': 'Genre :'},
    'filter_artist': {'en': 'Artist:', 'fr': 'Artiste :'},
    'filter_composer': {'en': 'Composer:', 'fr': 'Compositeur :'},
    'filter_album': {'en': 'Album:', 'fr': 'Album :'},
    'filter_era': {'en': 'Era:', 'fr': 'Époque :'},
    'filter_year_from': {'en': 'Year from:', 'fr': 'Année de :'},
    'filter_year_to': {'en': 'to:', 'fr': 'à :'},
    'filter_quality': {'en': 'Quality:', 'fr': 'Qualité :'},
    'filter_rating_min': {'en': 'Min. rating:', 'fr': 'Note min. :'},
    'filter_unplayed': {'en': 'Only unplayed tracks', 'fr': 'Pistes jamais écoutées uniquement'},
    'filter_all': {'en': '— All —', 'fr': '— Tous —'},
    'filter_all_f': {'en': '— All —', 'fr': '— Toutes —'},
    'era_medieval': {'en': 'Medieval (before 1400)', 'fr': 'Médiéval (avant 1400)'},
    'era_renaissance': {'en': 'Renaissance (1400–1600)', 'fr': 'Renaissance (1400–1600)'},
    'era_baroque': {'en': 'Baroque (1600–1750)', 'fr': 'Baroque (1600–1750)'},
    'era_classical': {'en': 'Classical (1750–1820)', 'fr': 'Classique (1750–1820)'},
    'era_romantic': {'en': 'Romantic (1820–1900)', 'fr': 'Romantique (1820–1900)'},
    'era_modern': {'en': 'Modern (1900–1950)', 'fr': 'Moderne (1900–1950)'},
    'era_contemporary': {'en': 'Contemporary (1950–2000)', 'fr': 'Contemporain (1950–2000)'},
    'era_recent': {'en': 'Recent (2000+)', 'fr': 'Récent (2000+)'},
    'era_custom': {'en': 'Custom year range', 'fr': 'Période personnalisée'},
    'quality_all': {'en': '— All —', 'fr': '— Toutes —'},
    'quality_filter_hires': {'en': 'Hi-Res (>48kHz or >16-bit)', 'fr': 'Hi-Res (>48kHz ou >16 bits)'},
    'quality_filter_cd': {'en': 'CD Quality (44.1kHz/16-bit)', 'fr': 'Qualité CD (44.1kHz/16 bits)'},
    'quality_filter_lossless': {'en': 'Lossless (FLAC, ALAC, WAV...)', 'fr': 'Sans perte (FLAC, ALAC, WAV...)'},
    'quality_filter_lossy': {'en': 'Lossy (MP3, AAC, OGG...)', 'fr': 'Avec perte (MP3, AAC, OGG...)'},
    'smart_radio_match': {'en': '{count} tracks match', 'fr': '{count} pistes correspondent'},
    'smart_radio_no_match': {'en': 'No tracks match these filters', 'fr': 'Aucune piste ne correspond à ces filtres'},
    'smart_radio_play_all': {'en': 'Play All Shuffled', 'fr': 'Tout lire en aléatoire'},
    'smart_radio_play_n': {'en': 'Play {count} random tracks', 'fr': 'Lire {count} pistes aléatoires'},
    'smart_radio_limit': {'en': 'Limit:', 'fr': 'Limite :'},
    'smart_radio_unlimited': {'en': 'Unlimited', 'fr': 'Illimité'},

    # Web Radio
    'web_radio': {'en': 'Web Radio', 'fr': 'Web Radio'},
    'web_radio_tip': {'en': 'Listen to internet radio stations worldwide', 'fr': 'Écouter des stations de radio en ligne du monde entier'},
    'radio_cat_classical': {'en': 'Classical', 'fr': 'Classique'},
    'radio_cat_folk': {'en': 'Folk / Traditional', 'fr': 'Folk / Traditionnel'},
    'radio_cat_culture': {'en': 'Culture', 'fr': 'Culture'},
    'radio_cat_news': {'en': 'News', 'fr': 'Info'},
    'radio_cat_eclectic': {'en': 'Eclectic', 'fr': 'Éclectique'},
    'radio_live': {'en': 'LIVE', 'fr': 'EN DIRECT'},
    'radio_stop': {'en': 'Stop Radio', 'fr': 'Arrêter la radio'},

    # Metadata editing
    'edit_metadata': {'en': 'Edit Metadata...', 'fr': 'Modifier les métadonnées...'},
    'edit_metadata_single': {'en': 'Edit Track Metadata', 'fr': 'Modifier les métadonnées de la piste'},
    'edit_metadata_multi': {'en': 'Edit Metadata ({count} tracks)', 'fr': 'Modifier les métadonnées ({count} pistes)'},
    'edit_metadata_tip': {'en': 'Edit metadata for selected tracks', 'fr': 'Modifier les métadonnées des pistes sélectionnées'},
    'meta_title': {'en': 'Title', 'fr': 'Titre'},
    'meta_artist': {'en': 'Artist', 'fr': 'Artiste'},
    'meta_album_artist': {'en': 'Album Artist', 'fr': 'Artiste de l\'album'},
    'meta_album': {'en': 'Album', 'fr': 'Album'},
    'meta_genre': {'en': 'Genre', 'fr': 'Genre'},
    'meta_year': {'en': 'Year', 'fr': 'Année'},
    'meta_track_num': {'en': 'Track #', 'fr': 'Piste #'},
    'meta_disc_num': {'en': 'Disc #', 'fr': 'CD #'},
    'meta_composer': {'en': 'Composer', 'fr': 'Compositeur'},
    'meta_period': {'en': 'Period', 'fr': 'Période'},
    'meta_movement': {'en': 'Movement', 'fr': 'Courant'},
    'meta_sub_period': {'en': 'Sub-period', 'fr': 'Sous-période'},
    'meta_form': {'en': 'Form', 'fr': 'Forme'},
    'meta_catalogue': {'en': 'Catalogue', 'fr': 'Catalogue'},
    'meta_instruments': {'en': 'Instruments', 'fr': 'Instruments'},
    'meta_music_key': {'en': 'Key', 'fr': 'Tonalité'},
    'meta_keep_original': {'en': '(keep original)', 'fr': '(conserver l\'original)'},
    'meta_save_success': {'en': 'Metadata saved for {count} track(s)', 'fr': 'Métadonnées sauvegardées pour {count} piste(s)'},
    'meta_save_error': {'en': 'Error saving metadata for {count} file(s)', 'fr': 'Erreur lors de la sauvegarde pour {count} fichier(s)'},
    'meta_writing_files': {'en': 'Writing metadata to files...', 'fr': 'Écriture des métadonnées dans les fichiers...'},
    'drag_copy_tracks': {'en': 'Copy {count} track(s)', 'fr': 'Copier {count} piste(s)'},

    # Reset play count
    'reset_play_counts': {'en': 'Reset Play Counts', 'fr': 'Réinitialiser les compteurs'},
    'reset_play_counts_tip': {'en': 'Reset all play counts and last played dates', 'fr': 'Réinitialiser tous les compteurs de lecture et dates'},
    'reset_play_counts_confirm': {'en': 'Reset play counts for all {count} tracks?\nThis cannot be undone.', 'fr': 'Réinitialiser les compteurs de lecture pour les {count} pistes ?\nCette action est irréversible.'},
    'reset_play_counts_done': {'en': 'Play counts reset for {count} tracks', 'fr': 'Compteurs réinitialisés pour {count} pistes'},
    'reset_play_count': {'en': 'Reset Play Count', 'fr': 'Réinitialiser le compteur'},
    'reset_play_count_done': {'en': 'Play count reset', 'fr': 'Compteur réinitialisé'},

    # Status messages
    'no_backups_found': {'en': 'No backups found', 'fr': 'Aucune sauvegarde trouvée'},
    'up_to_date': {'en': 'Up to date', 'fr': 'À jour'},
    'no_releases_found': {'en': 'No releases found', 'fr': 'Aucune version trouvée'},
    'update_check_failed': {'en': 'Update check failed', 'fr': 'Échec de la vérification'},
    'no_podcast_subs': {'en': 'No podcast subscriptions', 'fr': 'Aucun abonnement podcast'},
    'cd_ripper_unavailable': {'en': 'CD ripper module not available', 'fr': 'Module CD non disponible'},
    'harmonizer_unavailable': {'en': 'Harmonizer module not available', 'fr': 'Module harmoniseur non disponible'},
    'no_changes_needed': {'en': 'No changes needed', 'fr': 'Aucune modification nécessaire'},
    'update_available': {'en': 'Update available: {current} → {remote}', 'fr': 'Mise à jour disponible : {current} → {remote}'},
    'search_error': {'en': 'Search error', 'fr': 'Erreur de recherche'},

    # Music classification
    'classify_library': {'en': 'Classify Library', 'fr': 'Classifier la bibliothèque'},
    'classify_library_tip': {'en': 'Auto-classify tracks by musical period, form, and instrumentation', 'fr': 'Classifier automatiquement les pistes par période, forme et instrumentation'},
    'classify_running': {'en': 'Classifying tracks...', 'fr': 'Classification en cours...'},
    'classify_done': {'en': 'Classification complete: {count} tracks classified', 'fr': 'Classification terminée : {count} pistes classifiées'},
    'period': {'en': 'Period', 'fr': 'Période'},
    'form': {'en': 'Form', 'fr': 'Forme'},
    'catalogue_num': {'en': 'Catalogue', 'fr': 'Catalogue'},
    'instruments': {'en': 'Instruments', 'fr': 'Instruments'},
    'musical_key': {'en': 'Key', 'fr': 'Tonalité'},
    'track_details': {'en': 'Track Details', 'fr': 'Détails de la piste'},
    'classification': {'en': 'Classification', 'fr': 'Classification'},

    # Audio output / HiFi chain
    'audio_output': {'en': 'Audio Output', 'fr': 'Sortie Audio'},
    'audio_output_tip': {'en': 'Select audio output device (DAC, speakers, headphones)',
                         'fr': 'Sélectionner le périphérique de sortie audio (DAC, enceintes, casque)'},
    'audio_device': {'en': 'Output device:', 'fr': 'Périphérique de sortie :'},
    'audio_device_default': {'en': 'System Default', 'fr': 'Par défaut du système'},
    'audio_device_tip': {'en': 'Audio output device currently in use',
                         'fr': 'Périphérique de sortie audio actuellement utilisé'},
    'audio_device_caps': {'en': 'Capabilities: {rates} · {channels}ch · {formats}',
                          'fr': 'Capacités : {rates} · {channels} canaux · {formats}'},
    'audio_chain_info': {'en': 'Audio chain: source → output device',
                         'fr': 'Chaîne audio : source → périphérique de sortie'},
    'audio_format_display': {'en': '{fmt} · {rate} · {depth}',
                             'fr': '{fmt} · {rate} · {depth}'},
    'audio_exclusive': {'en': 'Exclusive mode (WASAPI)', 'fr': 'Mode exclusif (WASAPI)'},
    'audio_exclusive_tip': {'en': 'Bypass Windows mixer for bit-perfect output (restart required)',
                            'fr': 'Contourner le mixeur Windows pour une sortie bit-perfect (redémarrage requis)'},

    # Audio visualizer
    'visualizer': {'en': 'Audio Visualizer', 'fr': 'Visualiseur audio'},
    'visualizer_tip': {'en': 'Show spectrum analyzer, VU meter, and spectrogram (Ctrl+V)', 'fr': 'Afficher analyseur spectral, VU-mètre et spectrogramme (Ctrl+V)'},

    # Library watcher
    'watcher_changes': {'en': 'Library changes detected: {added} new, {modified} modified, {removed} removed',
                        'fr': 'Changements détectés : {added} nouveaux, {modified} modifiés, {removed} supprimés'},
    'watcher_relocated': {'en': 'Auto-relocated {count} tracks: {old} → {new}',
                          'fr': 'Relocalisation auto de {count} pistes : {old} → {new}'},

    # File organizer
    'organize_library': {'en': 'Organize Files on Disk...', 'fr': 'Organiser les fichiers sur le disque...'},
    'organize_library_tip': {'en': 'Sort music files into Artist/Album/Track folders', 'fr': 'Trier les fichiers dans des dossiers Artiste/Album/Piste'},
    'organize_running': {'en': 'Organizing files: {current}/{total}...', 'fr': 'Organisation des fichiers : {current}/{total}...'},
    'organize_done': {'en': 'Organized {count} files', 'fr': '{count} fichiers organisés'},
    'organize_confirm': {'en': 'Organize {count} tracks into:\n{dest}\n\nStructure: Artist / Album / Track?\n\nThis will MOVE files. Continue?',
                         'fr': 'Organiser {count} pistes dans :\n{dest}\n\nStructure : Artiste / Album / Piste ?\n\nCela va DÉPLACER les fichiers. Continuer ?'},

    # Enrichment
    'enrich_metadata': {'en': 'Enrich Metadata Online...', 'fr': 'Enrichir les métadonnées en ligne...'},
    'enrich_metadata_tip': {'en': 'Fetch missing metadata and cover art from MusicBrainz', 'fr': 'Récupérer les métadonnées et pochettes manquantes depuis MusicBrainz'},

    # Musical movements / styles
    'movement': {'en': 'Movement', 'fr': 'Courant'},
    'sub_period': {'en': 'Sub-period', 'fr': 'Sous-période'},
    'movement_impressionism': {'en': 'Impressionism', 'fr': 'Impressionnisme'},
    'movement_expressionism': {'en': 'Expressionism', 'fr': 'Expressionnisme'},
    'movement_neoclassicism': {'en': 'Neoclassicism', 'fr': 'Néoclassicisme'},
    'movement_serialism': {'en': 'Serialism', 'fr': 'Sérialisme'},
    'movement_minimalism': {'en': 'Minimalism', 'fr': 'Minimalisme'},
    'movement_nationalism': {'en': 'Nationalism', 'fr': 'Nationalisme'},
    'movement_late_romanticism': {'en': 'Late Romanticism', 'fr': 'Romantisme tardif'},
    'movement_avant_garde': {'en': 'Avant-Garde', 'fr': 'Avant-Garde'},
    'movement_film_music': {'en': 'Film Music', 'fr': 'Musique de film'},
    'movement_holy_minimalism': {'en': 'Holy Minimalism', 'fr': 'Minimalisme sacré'},
    'movement_neo_romanticism': {'en': 'Neo-Romanticism', 'fr': 'Néo-romantisme'},
    'movement_spectralism': {'en': 'Spectralism', 'fr': 'Spectralisme'},
    'movement_verismo': {'en': 'Verismo', 'fr': 'Vérisme'},
    'movement_bel_canto': {'en': 'Bel Canto', 'fr': 'Bel Canto'},
    'movement_venetian_school': {'en': 'Venetian School', 'fr': 'École vénitienne'},
    'movement_roman_school': {'en': 'Roman School', 'fr': 'École romaine'},
    'movement_franco_flemish': {'en': 'Franco-Flemish School', 'fr': 'École franco-flamande'},
    'movement_ars_nova': {'en': 'Ars Nova', 'fr': 'Ars Nova'},
    'movement_ars_antiqua': {'en': 'Ars Antiqua', 'fr': 'Ars Antiqua'},

    # Sub-periods
    'sub_early_baroque': {'en': 'Early Baroque (1600–1650)', 'fr': 'Premier Baroque (1600–1650)'},
    'sub_high_baroque': {'en': 'High Baroque (1650–1700)', 'fr': 'Haut Baroque (1650–1700)'},
    'sub_late_baroque': {'en': 'Late Baroque (1700–1750)', 'fr': 'Baroque tardif (1700–1750)'},
    'sub_galant': {'en': 'Galant Style (1720–1770)', 'fr': 'Style galant (1720–1770)'},
    'sub_early_romantic': {'en': 'Early Romantic (1820–1850)', 'fr': 'Début romantique (1820–1850)'},
    'sub_high_romantic': {'en': 'High Romantic (1850–1890)', 'fr': 'Haut romantisme (1850–1890)'},
    'sub_late_romantic': {'en': 'Late Romantic (1890–1910)', 'fr': 'Romantisme tardif (1890–1910)'},
    'sub_fin_de_siecle': {'en': 'Fin de Siècle (1890–1914)', 'fr': 'Fin de siècle (1890–1914)'},
    'sub_interwar': {'en': 'Interwar Modernism (1918–1945)', 'fr': 'Modernisme entre-deux-guerres (1918–1945)'},

    # Periods sidebar (enhanced)
    'view_movements': {'en': 'Movements', 'fr': 'Courants'},
    'sidebar_movements_tip': {'en': 'Browse by musical movement (Impressionism, Minimalism...)',
                               'fr': 'Parcourir par courant musical (Impressionnisme, Minimalisme...)'},

    # Classification enhanced
    'classify_done_detail': {'en': 'Classification complete: {count} tracks classified, {movements} movements detected',
                             'fr': 'Classification terminée : {count} pistes classifiées, {movements} courants détectés'},

    # Migration / first launch / multi-PC robustness
    'migrate_title': {'en': 'Previous Library Found', 'fr': 'Bibliothèque précédente trouvée'},
    'migrate_message': {
        'en': 'A MusicOthèque database was found at:\n{path}\n\n'
              'It contains {tracks} tracks, {playlists} playlists.\n\n'
              'Copy it here for portable multi-PC access?',
        'fr': 'Une base MusicOthèque a été trouvée dans :\n{path}\n\n'
              'Elle contient {tracks} pistes, {playlists} playlists.\n\n'
              'La copier ici pour un accès portable multi-PC ?'},
    'migrate_success': {'en': 'Library migrated successfully! {tracks} tracks imported.',
                        'fr': 'Bibliothèque migrée avec succès ! {tracks} pistes importées.'},
    'migrate_error': {'en': 'Migration failed: {error}', 'fr': 'Échec de la migration : {error}'},

    'welcome_title': {'en': 'Welcome to MusicOthèque', 'fr': 'Bienvenue dans MusicOthèque'},
    'welcome_message': {
        'en': 'Your music library is empty.\n\n'
              'Add a music folder to get started?\n'
              '(You can also do this later from File > Add Music Folder)',
        'fr': 'Votre bibliothèque musicale est vide.\n\n'
              'Ajouter un dossier musical pour commencer ?\n'
              '(Vous pouvez aussi le faire plus tard depuis Fichier > Ajouter un dossier)'},

    'folders_check_title': {'en': 'Unreachable Music Folders', 'fr': 'Dossiers musicaux inaccessibles'},
    'folders_check_message': {
        'en': 'The following music folders are not accessible:\n\n{folders}\n\n'
              'This may happen when launching from a different PC or OS.\n'
              'Use Tools > Relocate Music Paths to update them.',
        'fr': 'Les dossiers musicaux suivants sont inaccessibles :\n\n{folders}\n\n'
              'Cela peut arriver en lançant depuis un autre PC ou OS.\n'
              'Utilisez Outils > Déplacer les chemins musicaux pour les corriger.'},
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
