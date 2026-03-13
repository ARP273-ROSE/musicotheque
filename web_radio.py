"""Web Radio module for MusicOthèque.

Provides a curated list of internet radio stations with streaming URLs,
organized by category. Focused on classical music, French culture,
and international news.
"""

# Radio station categories
CATEGORY_CLASSICAL = 'classical'
CATEGORY_FOLK = 'folk'
CATEGORY_NEWS = 'news'
CATEGORY_CULTURE = 'culture'
CATEGORY_ECLECTIC = 'eclectic'

# Category display order and i18n keys
CATEGORIES = [
    (CATEGORY_CLASSICAL, 'radio_cat_classical'),
    (CATEGORY_FOLK,      'radio_cat_folk'),
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

    # --- Classical Music (United Kingdom) ---
    {
        'name': 'BBC Radio 3',
        'url': 'https://as-hls-ww.live.cf.md.bbci.co.uk/pool_23461179/live/ww/bbc_radio_three/bbc_radio_three.isml/bbc_radio_three-audio=96000.norewind.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'GB',
        'language': 'en',
    },
    {
        'name': 'Classic FM',
        'url': 'http://media-ice.musicradio.com/ClassicFMMP3',
        'category': CATEGORY_CLASSICAL,
        'country': 'GB',
        'language': 'en',
    },

    # --- Classical Music (Germany) ---
    {
        'name': 'BR-Klassik',
        'url': 'https://dispatcher.rndfnk.com/br/brklassik/live/mp3/high',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'NDR Kultur',
        'url': 'http://icecast.ndr.de/ndr/ndrkultur/live/mp3/128/stream.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'WDR 3',
        'url': 'https://wdr-wdr3-live.icecast.wdr.de/wdr/wdr3/live/mp3/256/stream.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'SWR Kultur',
        'url': 'https://liveradio.swr.de/sw282p3/swrkultur/play.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'Deutschlandfunk Kultur',
        'url': 'https://st02.sslstream.dlf.de/dlf/02/128/mp3/stream.mp3',
        'category': CATEGORY_CULTURE,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'Klassik Radio',
        'url': 'https://stream.klassikradio.de/live/mp3-192/www.klassikradio.de/',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'Klassik Radio Opera',
        'url': 'http://stream.klassikradio.de/opera/mp3-192/www.klassikradio.de/',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'HR2 Kultur',
        'url': 'https://hr-hr2-live.cast.addradio.de/hr/hr2/live/mp3/128/stream.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },
    {
        'name': 'MDR Klassik',
        'url': 'https://mdr-284350-0.cast.mdr.de/mdr/284350/0/mp3/high/stream.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'DE',
        'language': 'de',
    },

    # --- Classical Music (Austria) ---
    {
        'name': 'ORF \u00d61',
        'url': 'https://orf-live.ors-shoutcast.at/oe1-q2a',
        'category': CATEGORY_CLASSICAL,
        'country': 'AT',
        'language': 'de',
    },

    # --- Classical Music (Switzerland) ---
    {
        'name': 'RTS Espace 2',
        'url': 'https://stream.srg-ssr.ch/m/espace-2/mp3_128',
        'category': CATEGORY_CLASSICAL,
        'country': 'CH',
        'language': 'fr',
    },
    {
        'name': 'Radio Swiss Classic',
        'url': 'http://stream.srg-ssr.ch/m/rsc_de/mp3_128',
        'category': CATEGORY_CLASSICAL,
        'country': 'CH',
        'language': 'de',
    },

    # --- Classical Music (Italy) ---
    {
        'name': 'Rai Radio 3 Classica',
        'url': 'http://icestreaming.rai.it/5.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'IT',
        'language': 'it',
    },

    # --- Classical Music (Netherlands) ---
    {
        'name': 'NPO Radio 4',
        'url': 'http://icecast.omroep.nl/radio4-bb-mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'NL',
        'language': 'nl',
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
        'name': 'Concertzender Oude Muziek',
        'url': 'https://streams.greenhost.nl:8006/oudemuziek',
        'category': CATEGORY_CLASSICAL,
        'country': 'NL',
        'language': 'nl',
    },

    # --- Classical Music (Belgium) ---
    {
        'name': 'Klara (VRT)',
        'url': 'http://icecast.vrtcdn.be/klara-high.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'BE',
        'language': 'nl',
    },
    {
        'name': 'Klara Continuo',
        'url': 'http://icecast.vrtcdn.be/klaracontinuo-high.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'BE',
        'language': 'nl',
    },
    {
        'name': 'Musiq3 (RTBF)',
        'url': 'https://radio.rtbf.be/musiq3/mp3-320',
        'category': CATEGORY_CLASSICAL,
        'country': 'BE',
        'language': 'fr',
    },

    # --- Classical Music (Spain) ---
    {
        'name': 'Radio Cl\u00e1sica (RNE)',
        'url': 'https://rtvelivestream.akamaized.net/rtvesec/rne/rne_r2_main.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'ES',
        'language': 'es',
    },

    # --- Classical Music (Portugal) ---
    {
        'name': 'Antena 2 (RTP)',
        'url': 'https://streaming-live.rtp.pt/liveradio/antena280a/playlist.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'PT',
        'language': 'pt',
    },

    # --- Classical Music (Poland) ---
    {
        'name': 'Polskie Radio Dw\u00f3jka',
        'url': 'https://stream12.polskieradio.pl/pr2/pr2.sdp/playlist.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'PL',
        'language': 'pl',
    },
    {
        'name': 'Radio Chopin',
        'url': 'https://stream85.polskieradio.pl/live/rytm.sdp/playlist.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'PL',
        'language': 'pl',
    },

    # --- Classical Music (Czech Republic) ---
    {
        'name': '\u010cRo Vltava',
        'url': 'http://icecast5.play.cz:8000/cro3-128.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'CZ',
        'language': 'cs',
    },

    # --- Classical Music (Hungary) ---
    {
        'name': 'Bart\u00f3k R\u00e1di\u00f3 (MR3)',
        'url': 'https://mr-stream.connectmedia.hu/4741/mr3.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'HU',
        'language': 'hu',
    },

    # --- Classical Music (Romania) ---
    {
        'name': 'Radio Rom\u00e2nia Muzical',
        'url': 'https://stream2.srr.ro:9012/romania_muzical',
        'category': CATEGORY_CLASSICAL,
        'country': 'RO',
        'language': 'ro',
    },

    # --- Classical Music (Slovenia) ---
    {
        'name': 'Radio Ars (RTV SLO)',
        'url': 'http://mp3.rtvslo.si/ars',
        'category': CATEGORY_CLASSICAL,
        'country': 'SI',
        'language': 'sl',
    },

    # --- Classical Music (Scandinavia) ---
    {
        'name': 'Sveriges Radio P2',
        'url': 'https://live1.sr.se/p2-mp3-96',
        'category': CATEGORY_CLASSICAL,
        'country': 'SE',
        'language': 'sv',
    },
    {
        'name': 'NRK Klassisk',
        'url': 'http://lyd.nrk.no/nrk_radio_klassisk_mp3_h',
        'category': CATEGORY_CLASSICAL,
        'country': 'NO',
        'language': 'no',
    },
    {
        'name': 'DR P2 Klassisk',
        'url': 'http://live-icy.gss.dr.dk:8000/A/A04H.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'DK',
        'language': 'da',
    },
    {
        'name': 'YLE Klassinen',
        'url': 'https://icecast.live.yle.fi/radio/YleKlassinen/icecast.audio',
        'category': CATEGORY_CLASSICAL,
        'country': 'FI',
        'language': 'fi',
    },

    # --- Classical Music (Baltic States) ---
    {
        'name': 'Klassikaraadio (ERR)',
        'url': 'http://icecast.err.ee/klassikaraadio.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'EE',
        'language': 'et',
    },
    {
        'name': 'Latvijas Radio 3 Klasika',
        'url': 'http://muste.radio.org.lv:1935/shoutcast/lr3a.stream/playlist.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'LV',
        'language': 'lv',
    },
    {
        'name': 'LRT Klasika',
        'url': 'https://radijas.lrt.lt/klasika_mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'LT',
        'language': 'lt',
    },

    # --- Classical Music (Croatia) ---
    {
        'name': 'HR3 (HRT)',
        'url': 'https://livehr3.hrt.hr/hr3_stereo',
        'category': CATEGORY_CLASSICAL,
        'country': 'HR',
        'language': 'hr',
    },

    # --- Classical Music (Bulgaria) ---
    {
        'name': 'BNR Hristo Botev',
        'url': 'https://live.bnr.bg/bhr_high.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'BG',
        'language': 'bg',
    },

    # --- Classical Music (Israel) ---
    {
        'name': 'Kol HaMusica',
        'url': 'https://mediacast.iba.org.il/ibamusicmp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'IL',
        'language': 'he',
    },

    # --- Classical Music (USA) ---
    {
        'name': 'WQXR New York',
        'url': 'https://stream.wqxr.org/wqxr',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'WQXR Operavore',
        'url': 'https://opera-stream.wqxr.org/operavore',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'KUSC Los Angeles',
        'url': 'https://playerservices.streamtheworld.com/pls/KUSCAAC96.pls',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'WFMT Chicago',
        'url': 'http://wowza.wfmt.com/live/smil:wfmt.smil/playlist.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },

    {
        'name': 'Classical KING FM (Seattle)',
        'url': 'https://classicalking.streamguys1.com/king-fm-aac-128k',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'Classical MPR (Minnesota)',
        'url': 'https://cms.stream.publicradio.org/cms.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'WCPE The Classical Station',
        'url': 'http://audio-mp3.ibiblio.org:8000/wcpe.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'WRTI Classical (Philadelphia)',
        'url': 'http://playerservices.streamtheworld.com/api/livestream-redirect/WRTI_CLASSICAL.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },
    {
        'name': 'WWFM Classical Network',
        'url': 'https://wwfm.streamguys1.com/live-mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'US',
        'language': 'en',
    },

    # --- Classical Music (Canada) ---
    {
        'name': 'CBC Music Classical',
        'url': 'http://playerservices.streamtheworld.com/pls/CBC_R2CLAS_H.pls',
        'category': CATEGORY_CLASSICAL,
        'country': 'CA',
        'language': 'en',
    },

    # --- Classical Music (Australia) ---
    {
        'name': 'ABC Classic',
        'url': 'https://live-radio02.mediahubaustralia.com/2FMW/mp3/',
        'category': CATEGORY_CLASSICAL,
        'country': 'AU',
        'language': 'en',
    },

    # --- Classical Music (Japan) ---
    {
        'name': 'OTTAVA',
        'url': 'https://sslv.smartstream.ne.jp/ottava/_definst_/live01/chunklist.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'JP',
        'language': 'ja',
    },

    # --- Classical Music (South Korea) ---
    {
        'name': 'KBS Classic FM',
        'url': 'https://kong.kbs.co.kr/listener/lo_1fm.m3u8',
        'category': CATEGORY_CLASSICAL,
        'country': 'KR',
        'language': 'ko',
    },

    # --- Classical Music (Internet-only) ---
    {
        'name': 'Venice Classic Radio',
        'url': 'https://uk2.streamingpulse.com/ssl/vcr1',
        'category': CATEGORY_CLASSICAL,
        'country': 'IT',
        'language': 'it',
    },

    # --- Classical Music (Russia) ---
    {
        'name': 'Radio Orpheus',
        'url': 'http://orfeyfm.hostingradio.ru:8034/orfeyfm128.mp3',
        'category': CATEGORY_CLASSICAL,
        'country': 'RU',
        'language': 'ru',
    },

    # --- Classical Music (Greece) ---
    {
        'name': 'ERT Trito (Third Programme)',
        'url': 'https://radiostreaming.ert.gr/ert-trito',
        'category': CATEGORY_CLASSICAL,
        'country': 'GR',
        'language': 'el',
    },

    # --- Greek Traditional / Folk ---
    {
        'name': 'ERT Paradosiaka',
        'url': 'https://radiostreaming.ert.gr/ert-defteroparadosiaka',
        'category': CATEGORY_FOLK,
        'country': 'GR',
        'language': 'el',
    },
    {
        'name': 'ERT Laika',
        'url': 'https://radiostreaming.ert.gr/ert-talaika',
        'category': CATEGORY_FOLK,
        'country': 'GR',
        'language': 'el',
    },
    {
        'name': 'Pame Rebetiko',
        'url': 'https://stream.zeno.fm/wqcp8gq67vzuv',
        'category': CATEGORY_FOLK,
        'country': 'GR',
        'language': 'el',
    },
    {
        'name': 'Rembetiko Gia Ligous',
        'url': 'http://stream.radiojar.com/k55d9sumb.mp3',
        'category': CATEGORY_FOLK,
        'country': 'GR',
        'language': 'el',
    },
    {
        'name': 'Derti 98.6 (Laika)',
        'url': 'http://derti.live24.gr/derty1000',
        'category': CATEGORY_FOLK,
        'country': 'GR',
        'language': 'el',
    },

    # --- Greek Culture ---
    {
        'name': 'ERT Proto (Voice of Greece)',
        'url': 'https://radiostreaming.ert.gr/ert-proto',
        'category': CATEGORY_CULTURE,
        'country': 'GR',
        'language': 'el',
    },
    {
        'name': 'ERT Deytero',
        'url': 'https://radiostreaming.ert.gr/ert-deytero',
        'category': CATEGORY_CULTURE,
        'country': 'GR',
        'language': 'el',
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
        'name': 'Europe 1',
        'url': 'https://stream.europe1.fr/europe1.mp3',
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
    'AT': '\U0001f1e6\U0001f1f9',  # Austria
    'AU': '\U0001f1e6\U0001f1fa',  # Australia
    'BE': '\U0001f1e7\U0001f1ea',  # Belgium
    'BG': '\U0001f1e7\U0001f1ec',  # Bulgaria
    'CA': '\U0001f1e8\U0001f1e6',  # Canada
    'CH': '\U0001f1e8\U0001f1ed',  # Switzerland
    'CZ': '\U0001f1e8\U0001f1ff',  # Czech Republic
    'DE': '\U0001f1e9\U0001f1ea',  # Germany
    'DK': '\U0001f1e9\U0001f1f0',  # Denmark
    'EE': '\U0001f1ea\U0001f1ea',  # Estonia
    'ES': '\U0001f1ea\U0001f1f8',  # Spain
    'FI': '\U0001f1eb\U0001f1ee',  # Finland
    'FR': '\U0001f1eb\U0001f1f7',  # France
    'GB': '\U0001f1ec\U0001f1e7',  # United Kingdom
    'GR': '\U0001f1ec\U0001f1f7',  # Greece
    'HR': '\U0001f1ed\U0001f1f7',  # Croatia
    'HU': '\U0001f1ed\U0001f1fa',  # Hungary
    'IL': '\U0001f1ee\U0001f1f1',  # Israel
    'IT': '\U0001f1ee\U0001f1f9',  # Italy
    'JP': '\U0001f1ef\U0001f1f5',  # Japan
    'KR': '\U0001f1f0\U0001f1f7',  # South Korea
    'LT': '\U0001f1f1\U0001f1f9',  # Lithuania
    'LV': '\U0001f1f1\U0001f1fb',  # Latvia
    'NL': '\U0001f1f3\U0001f1f1',  # Netherlands
    'NO': '\U0001f1f3\U0001f1f4',  # Norway
    'PL': '\U0001f1f5\U0001f1f1',  # Poland
    'PT': '\U0001f1f5\U0001f1f9',  # Portugal
    'RO': '\U0001f1f7\U0001f1f4',  # Romania
    'RU': '\U0001f1f7\U0001f1fa',  # Russia
    'SE': '\U0001f1f8\U0001f1ea',  # Sweden
    'SI': '\U0001f1f8\U0001f1ee',  # Slovenia
    'US': '\U0001f1fa\U0001f1f8',  # United States
}


def station_display_name(station):
    """Return display name with country flag or code.

    Windows does not render flag emojis — use [XX] country code instead.
    macOS and Linux render flags natively.
    """
    import platform
    country = station.get('country', '')
    name = station.get('name', '')
    if not country:
        return name
    if platform.system() == 'Windows':
        return f"[{country}] {name}"
    flag = COUNTRY_FLAGS.get(country, '')
    return f"{flag} {name}" if flag else f"[{country}] {name}"
