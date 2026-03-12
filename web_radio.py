"""Web Radio module for MusicOthèque.

Provides a curated list of internet radio stations with streaming URLs,
organized by category. Focused on classical music, French culture,
and international news.
"""

# Radio station categories
CATEGORY_CLASSICAL = 'classical'
CATEGORY_NEWS = 'news'
CATEGORY_CULTURE = 'culture'
CATEGORY_ECLECTIC = 'eclectic'

# Category display order and i18n keys
CATEGORIES = [
    (CATEGORY_CLASSICAL, 'radio_cat_classical'),
    (CATEGORY_CULTURE,   'radio_cat_culture'),
    (CATEGORY_NEWS,      'radio_cat_news'),
    (CATEGORY_ECLECTIC,  'radio_cat_eclectic'),
]

# Curated radio stations
# Each entry: name, url, category, country code, language
RADIO_STATIONS = [
    # --- Classical Music (France) ---
    {
        'name': 'France Musique',
        'url': 'https://icecast.radiofrance.fr/francemusique-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique Baroque',
        'url': 'https://icecast.radiofrance.fr/francemusiquebaroque-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique Classique Plus',
        'url': 'https://icecast.radiofrance.fr/francemusiqueclassiqueplus-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique Concerts',
        'url': 'https://icecast.radiofrance.fr/francemusiqueconcertsradiofrance-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique Easy Classique',
        'url': 'https://icecast.radiofrance.fr/francemusiqueeasyclassique-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique La Contemporaine',
        'url': 'https://icecast.radiofrance.fr/francemusiquelacontemporaine-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique Jazz',
        'url': 'https://icecast.radiofrance.fr/francemusiquelajazz-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Musique Ocora Monde',
        'url': 'https://icecast.radiofrance.fr/francemusiqueocoramonde-hifi.aac?id=radiofrance',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'Radio Classique',
        'url': 'https://radioclassique.ice.infomaniak.ch/radioclassique-high.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'FR',
        'language': 'fr',
    },

    # --- Classical Music (International) ---
    {
        'name': 'BBC Radio 3',
        'url': 'http://stream.live.vc.bbcmedia.co.uk/bbc_radio_three',
        'category': CATEGORY_CLASSICAL,
        'country': 'GB',
        'language': 'en',
    },
    {
        'name': 'Rai Radio 3 Classica',
        'url': 'http://icestreaming.rai.it/5.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'IT',
        'language': 'it',
    },
    {
        'name': 'RTS Espace 2',
        'url': 'https://stream.srg-ssr.ch/m/espace-2/mp3_128',
        'category': CATEGORY_CLASSICAL,
        'country': 'CH',
        'language': 'fr',
    },
    {
        'name': 'WQXR New York',
        'url': 'https://stream.wqxr.org/wqxr',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'BR-Klassik',
        'url': 'https://dispatcher.rndfnk.com/br/brklassik/live/mp3/high',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'Concertzender',
        'url': 'https://streams.greenhost.nl:8006/live',
        'category': CATEGORY_CLASSICAL,
        'country': 'NL',
        'language': 'nl',
    },
    {
        'name': 'Concertzender Klassiek',
        'url': 'https://streams.greenhost.nl:8006/klassiek',
        'category': CATEGORY_CLASSICAL,
        'country': 'NL',
        'language': 'nl',
    },
    {
        'name': 'ABC Classic',
        'url': 'https://live-radio02.mediahubaustralia.com/2FMW/mp3/',
        'category': CATEGORY_CLASSICAL,
        'country': 'AU',
        'language': 'en',
    },

    # --- Culture ---
    {
        'name': 'France Culture',
        'url': 'https://icecast.radiofrance.fr/franceculture-hifi.aac?id=radiofrance',
        'category': CATEGORY_CULTURE,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'France Inter',
        'url': 'https://icecast.radiofrance.fr/franceinter-hifi.aac?id=radiofrance',
        'category': CATEGORY_CULTURE,
        'country': 'FR',
        'language': 'fr',
    },

    # --- News ---
    {
        'name': 'Franceinfo',
        'url': 'https://icecast.radiofrance.fr/franceinfo-hifi.aac?id=radiofrance',
        'category': CATEGORY_NEWS,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'BBC World Service',
        'url': 'http://stream.live.vc.bbcmedia.co.uk/bbc_world_service',
        'category': CATEGORY_NEWS,
        'country': 'GB',
        'language': 'en',
    },
    {
        'name': 'NPR (WNYC)',
        'url': 'https://fm939.wnyc.org/wnycfm',
        'category': CATEGORY_NEWS,
        'country': 'US',
        'language': 'en',
    },

    # --- Eclectic / Other ---
    {
        'name': 'FIP',
        'url': 'https://icecast.radiofrance.fr/fip-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP Rock',
        'url': 'https://icecast.radiofrance.fr/fiprock-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP Jazz',
        'url': 'https://icecast.radiofrance.fr/fipjazz-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP Electro',
        'url': 'https://icecast.radiofrance.fr/fipelectro-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP World',
        'url': 'https://icecast.radiofrance.fr/fipworld-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP Groove',
        'url': 'https://icecast.radiofrance.fr/fipgroove-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP Pop',
        'url': 'https://icecast.radiofrance.fr/fippop-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
    {
        'name': 'FIP Nouveautés',
        'url': 'https://icecast.radiofrance.fr/fipnouveautes-hifi.aac?id=radiofrance',
        'category': CATEGORY_ECLECTIC,
        'country': 'FR',
        'language': 'fr',
    },
]


def get_stations_by_category(category):
    """Return stations for a given category."""
    return [s for s in RADIO_STATIONS if s['category'] == category]


def get_all_stations_in_category_order():
    """Return all stations grouped by category in display order."""
    result = []
    for cat_id, _ in CATEGORIES:
        stations = get_stations_by_category(cat_id)
        if stations:
            result.append((cat_id, stations))
    return result


def find_station_by_url(url):
    """Find a station by its stream URL."""
    for s in RADIO_STATIONS:
        if s['url'] == url:
            return s
    return None


# Country flag emoji mapping
COUNTRY_FLAGS = {
    'FR': '\U0001f1eb\U0001f1f7',
    'GB': '\U0001f1ec\U0001f1e7',
    'IT': '\U0001f1ee\U0001f1f9',
    'CH': '\U0001f1e8\U0001f1ed',
    'US': '\U0001f1fa\U0001f1f8',
    'DE': '\U0001f1e9\U0001f1ea',
    'NL': '\U0001f1f3\U0001f1f1',
    'AU': '\U0001f1e6\U0001f1fa',
}


def station_display_name(station):
    """Return display name with country flag."""
    flag = COUNTRY_FLAGS.get(station.get('country', ''), '')
    name = station.get('name', '')
    return f"{flag} {name}" if flag else name
