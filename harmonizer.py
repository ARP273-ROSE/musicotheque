"""Metadata harmonization module for MusicOthèque.

Normalizes and cleans up music metadata: artist names, composers, album titles,
genres. Ensures consistency across a large music library (17,000+ tracks).

Designed for a collection heavy on classical music (Bach 333, Mozart 225,
Beethoven 2020) and film soundtracks (Morricone, Zimmer, Williams).
"""
import re
import logging
import unicodedata
from difflib import SequenceMatcher

from PyQt6.QtCore import QObject, pyqtSignal

import database as db

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Multi-artist separators (order matters: longer patterns first)
_ARTIST_SEPARATORS = [
    ' feat. ', ' ft. ', ' Feat. ', ' Ft. ',
    ' featuring ', ' Featuring ',
    ' with ', ' With ',
    ' vs. ', ' vs ',
    ' & ', ' / ', '; ',
]

# Regex to detect iTunes-style trailing duplicate numbers ("Artist 1", "Artist 2")
_TRAILING_NUM_RE = re.compile(r'^(.+?)\s+(\d+)$')

# Regex to detect "Artist: Details" or "Artist_ Details" (iTunes escaping)
_ITUNES_COLON_RE = re.compile(r'^(.+?)[\s]*[:_][\s]+(.+)$')

# ---------------------------------------------------------------------------
# Composer aliases — at least 40 major classical composers
# Maps known abbreviations and variants to (canonical_full_name, sort_name)
# ---------------------------------------------------------------------------

# Helper to build bidirectional aliases
def _build_composer_map():
    """Build the composer alias dictionary.

    Returns dict mapping lowercased variant -> (canonical_name, sort_name).
    """
    # (canonical_full_name, sort_name, [aliases])
    composers = [
        # Baroque
        ("Johann Sebastian Bach", "Bach, Johann Sebastian", [
            "J.S. Bach", "J. S. Bach", "JS Bach", "J.S.Bach",
            "Jean-Sébastien Bach", "Jean Sébastien Bach",
            "Bach, J.S.", "Bach, Johann S.",
            "Bach",
        ]),
        ("Carl Philipp Emanuel Bach", "Bach, Carl Philipp Emanuel", [
            "C.P.E. Bach", "C. P. E. Bach", "CPE Bach",
            "Bach, C.P.E.",
        ]),
        ("Johann Christian Bach", "Bach, Johann Christian", [
            "J.C. Bach", "J. C. Bach", "JC Bach",
        ]),
        ("Georg Friedrich Händel", "Händel, Georg Friedrich", [
            "G.F. Handel", "G. F. Handel", "Handel", "Händel",
            "George Frideric Handel", "Georg Friedrich Handel",
            "Haendel",
        ]),
        ("Antonio Vivaldi", "Vivaldi, Antonio", [
            "A. Vivaldi", "Vivaldi",
        ]),
        ("Georg Philipp Telemann", "Telemann, Georg Philipp", [
            "G.P. Telemann", "Telemann",
        ]),
        ("Arcangelo Corelli", "Corelli, Arcangelo", [
            "A. Corelli", "Corelli",
        ]),
        ("Henry Purcell", "Purcell, Henry", [
            "H. Purcell", "Purcell",
        ]),
        ("Domenico Scarlatti", "Scarlatti, Domenico", [
            "D. Scarlatti", "Scarlatti",
        ]),
        ("Claudio Monteverdi", "Monteverdi, Claudio", [
            "C. Monteverdi", "Monteverdi",
        ]),
        # Classical era
        ("Wolfgang Amadeus Mozart", "Mozart, Wolfgang Amadeus", [
            "W.A. Mozart", "W. A. Mozart", "WA Mozart", "W.A.Mozart",
            "Mozart, W.A.", "Mozart, Wolfgang A.",
            "Mozart",
        ]),
        ("Ludwig van Beethoven", "Beethoven, Ludwig van", [
            "L.v. Beethoven", "L. v. Beethoven", "L.v.Beethoven",
            "L. van Beethoven", "Beethoven, L.v.",
            "Beethoven",
        ]),
        ("Joseph Haydn", "Haydn, Joseph", [
            "J. Haydn", "Franz Joseph Haydn", "F.J. Haydn",
            "Haydn",
        ]),
        ("Franz Schubert", "Schubert, Franz", [
            "F. Schubert", "Schubert",
        ]),
        # Romantic era
        ("Frédéric Chopin", "Chopin, Frédéric", [
            "F. Chopin", "Frederic Chopin", "Fryderyk Chopin",
            "Chopin",
        ]),
        ("Robert Schumann", "Schumann, Robert", [
            "R. Schumann", "Schumann",
        ]),
        ("Clara Schumann", "Schumann, Clara", [
            "C. Schumann", "Clara Wieck-Schumann",
        ]),
        ("Felix Mendelssohn", "Mendelssohn, Felix", [
            "F. Mendelssohn", "Mendelssohn-Bartholdy",
            "Felix Mendelssohn-Bartholdy", "Felix Mendelssohn Bartholdy",
            "Mendelssohn",
        ]),
        ("Franz Liszt", "Liszt, Franz", [
            "F. Liszt", "Liszt",
        ]),
        ("Johannes Brahms", "Brahms, Johannes", [
            "J. Brahms", "Brahms",
        ]),
        ("Pyotr Ilyich Tchaikovsky", "Tchaikovsky, Pyotr Ilyich", [
            "P.I. Tchaikovsky", "P. I. Tchaikovsky", "PI Tchaikovsky",
            "P.I. Tchaïkovski", "Tchaïkovski", "Tchaikovsky",
            "Tchaikowsky", "Tschaikowsky", "Tschaikowski",
            "Piotr Ilitch Tchaïkovski",
        ]),
        ("Antonín Dvořák", "Dvořák, Antonín", [
            "A. Dvorak", "Dvorak", "Dvořák", "Anton Dvorak",
            "Antonin Dvorak",
        ]),
        ("Edvard Grieg", "Grieg, Edvard", [
            "E. Grieg", "Grieg",
        ]),
        ("Hector Berlioz", "Berlioz, Hector", [
            "H. Berlioz", "Berlioz",
        ]),
        ("Camille Saint-Saëns", "Saint-Saëns, Camille", [
            "C. Saint-Saens", "Saint-Saens", "Saint-Saëns",
        ]),
        ("César Franck", "Franck, César", [
            "C. Franck", "Cesar Franck", "Franck",
        ]),
        ("Gabriel Fauré", "Fauré, Gabriel", [
            "G. Fauré", "G. Faure", "Gabriel Faure", "Fauré", "Faure",
        ]),
        ("Anton Bruckner", "Bruckner, Anton", [
            "A. Bruckner", "Bruckner",
        ]),
        ("Richard Wagner", "Wagner, Richard", [
            "R. Wagner", "Wagner",
        ]),
        ("Giuseppe Verdi", "Verdi, Giuseppe", [
            "G. Verdi", "Verdi",
        ]),
        ("Giacomo Puccini", "Puccini, Giacomo", [
            "G. Puccini", "Puccini",
        ]),
        ("Richard Strauss", "Strauss, Richard", [
            "R. Strauss",
        ]),
        ("Johann Strauss II", "Strauss II, Johann", [
            "J. Strauss II", "Johann Strauss Jr.", "Johann Strauss",
            "Strauss",
        ]),
        # Late Romantic / Modern
        ("Gustav Mahler", "Mahler, Gustav", [
            "G. Mahler", "Mahler",
        ]),
        ("Claude Debussy", "Debussy, Claude", [
            "C. Debussy", "Debussy",
        ]),
        ("Maurice Ravel", "Ravel, Maurice", [
            "M. Ravel", "Ravel",
        ]),
        ("Sergei Rachmaninoff", "Rachmaninoff, Sergei", [
            "S. Rachmaninoff", "Rachmaninov", "Rachmaninoff",
            "Sergei Rachmaninov", "Sergueï Rachmaninov",
            "S. Rachmaninov",
        ]),
        ("Igor Stravinsky", "Stravinsky, Igor", [
            "I. Stravinsky", "Stravinsky", "Strawinsky",
        ]),
        ("Sergei Prokofiev", "Prokofiev, Sergei", [
            "S. Prokofiev", "Prokofiev", "Prokofieff",
            "Sergei Prokofieff",
        ]),
        ("Dmitri Shostakovich", "Shostakovich, Dmitri", [
            "D. Shostakovich", "Shostakovich", "Schostakowitsch",
            "Chostakovitch",
        ]),
        ("Béla Bartók", "Bartók, Béla", [
            "B. Bartok", "Bartok", "Bartók", "Bela Bartok",
        ]),
        ("Jean Sibelius", "Sibelius, Jean", [
            "J. Sibelius", "Sibelius",
        ]),
        ("Erik Satie", "Satie, Erik", [
            "E. Satie", "Satie",
        ]),
        ("Nikolai Rimsky-Korsakov", "Rimsky-Korsakov, Nikolai", [
            "N. Rimsky-Korsakov", "Rimsky-Korsakov",
            "Rimski-Korsakov", "Korsakov",
        ]),
        ("Modest Mussorgsky", "Mussorgsky, Modest", [
            "M. Mussorgsky", "Mussorgsky", "Moussorgski",
            "Moussorgsky",
        ]),
        ("Alexander Borodin", "Borodin, Alexander", [
            "A. Borodin", "Borodin", "Borodine",
        ]),
        ("Sergei Taneyev", "Taneyev, Sergei", [
            "S. Taneyev", "Taneyev",
        ]),
        ("Edward Elgar", "Elgar, Edward", [
            "E. Elgar", "Elgar",
        ]),
        ("Ralph Vaughan Williams", "Vaughan Williams, Ralph", [
            "R. Vaughan Williams", "Vaughan Williams",
        ]),
        ("Benjamin Britten", "Britten, Benjamin", [
            "B. Britten", "Britten",
        ]),
        ("Leoš Janáček", "Janáček, Leoš", [
            "L. Janacek", "Janacek", "Janáček",
        ]),
        ("Olivier Messiaen", "Messiaen, Olivier", [
            "O. Messiaen", "Messiaen",
        ]),
        ("Arvo Pärt", "Pärt, Arvo", [
            "A. Part", "Part", "Pärt", "Arvo Part",
        ]),
        ("Philip Glass", "Glass, Philip", [
            "P. Glass", "Glass",
        ]),
        ("John Adams", "Adams, John", [
            "J. Adams",
        ]),
        # Film composers (important for Kevin's collection)
        ("Ennio Morricone", "Morricone, Ennio", [
            "E. Morricone", "Morricone",
        ]),
        ("Hans Zimmer", "Zimmer, Hans", [
            "H. Zimmer", "Zimmer",
        ]),
        ("John Williams", "Williams, John", [
            "J. Williams",
        ]),
        ("Howard Shore", "Shore, Howard", [
            "H. Shore", "Shore",
        ]),
        ("James Horner", "Horner, James", [
            "J. Horner", "Horner",
        ]),
        ("Danny Elfman", "Elfman, Danny", [
            "D. Elfman", "Elfman",
        ]),
        ("Alexandre Desplat", "Desplat, Alexandre", [
            "A. Desplat", "Desplat",
        ]),
        ("Joe Hisaishi", "Hisaishi, Joe", [
            "J. Hisaishi", "Hisaishi", "久石譲",
        ]),
    ]

    alias_map = {}
    for canonical, sort_name, aliases in composers:
        entry = (canonical, sort_name)
        alias_map[canonical.lower()] = entry
        alias_map[sort_name.lower()] = entry
        for alias in aliases:
            alias_map[alias.lower()] = entry

    return alias_map


COMPOSER_ALIASES = _build_composer_map()

# ---------------------------------------------------------------------------
# Genre normalization map
# ---------------------------------------------------------------------------

# Maps lowercased genre -> canonical genre name
_GENRE_MAP = {
    # Classical
    'classique': 'Classical',
    'classical': 'Classical',
    'classic': 'Classical',
    'klasik': 'Classical',
    'klassik': 'Classical',
    'musique classique': 'Classical',
    'classical music': 'Classical',
    'contemporary classical': 'Contemporary Classical',
    'classical crossover': 'Classical Crossover',
    'modern classical': 'Contemporary Classical',
    'baroque': 'Baroque',
    'opera': 'Opera',
    'opéra': 'Opera',
    'choral': 'Choral',
    'chamber music': 'Chamber Music',
    'musique de chambre': 'Chamber Music',
    'orchestral': 'Orchestral',
    'symphonique': 'Orchestral',
    'symphonic': 'Orchestral',
    'concerto': 'Classical',
    'piano': 'Classical',
    'organ': 'Classical',

    # Soundtracks
    'bande originale': 'Soundtrack',
    'bande originale de film': 'Soundtrack',
    'bande-originale': 'Soundtrack',
    'b.o.f.': 'Soundtrack',
    'bof': 'Soundtrack',
    'soundtrack': 'Soundtrack',
    'film soundtrack': 'Soundtrack',
    'movie soundtrack': 'Soundtrack',
    'ost': 'Soundtrack',
    'original soundtrack': 'Soundtrack',
    'original motion picture soundtrack': 'Soundtrack',
    'score': 'Soundtrack',
    'film score': 'Soundtrack',
    'musique de film': 'Soundtrack',
    'tv soundtrack': 'TV Soundtrack',
    'television soundtrack': 'TV Soundtrack',
    'game soundtrack': 'Game Soundtrack',
    'video game soundtrack': 'Game Soundtrack',

    # Rock
    'rock': 'Rock',
    'rock & roll': 'Rock & Roll',
    "rock 'n' roll": 'Rock & Roll',
    'rock and roll': 'Rock & Roll',
    'rock n roll': 'Rock & Roll',
    'alternative rock': 'Alternative Rock',
    'alt-rock': 'Alternative Rock',
    'alt rock': 'Alternative Rock',
    'rock alternatif': 'Alternative Rock',
    'indie rock': 'Indie Rock',
    'progressive rock': 'Progressive Rock',
    'prog rock': 'Progressive Rock',
    'prog-rock': 'Progressive Rock',
    'hard rock': 'Hard Rock',
    'classic rock': 'Classic Rock',
    'punk rock': 'Punk Rock',
    'punk': 'Punk Rock',
    'post-rock': 'Post-Rock',
    'post rock': 'Post-Rock',
    'psychedelic rock': 'Psychedelic Rock',
    'grunge': 'Grunge',
    'garage rock': 'Garage Rock',
    'soft rock': 'Soft Rock',
    'blues rock': 'Blues Rock',
    'folk rock': 'Folk Rock',
    'southern rock': 'Southern Rock',
    'stoner rock': 'Stoner Rock',
    'space rock': 'Space Rock',

    # Pop
    'pop': 'Pop',
    'pop/rock': 'Pop/Rock',
    'pop rock': 'Pop/Rock',
    'synthpop': 'Synthpop',
    'synth-pop': 'Synthpop',
    'synth pop': 'Synthpop',
    'electropop': 'Electropop',
    'indie pop': 'Indie Pop',
    'dream pop': 'Dream Pop',
    'britpop': 'Britpop',
    'k-pop': 'K-Pop',
    'j-pop': 'J-Pop',
    'teen pop': 'Teen Pop',
    'power pop': 'Power Pop',

    # Metal
    'metal': 'Metal',
    'heavy metal': 'Heavy Metal',
    'death metal': 'Death Metal',
    'black metal': 'Black Metal',
    'thrash metal': 'Thrash Metal',
    'doom metal': 'Doom Metal',
    'power metal': 'Power Metal',
    'symphonic metal': 'Symphonic Metal',
    'progressive metal': 'Progressive Metal',
    'prog metal': 'Progressive Metal',
    'folk metal': 'Folk Metal',
    'nu-metal': 'Nu-Metal',
    'nu metal': 'Nu-Metal',
    'metalcore': 'Metalcore',

    # Electronic
    'electronic': 'Electronic',
    'électronique': 'Electronic',
    'electronique': 'Electronic',
    'electro': 'Electronic',
    'electronica': 'Electronic',
    'edm': 'Electronic',
    'ambient': 'Ambient',
    'ambient electronic': 'Ambient',
    'downtempo': 'Downtempo',
    'chillout': 'Chillout',
    'chill-out': 'Chillout',
    'chill out': 'Chillout',
    'lounge': 'Lounge',
    'house': 'House',
    'deep house': 'Deep House',
    'tech house': 'Tech House',
    'techno': 'Techno',
    'trance': 'Trance',
    'drum and bass': 'Drum and Bass',
    'drum & bass': 'Drum and Bass',
    'dnb': 'Drum and Bass',
    "d'n'b": 'Drum and Bass',
    'dubstep': 'Dubstep',
    'trip-hop': 'Trip-Hop',
    'trip hop': 'Trip-Hop',
    'idm': 'IDM',
    'industrial': 'Industrial',
    'new wave': 'New Wave',
    'synthwave': 'Synthwave',
    'retrowave': 'Synthwave',

    # Jazz
    'jazz': 'Jazz',
    'smooth jazz': 'Smooth Jazz',
    'vocal jazz': 'Vocal Jazz',
    'bebop': 'Bebop',
    'swing': 'Swing',
    'big band': 'Big Band',
    'free jazz': 'Free Jazz',
    'fusion': 'Fusion',
    'jazz fusion': 'Fusion',
    'acid jazz': 'Acid Jazz',
    'cool jazz': 'Cool Jazz',
    'latin jazz': 'Latin Jazz',
    'jazz manouche': 'Gypsy Jazz',
    'gypsy jazz': 'Gypsy Jazz',

    # Blues
    'blues': 'Blues',
    'delta blues': 'Delta Blues',
    'chicago blues': 'Chicago Blues',
    'electric blues': 'Electric Blues',
    'country blues': 'Country Blues',

    # Folk / World
    'folk': 'Folk',
    'folk music': 'Folk',
    'world': 'World',
    'world music': 'World',
    'musique du monde': 'World',
    'celtic': 'Celtic',
    'celtique': 'Celtic',
    'musique celtique': 'Celtic',
    'flamenco': 'Flamenco',
    'latin': 'Latin',
    'bossa nova': 'Bossa Nova',
    'reggae': 'Reggae',
    'ska': 'Ska',
    'afrobeat': 'Afrobeat',
    'afro-beat': 'Afrobeat',

    # French
    'chanson': 'Chanson',
    'chanson française': 'Chanson Française',
    'chanson francaise': 'Chanson Française',
    'french chanson': 'Chanson Française',
    'variété française': 'Variété Française',
    'variete francaise': 'Variété Française',
    'variété': 'Variété Française',
    'french pop': 'French Pop',

    # R&B / Soul / Funk
    'r&b': 'R&B',
    'rnb': 'R&B',
    'rhythm and blues': 'R&B',
    'soul': 'Soul',
    'neo-soul': 'Neo-Soul',
    'neo soul': 'Neo-Soul',
    'funk': 'Funk',
    'disco': 'Disco',
    'motown': 'Motown',
    'gospel': 'Gospel',

    # Hip-Hop
    'hip-hop': 'Hip-Hop',
    'hip hop': 'Hip-Hop',
    'hiphop': 'Hip-Hop',
    'rap': 'Hip-Hop/Rap',
    'hip-hop/rap': 'Hip-Hop/Rap',
    'trap': 'Trap',
    'conscious rap': 'Conscious Rap',

    # Country
    'country': 'Country',
    'country music': 'Country',
    'country & western': 'Country',
    'alt-country': 'Alt-Country',
    'americana': 'Americana',
    'bluegrass': 'Bluegrass',

    # Other
    'new age': 'New Age',
    'meditation': 'New Age',
    'relaxation': 'New Age',
    'easy listening': 'Easy Listening',
    'spoken word': 'Spoken Word',
    'comedy': 'Comedy',
    'humour': 'Comedy',
    'humor': 'Comedy',
    'children': "Children's",
    'enfants': "Children's",
    "children's": "Children's",
    "children's music": "Children's",
    'holiday': 'Holiday',
    'christmas': 'Christmas',
    'noël': 'Christmas',
    'noel': 'Christmas',
    'religious': 'Religious',
    'spiritual': 'Spiritual',
    'audiobook': 'Audiobook',
    'livre audio': 'Audiobook',
    'podcast': 'Podcast',
    'experimental': 'Experimental',
    'avant-garde': 'Avant-Garde',
    'noise': 'Noise',
    'minimal': 'Minimal',
    'minimalism': 'Minimal',
    'minimalisme': 'Minimal',
}

# ---------------------------------------------------------------------------
# Album title cleanup patterns
# ---------------------------------------------------------------------------

# Encoding info patterns to remove (case-insensitive)
_ALBUM_ENCODING_PATTERNS = [
    # Bracketed encoding tags
    r'\s*\[FLAC\]',
    r'\s*\[MP3\]',
    r'\s*\[AAC\]',
    r'\s*\[ALAC\]',
    r'\s*\[DSD\]',
    r'\s*\[WAV\]',
    r'\s*\[WMA\]',
    r'\s*\[OGG\]',
    r'\s*\[SACD\]',
    # Bit depth / sample rate in brackets
    r'\s*\[\d+[\s-]*bits?\]',
    r'\s*\[\d+\.?\d*\s*kHz\]',
    r'\s*\[\d+[\s-]*\d+\]',       # [24-88], [16-44]
    r'\s*\[\d+bit[\s/-]*\d+\.?\d*kHz\]',
    # Parenthesized encoding tags
    r'\s*\(FLAC\)',
    r'\s*\(MP3\)',
    r'\s*\(DSD\d*\)',
    # Common web-rip tags
    r'\s*WEB[\s._-]*FLAC',
    r'\s*WEB[\s._-]*MP3',
    r'\s*WEB[\s._-]*AAC',
    r'\s*WEB[\s._-]*DL',
    # Bitrate tags
    r'\s*[àa@]\s*\d+\s*kbps',
    r'\s*\d+\s*kbps',
    r'\s*\(\d+kbps\)',
    # Specific known noise strings
    r'\s*EICHBAUM',
    # Remaster / edition tags (keep but normalize later)
    r'\s*\((?:[Rr]e-?master(?:ed|isé|isée)?)\)',
    r'\s*\((?:[Rr]emasterisé(?:e)?)\)',
    r'\s*\[(?:[Rr]e-?master(?:ed|isé|isée)?)\]',
    # Label/year edition tags
    r'\s*\([A-Z]{2,5}\s+\d{4}\)',  # (DG 2009), (EMI 1992)
    # Generic bracketed year-only tags (but not part of title)
    r'\s*\[\d{4}\]$',
]

# Compiled album encoding patterns
_ALBUM_ENCODING_RE = [re.compile(p, re.IGNORECASE) for p in _ALBUM_ENCODING_PATTERNS]

# Disc/CD normalization pattern
_DISC_PATTERN = re.compile(
    r'\s*[-–—]\s*'
    r'(?:CD|Disc|Disk|Vol\.?|Volume)\s*'
    r'(\d+)',
    re.IGNORECASE
)

# Leading catalog numbers: "123 - Title" or "ABC-123 Title"
_CATALOG_PREFIX_RE = re.compile(r'^\s*[A-Z]{0,5}\s*[-–]?\s*\d{3,}\s*[-–—:]\s*')

# Trailing catalog numbers: "Title [ABC 12345]"
_CATALOG_SUFFIX_RE = re.compile(r'\s*\[[A-Z]{1,5}\s*\d{3,}\]$')


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _strip_diacritics(text):
    """Remove diacritics for comparison purposes only."""
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _sanitize_input(text):
    """Validate and sanitize text input.

    Returns stripped string or empty string if input is invalid.
    """
    if text is None:
        return ''
    if not isinstance(text, str):
        try:
            text = str(text)
        except (ValueError, TypeError):
            return ''
    # Remove null bytes and control characters (except newlines/tabs)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text.strip()


def _normalize_whitespace(text):
    """Collapse multiple spaces, strip leading/trailing whitespace."""
    return re.sub(r'\s+', ' ', text).strip()


def _title_case_name(name):
    """Apply title case suitable for artist/composer names.

    Handles particles like 'van', 'von', 'de', 'di', 'du', 'le', 'la' that
    should stay lowercase mid-name but uppercase at start.
    Preserves names containing '/' without spaces (e.g. "AC/DC").
    """
    particles = {'van', 'von', 'de', 'di', 'du', 'le', 'la', 'les',
                 'el', 'al', 'the', 'of', 'und', 'et', 'y'}

    words = name.split()
    if not words:
        return name

    result = []
    for i, word in enumerate(words):
        lower = word.lower()

        # Preserve words with "/" that are not space-delimited (AC/DC, N/A)
        if '/' in word and not word.startswith('/') and not word.endswith('/'):
            # Keep original casing for slash-compound words
            result.append(word)
            continue

        if i == 0:
            # First word always capitalized
            result.append(word.capitalize())
        elif lower in particles:
            result.append(lower)
        elif word.isupper() and len(word) > 3:
            # ALL CAPS longer than 3 chars -> Title Case
            result.append(word.capitalize())
        elif '-' in word:
            # Hyphenated names: each part capitalized
            result.append('-'.join(
                part.capitalize() if part.lower() not in particles else part.lower()
                for part in word.split('-')
            ))
        else:
            # Keep original casing if it already has mixed case
            if word == word.lower() or word == word.upper():
                result.append(word.capitalize())
            else:
                result.append(word)

    return ' '.join(result)


# ---------------------------------------------------------------------------
# Public normalization functions
# ---------------------------------------------------------------------------

def normalize_artist(name):
    """Normalize an artist name.

    - Strips whitespace, fixes case
    - Handles "The X" vs "X, The" (flags as same, keeps canonical form)
    - Handles multi-artist separators
    - Handles iTunes escaping ("Artist_ Details", "Artist: Details")
    - Returns dict with normalization details:
      {
          'original': str,
          'normalized': str,
          'individual_artists': [str],
          'the_variant': str or None,  # alternate "The" form if applicable
          'changed': bool,
      }
    """
    name = _sanitize_input(name)
    if not name:
        return {
            'original': '',
            'normalized': '',
            'individual_artists': [],
            'the_variant': None,
            'changed': False,
        }

    original = name

    # Fix iTunes colon/underscore escaping: "Artist_ Details" -> "Artist: Details"
    # But only if it looks like metadata noise, not a real name
    match = _ITUNES_COLON_RE.match(name)
    if match:
        # Keep the full string but fix underscore -> colon
        name = name.replace('_ ', ': ')

    # Normalize whitespace
    name = _normalize_whitespace(name)

    # Split multi-artist entries
    individual_artists = _split_artists(name)

    # Normalize each individual artist
    normalized_individuals = []
    for artist in individual_artists:
        artist = _normalize_whitespace(artist)
        artist = _title_case_name(artist)
        normalized_individuals.append(artist)

    # Reconstruct the name
    if len(normalized_individuals) == 1:
        normalized = normalized_individuals[0]
    else:
        # Use "; " as the canonical multi-artist separator
        normalized = '; '.join(normalized_individuals)

    # Handle "The" prefix — canonical form is "The X", variant is "X, The"
    the_variant = None
    the_match = re.match(r'^The\s+(.+)$', normalized, re.IGNORECASE)
    if the_match:
        rest = the_match.group(1)
        the_variant = f"{rest}, The"
        # Ensure canonical form has capitalized "The"
        if not normalized.startswith('The '):
            normalized = f"The {rest}"
    else:
        the_match = re.match(r'^(.+?),\s*[Tt]he$', normalized)
        if the_match:
            rest = the_match.group(1)
            the_variant = f"{rest}, The"
            normalized = f"The {rest}"

    changed = normalized != original

    return {
        'original': original,
        'normalized': normalized,
        'individual_artists': normalized_individuals,
        'the_variant': the_variant,
        'changed': changed,
    }


def _split_artists(name):
    """Split a multi-artist string into individual artist names.

    Handles separators like "; ", " / ", " & ", " feat. " etc.
    Does NOT split on "/" without surrounding spaces (e.g. "AC/DC" stays intact).
    """
    # Try each separator
    for sep in _ARTIST_SEPARATORS:
        if sep.lower() in name.lower():
            # Case-insensitive split
            pattern = re.escape(sep)
            parts = re.split(pattern, name, flags=re.IGNORECASE)
            # Filter empty parts
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) > 1:
                return parts
    return [name]


def normalize_composer(name):
    """Normalize a composer name for classical music.

    Uses a dictionary of known classical composer aliases.
    Output format: "Last, First" for sort consistency.

    Returns dict:
      {
          'original': str,
          'canonical': str,
          'sort_name': str,
          'changed': bool,
          'is_known': bool,
      }
    """
    name = _sanitize_input(name)
    if not name:
        return {
            'original': '',
            'canonical': '',
            'sort_name': '',
            'changed': False,
            'is_known': False,
        }

    original = name
    name = _normalize_whitespace(name)

    # Handle multiple composers separated by ; or /
    if ';' in name or '/' in name:
        composers = re.split(r'\s*[;/]\s*', name)
        results = [normalize_composer(c) for c in composers if c.strip()]
        if results:
            canonicals = [r['canonical'] for r in results]
            sort_names = [r['sort_name'] for r in results]
            combined = '; '.join(canonicals)
            combined_sort = '; '.join(sort_names)
            return {
                'original': original,
                'canonical': combined,
                'sort_name': combined_sort,
                'changed': combined != original,
                'is_known': any(r['is_known'] for r in results),
            }

    # Look up in aliases (case-insensitive)
    lookup_key = name.lower().strip()

    # Also try without trailing period
    lookup_variants = [
        lookup_key,
        lookup_key.rstrip('.'),
        _strip_diacritics(lookup_key),
    ]

    for variant in lookup_variants:
        if variant in COMPOSER_ALIASES:
            canonical, sort_name = COMPOSER_ALIASES[variant]
            return {
                'original': original,
                'canonical': canonical,
                'sort_name': sort_name,
                'changed': canonical != original,
                'is_known': True,
            }

    # Not a known composer — apply basic normalization
    name = _title_case_name(name)

    # Generate sort name for unknown composers
    sort_name = name
    parts = name.split()
    if len(parts) >= 2:
        # "First Last" -> "Last, First"
        # But handle particles (van, von, de, etc.)
        particles = {'van', 'von', 'de', 'di', 'du', 'le', 'la', 'el', 'al'}
        last_start = len(parts) - 1
        while last_start > 0 and parts[last_start - 1].lower() in particles:
            last_start -= 1
        if last_start > 0:
            last_part = ' '.join(parts[last_start:])
            first_part = ' '.join(parts[:last_start])
            sort_name = f"{last_part}, {first_part}"

    return {
        'original': original,
        'canonical': name,
        'sort_name': sort_name,
        'changed': name != original,
        'is_known': False,
    }


def normalize_album_title(title):
    """Clean up album title.

    - Removes encoding info: [FLAC], [16bits], WEB FLAC, etc.
    - Normalizes disc/volume indicators format
    - Removes catalog number prefixes/suffixes
    - Trims whitespace and trailing punctuation noise

    Returns dict:
      {
          'original': str,
          'normalized': str,
          'disc_info': str or None,  # extracted disc info e.g. "CD 1"
          'changed': bool,
      }
    """
    title = _sanitize_input(title)
    if not title:
        return {
            'original': '',
            'normalized': '',
            'disc_info': None,
            'changed': False,
        }

    original = title
    title = _normalize_whitespace(title)

    # Remove encoding info patterns
    for pattern in _ALBUM_ENCODING_RE:
        title = pattern.sub('', title)

    # Extract disc info before removing it
    disc_info = None
    disc_match = _DISC_PATTERN.search(title)
    if disc_match:
        disc_num = disc_match.group(1)
        disc_info = f"CD {disc_num}"
        # Remove the disc pattern from title
        title = _DISC_PATTERN.sub('', title)

    # Remove catalog number prefixes
    title = _CATALOG_PREFIX_RE.sub('', title)

    # Remove catalog number suffixes
    title = _CATALOG_SUFFIX_RE.sub('', title)

    # Clean up separator artifacts after removals
    # " - " at the end, or ":" at the end
    title = re.sub(r'\s*[-–—:]\s*$', '', title)
    title = re.sub(r'^\s*[-–—:]\s*', '', title)

    # Collapse multiple spaces
    title = _normalize_whitespace(title)

    # Remove trailing/leading parentheses that are now empty
    title = re.sub(r'\(\s*\)', '', title)
    title = re.sub(r'\[\s*\]', '', title)
    title = title.strip()

    changed = title != original

    return {
        'original': original,
        'normalized': title,
        'disc_info': disc_info,
        'changed': changed,
    }


def normalize_genre(genre):
    """Normalize genre names.

    - Merges French/English variants
    - Merges common misspellings and abbreviations
    - Handles empty/whitespace-only genres

    Returns dict:
      {
          'original': str,
          'normalized': str,
          'changed': bool,
      }
    """
    genre = _sanitize_input(genre)
    if not genre:
        return {
            'original': '',
            'normalized': '',
            'changed': False,
        }

    original = genre
    genre = _normalize_whitespace(genre)

    # Handle compound genres separated by "/"
    # Only split on "/" if it's NOT part of a known compound genre
    lookup = genre.lower().strip()

    # Direct lookup
    if lookup in _GENRE_MAP:
        normalized = _GENRE_MAP[lookup]
        return {
            'original': original,
            'normalized': normalized,
            'changed': normalized != original,
        }

    # Try without diacritics
    lookup_ascii = _strip_diacritics(lookup)
    if lookup_ascii in _GENRE_MAP:
        normalized = _GENRE_MAP[lookup_ascii]
        return {
            'original': original,
            'normalized': normalized,
            'changed': normalized != original,
        }

    # Handle compound genres: "Rock/Pop" -> keep as-is but normalize parts
    if '/' in genre and genre.lower() not in _GENRE_MAP:
        parts = [p.strip() for p in genre.split('/') if p.strip()]
        normalized_parts = []
        for part in parts:
            part_lower = part.lower()
            if part_lower in _GENRE_MAP:
                normalized_parts.append(_GENRE_MAP[part_lower])
            else:
                # Title case unknown genre
                normalized_parts.append(part.strip().title())
        normalized = '/'.join(normalized_parts)
        return {
            'original': original,
            'normalized': normalized,
            'changed': normalized != original,
        }

    # Unknown genre — just apply title case
    normalized = genre.strip().title()
    return {
        'original': original,
        'normalized': normalized,
        'changed': normalized != original,
    }


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def find_duplicate_artists(threshold=0.85):
    """Find potential duplicate artists using fuzzy matching.

    Returns list of groups:
      [{
          'canonical': str,      # suggested canonical name
          'variants': [str],     # similar names found
          'artist_ids': [int],   # corresponding database IDs
          'similarity': float,   # average similarity score
      }]
    """
    rows = db.fetchall("SELECT id, name FROM artists ORDER BY name")
    if not rows:
        return []

    artists = [(row['id'], row['name']) for row in rows]
    n = len(artists)

    # Pre-compute normalized names for faster comparison
    normalized = []
    for aid, name in artists:
        norm = _normalize_whitespace(name).lower()
        norm = _strip_diacritics(norm)
        # Remove "The " prefix for comparison
        if norm.startswith('the '):
            norm = norm[4:]
        normalized.append((aid, name, norm))

    # Find groups of similar artists
    used = set()
    groups = []

    for i in range(n):
        if i in used:
            continue

        aid_i, name_i, norm_i = normalized[i]
        if not norm_i:
            continue

        group_ids = [aid_i]
        group_names = [name_i]
        group_sims = []

        for j in range(i + 1, n):
            if j in used:
                continue

            aid_j, name_j, norm_j = normalized[j]
            if not norm_j:
                continue

            # Quick length check to avoid expensive comparison
            len_ratio = min(len(norm_i), len(norm_j)) / max(len(norm_i), len(norm_j))
            if len_ratio < 0.5:
                continue

            sim = SequenceMatcher(None, norm_i, norm_j).ratio()
            if sim >= threshold:
                group_ids.append(aid_j)
                group_names.append(name_j)
                group_sims.append(sim)
                used.add(j)

        if len(group_ids) > 1:
            used.add(i)
            # Pick canonical name: longest or most common
            canonical = max(group_names, key=len)
            avg_sim = sum(group_sims) / len(group_sims) if group_sims else 1.0
            groups.append({
                'canonical': canonical,
                'variants': group_names,
                'artist_ids': group_ids,
                'similarity': round(avg_sim, 3),
            })

    return groups


def find_duplicate_albums(threshold=0.85):
    """Find potential duplicate albums (same artist, similar title).

    Returns list of duplicates:
      [{
          'artist_id': int,
          'artist_name': str,
          'canonical_title': str,
          'variants': [{'id': int, 'title': str, 'year': int}],
          'similarity': float,
      }]
    """
    rows = db.fetchall("""
        SELECT al.id, al.title, al.year, al.artist_id, a.name as artist_name
        FROM albums al
        LEFT JOIN artists a ON al.artist_id = a.id
        ORDER BY al.artist_id, al.title
    """)
    if not rows:
        return []

    # Group albums by artist
    by_artist = {}
    for row in rows:
        aid = row['artist_id']
        if aid not in by_artist:
            by_artist[aid] = []
        by_artist[aid].append({
            'id': row['id'],
            'title': row['title'],
            'year': row['year'],
            'artist_name': row['artist_name'],
        })

    duplicates = []

    for artist_id, albums in by_artist.items():
        n = len(albums)
        if n < 2:
            continue

        # Pre-normalize titles for comparison
        normalized = []
        for alb in albums:
            norm_result = normalize_album_title(alb['title'])
            norm = norm_result['normalized'].lower()
            norm = _strip_diacritics(norm)
            normalized.append(norm)

        used = set()
        for i in range(n):
            if i in used:
                continue

            group = [albums[i]]
            group_sims = []

            for j in range(i + 1, n):
                if j in used:
                    continue

                # Quick length check
                len_i, len_j = len(normalized[i]), len(normalized[j])
                if len_i == 0 or len_j == 0:
                    continue
                len_ratio = min(len_i, len_j) / max(len_i, len_j)
                if len_ratio < 0.5:
                    continue

                sim = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
                if sim >= threshold:
                    group.append(albums[j])
                    group_sims.append(sim)
                    used.add(j)

            if len(group) > 1:
                used.add(i)
                canonical_title = max(
                    [a['title'] for a in group],
                    key=len
                )
                avg_sim = sum(group_sims) / len(group_sims) if group_sims else 1.0
                duplicates.append({
                    'artist_id': artist_id,
                    'artist_name': albums[i]['artist_name'] or 'Unknown',
                    'canonical_title': canonical_title,
                    'variants': [
                        {'id': a['id'], 'title': a['title'], 'year': a['year']}
                        for a in group
                    ],
                    'similarity': round(avg_sim, 3),
                })

    return duplicates


# ---------------------------------------------------------------------------
# Merge operations (database mutations)
# ---------------------------------------------------------------------------

def merge_artists(keep_id, merge_ids):
    """Merge duplicate artists into one.

    Updates all tracks and albums referencing merge_ids to point to keep_id,
    then deletes the merged artist records.

    Args:
        keep_id: Artist ID to keep as canonical.
        merge_ids: List of artist IDs to merge into keep_id.

    Returns:
        int: Number of tracks updated.
    """
    if not merge_ids:
        return 0
    if not isinstance(merge_ids, (list, tuple)):
        merge_ids = [merge_ids]

    # Validate IDs are integers
    keep_id = int(keep_id)
    merge_ids = [int(mid) for mid in merge_ids]

    # Don't merge an artist into itself
    merge_ids = [mid for mid in merge_ids if mid != keep_id]
    if not merge_ids:
        return 0

    # Verify keep_id exists
    keep_row = db.fetchone("SELECT id, name FROM artists WHERE id = ?", (keep_id,))
    if not keep_row:
        raise ValueError(f"Artist ID {keep_id} not found")

    total_updated = 0

    for merge_id in merge_ids:
        # Update tracks: artist_id
        cursor = db.execute(
            "UPDATE tracks SET artist_id = ? WHERE artist_id = ?",
            (keep_id, merge_id), commit=False
        )
        total_updated += cursor.rowcount

        # Update tracks: album_artist_id
        db.execute(
            "UPDATE tracks SET album_artist_id = ? WHERE album_artist_id = ?",
            (keep_id, merge_id), commit=False
        )

        # Update albums: artist_id
        db.execute(
            "UPDATE albums SET artist_id = ? WHERE artist_id = ?",
            (keep_id, merge_id), commit=False
        )

        # Delete the merged artist
        db.execute(
            "DELETE FROM artists WHERE id = ?",
            (merge_id,), commit=False
        )

    db.commit()
    log.info(
        "Merged artists %s into %d (%s): %d tracks updated",
        merge_ids, keep_id, keep_row['name'], total_updated
    )
    return total_updated


def merge_albums(keep_id, merge_ids):
    """Merge duplicate albums into one.

    Moves all tracks to keep_id, preserves best metadata (non-null values),
    then deletes merged album records.

    Args:
        keep_id: Album ID to keep as canonical.
        merge_ids: List of album IDs to merge into keep_id.

    Returns:
        int: Number of tracks moved.
    """
    if not merge_ids:
        return 0
    if not isinstance(merge_ids, (list, tuple)):
        merge_ids = [merge_ids]

    keep_id = int(keep_id)
    merge_ids = [int(mid) for mid in merge_ids]
    merge_ids = [mid for mid in merge_ids if mid != keep_id]
    if not merge_ids:
        return 0

    # Verify keep_id exists
    keep_row = db.fetchone("SELECT * FROM albums WHERE id = ?", (keep_id,))
    if not keep_row:
        raise ValueError(f"Album ID {keep_id} not found")

    total_moved = 0

    for merge_id in merge_ids:
        merge_row = db.fetchone("SELECT * FROM albums WHERE id = ?", (merge_id,))
        if not merge_row:
            continue

        # Move all tracks to the canonical album
        cursor = db.execute(
            "UPDATE tracks SET album_id = ? WHERE album_id = ?",
            (keep_id, merge_id), commit=False
        )
        total_moved += cursor.rowcount

        # Update keep album with best metadata from merged album
        # Prefer non-null values
        updates = []
        params = []

        if not keep_row['year'] and merge_row['year']:
            updates.append("year = ?")
            params.append(merge_row['year'])
        if not keep_row['genre'] and merge_row['genre']:
            updates.append("genre = ?")
            params.append(merge_row['genre'])
        if not keep_row['cover_data'] and merge_row['cover_data']:
            updates.append("cover_data = ?")
            params.append(merge_row['cover_data'])
        if not keep_row['cover_path'] and merge_row['cover_path']:
            updates.append("cover_path = ?")
            params.append(merge_row['cover_path'])
        if not keep_row['musicbrainz_id'] and merge_row['musicbrainz_id']:
            updates.append("musicbrainz_id = ?")
            params.append(merge_row['musicbrainz_id'])
        if not keep_row['folder_path'] and merge_row['folder_path']:
            updates.append("folder_path = ?")
            params.append(merge_row['folder_path'])

        # Update total_tracks to max
        max_tracks = max(
            keep_row['total_tracks'] or 0,
            merge_row['total_tracks'] or 0
        )
        updates.append("total_tracks = ?")
        params.append(max_tracks)

        max_discs = max(
            keep_row['total_discs'] or 1,
            merge_row['total_discs'] or 1
        )
        updates.append("total_discs = ?")
        params.append(max_discs)

        if updates:
            sql = f"UPDATE albums SET {', '.join(updates)} WHERE id = ?"
            params.append(keep_id)
            db.execute(sql, tuple(params), commit=False)

        # Delete the merged album
        db.execute(
            "DELETE FROM albums WHERE id = ?",
            (merge_id,), commit=False
        )

    db.commit()
    log.info(
        "Merged albums %s into %d: %d tracks moved",
        merge_ids, keep_id, total_moved
    )
    return total_moved


# ---------------------------------------------------------------------------
# Batch harmonization worker
# ---------------------------------------------------------------------------

class HarmonizeWorker(QObject):
    """Worker for batch metadata harmonization.

    Runs in a QThread. Two modes:
      - preview: scan and report proposed changes without modifying the database
      - apply: actually update the database

    Signals:
        progress(int current, int total, str description)
        preview(list changes)  — emitted in preview mode with list of proposed changes
        finished(dict stats)   — emitted on completion with statistics
        error(str msg)         — emitted on fatal error
    """

    progress = pyqtSignal(int, int, str)
    preview = pyqtSignal(list)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, mode='preview', normalize_artists=True,
                 normalize_composers=True, normalize_albums=True,
                 normalize_genres=True, detect_duplicates=True):
        """Initialize harmonization worker.

        Args:
            mode: 'preview' (report changes) or 'apply' (update database).
            normalize_artists: Whether to normalize artist names.
            normalize_composers: Whether to normalize composer names.
            normalize_albums: Whether to normalize album titles.
            normalize_genres: Whether to normalize genre names.
            detect_duplicates: Whether to detect duplicate artists/albums.
        """
        super().__init__()
        self._mode = mode
        self._normalize_artists = normalize_artists
        self._normalize_composers = normalize_composers
        self._normalize_albums = normalize_albums
        self._normalize_genres = normalize_genres
        self._detect_duplicates = detect_duplicates
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the harmonization."""
        self._cancelled = True

    def run(self):
        """Execute the harmonization process."""
        try:
            changes = []
            stats = {
                'artists_normalized': 0,
                'albums_cleaned': 0,
                'genres_merged': 0,
                'composers_fixed': 0,
                'duplicates_found': 0,
                'total_scanned': 0,
            }

            # Count total items to process for progress reporting
            total_items = 0
            if self._normalize_artists:
                count = db.fetchone("SELECT COUNT(*) as c FROM artists")
                total_items += count['c'] if count else 0
            if self._normalize_albums:
                count = db.fetchone("SELECT COUNT(*) as c FROM albums")
                total_items += count['c'] if count else 0
            if self._normalize_composers or self._normalize_genres:
                count = db.fetchone("SELECT COUNT(*) as c FROM tracks")
                total_items += count['c'] if count else 0

            current = 0

            # --- Phase 1: Artist normalization ---
            if self._normalize_artists and not self._cancelled:
                current = self._harmonize_artists(changes, stats, current, total_items)

            # --- Phase 2: Album title normalization ---
            if self._normalize_albums and not self._cancelled:
                current = self._harmonize_albums(changes, stats, current, total_items)

            # --- Phase 3: Track-level normalization (composer, genre) ---
            if (self._normalize_composers or self._normalize_genres) and not self._cancelled:
                current = self._harmonize_tracks(changes, stats, current, total_items)

            # --- Phase 4: Duplicate detection ---
            if self._detect_duplicates and not self._cancelled:
                self.progress.emit(current, total_items, "Detecting duplicates...")
                dup_artists = find_duplicate_artists()
                dup_albums = find_duplicate_albums()
                stats['duplicates_found'] = len(dup_artists) + len(dup_albums)

                for group in dup_artists:
                    changes.append({
                        'type': 'duplicate_artist',
                        'description': f"Duplicate artists: {', '.join(group['variants'])}",
                        'canonical': group['canonical'],
                        'ids': group['artist_ids'],
                        'similarity': group['similarity'],
                    })

                for dup in dup_albums:
                    variant_titles = [v['title'] for v in dup['variants']]
                    changes.append({
                        'type': 'duplicate_album',
                        'description': (
                            f"Duplicate albums by {dup['artist_name']}: "
                            f"{', '.join(variant_titles)}"
                        ),
                        'canonical': dup['canonical_title'],
                        'ids': [v['id'] for v in dup['variants']],
                        'similarity': dup['similarity'],
                    })

            stats['total_scanned'] = current

            # Emit results
            if self._mode == 'preview':
                self.preview.emit(changes)

            self.finished.emit(stats)

        except Exception as e:
            log.exception("Harmonization error")
            self.error.emit(str(e))
        finally:
            db.close_connection()

    def _harmonize_artists(self, changes, stats, current, total_items):
        """Normalize all artist names."""
        rows = db.fetchall("SELECT id, name, sort_name FROM artists")
        for row in rows:
            if self._cancelled:
                break

            current += 1
            if current % 50 == 0:
                self.progress.emit(current, total_items, f"Artist: {row['name']}")

            result = normalize_artist(row['name'])
            if result['changed']:
                stats['artists_normalized'] += 1

                change = {
                    'type': 'artist',
                    'id': row['id'],
                    'field': 'name',
                    'old_value': row['name'],
                    'new_value': result['normalized'],
                }
                changes.append(change)

                if self._mode == 'apply':
                    # Also update sort_name
                    sort_parts = result['normalized'].split()
                    sort_name = result['normalized']
                    if len(sort_parts) >= 2:
                        # Generate sort name: "Last, First"
                        particles = {'van', 'von', 'de', 'di', 'du', 'le', 'la'}
                        last_start = len(sort_parts) - 1
                        while last_start > 0 and sort_parts[last_start - 1].lower() in particles:
                            last_start -= 1
                        if last_start > 0:
                            sort_name = (
                                f"{' '.join(sort_parts[last_start:])}, "
                                f"{' '.join(sort_parts[:last_start])}"
                            )

                    db.execute(
                        "UPDATE artists SET name = ?, sort_name = ? WHERE id = ?",
                        (result['normalized'], sort_name, row['id']),
                        commit=False
                    )

            # Check for "The" variant — flag even if no normalization needed
            if result['the_variant']:
                # Check if both forms exist in the database
                the_match = db.fetchone(
                    "SELECT id FROM artists WHERE name = ?",
                    (result['the_variant'],)
                )
                if the_match and the_match['id'] != row['id']:
                    changes.append({
                        'type': 'duplicate_artist_the',
                        'description': (
                            f'"{row["name"]}" and "{result["the_variant"]}" '
                            f'are the same artist'
                        ),
                        'ids': [row['id'], the_match['id']],
                    })
                    stats['duplicates_found'] += 1

        if self._mode == 'apply' and stats['artists_normalized'] > 0:
            db.commit()

        return current

    def _harmonize_albums(self, changes, stats, current, total_items):
        """Normalize all album titles."""
        rows = db.fetchall("SELECT id, title FROM albums")
        for row in rows:
            if self._cancelled:
                break

            current += 1
            if current % 50 == 0:
                self.progress.emit(current, total_items, f"Album: {row['title']}")

            result = normalize_album_title(row['title'])
            if result['changed']:
                stats['albums_cleaned'] += 1

                changes.append({
                    'type': 'album',
                    'id': row['id'],
                    'field': 'title',
                    'old_value': row['title'],
                    'new_value': result['normalized'],
                    'disc_info': result['disc_info'],
                })

                if self._mode == 'apply':
                    db.execute(
                        "UPDATE albums SET title = ? WHERE id = ?",
                        (result['normalized'], row['id']),
                        commit=False
                    )

        if self._mode == 'apply' and stats['albums_cleaned'] > 0:
            db.commit()

        return current

    def _harmonize_tracks(self, changes, stats, current, total_items):
        """Normalize composer and genre on all tracks."""
        rows = db.fetchall("SELECT id, composer, genre FROM tracks")
        batch_count = 0

        for row in rows:
            if self._cancelled:
                break

            current += 1
            if current % 200 == 0:
                self.progress.emit(current, total_items, "Tracks: composer/genre...")

            track_id = row['id']

            # Composer normalization
            if self._normalize_composers and row['composer']:
                comp_result = normalize_composer(row['composer'])
                if comp_result['changed']:
                    stats['composers_fixed'] += 1

                    changes.append({
                        'type': 'track_composer',
                        'id': track_id,
                        'field': 'composer',
                        'old_value': row['composer'],
                        'new_value': comp_result['canonical'],
                        'is_known': comp_result['is_known'],
                    })

                    if self._mode == 'apply':
                        db.execute(
                            "UPDATE tracks SET composer = ? WHERE id = ?",
                            (comp_result['canonical'], track_id),
                            commit=False
                        )
                        batch_count += 1

            # Genre normalization
            if self._normalize_genres and row['genre']:
                genre_result = normalize_genre(row['genre'])
                if genre_result['changed']:
                    stats['genres_merged'] += 1

                    changes.append({
                        'type': 'track_genre',
                        'id': track_id,
                        'field': 'genre',
                        'old_value': row['genre'],
                        'new_value': genre_result['normalized'],
                    })

                    if self._mode == 'apply':
                        db.execute(
                            "UPDATE tracks SET genre = ? WHERE id = ?",
                            (genre_result['normalized'], track_id),
                            commit=False
                        )
                        batch_count += 1

            # Batch commit every 100 changes
            if self._mode == 'apply' and batch_count >= 100:
                db.commit()
                batch_count = 0

        if self._mode == 'apply' and batch_count > 0:
            db.commit()

        # Also update genre on albums table
        if self._normalize_genres and not self._cancelled:
            album_rows = db.fetchall(
                "SELECT id, genre FROM albums WHERE genre IS NOT NULL AND genre != ''"
            )
            batch_count = 0
            for row in album_rows:
                if self._cancelled:
                    break
                genre_result = normalize_genre(row['genre'])
                if genre_result['changed']:
                    if self._mode == 'apply':
                        db.execute(
                            "UPDATE albums SET genre = ? WHERE id = ?",
                            (genre_result['normalized'], row['id']),
                            commit=False
                        )
                        batch_count += 1
                        if batch_count >= 100:
                            db.commit()
                            batch_count = 0

            if self._mode == 'apply' and batch_count > 0:
                db.commit()

        return current
