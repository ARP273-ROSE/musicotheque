"""Classical music classifier — automatic period, form, catalogue, and movement detection.

Uses metadata (composer, title, genre) to classify tracks by musical period,
sub-period, musical movement/style, form/genre, catalogue number,
and instrumentation.

Covers 350+ composers across all periods (Medieval to Contemporary),
70+ musical forms, 15+ catalogue number systems, 35+ instruments,
and 20+ musical movements/styles (Impressionism, Expressionism,
Serialism, Minimalism, Nationalism, etc.).
"""
import re
import logging

log = logging.getLogger(__name__)

# --- Musical Periods ---

# Composer → (primary_period, birth_year, death_year)
# For composers spanning two periods, the primary classification is used
COMPOSER_PERIODS = {
    # Medieval (< 1400)
    'Hildegard von Bingen': ('Medieval', 1098, 1179),
    'Guillaume de Machaut': ('Medieval', 1300, 1377),
    'Pérotin': ('Medieval', 1160, 1230),
    'Léonin': ('Medieval', 1135, 1201),
    'Philippe de Vitry': ('Medieval', 1291, 1361),
    'Francesco Landini': ('Medieval', 1325, 1397),

    # Renaissance (1400-1600)
    'Guillaume Dufay': ('Renaissance', 1397, 1474),
    'Johannes Ockeghem': ('Renaissance', 1410, 1497),
    'Josquin des Prez': ('Renaissance', 1450, 1521),
    'Giovanni Pierluigi da Palestrina': ('Renaissance', 1525, 1594),
    'Palestrina': ('Renaissance', 1525, 1594),
    'Orlando di Lasso': ('Renaissance', 1532, 1594),
    'William Byrd': ('Renaissance', 1540, 1623),
    'Thomas Tallis': ('Renaissance', 1505, 1585),
    'Tomás Luis de Victoria': ('Renaissance', 1548, 1611),
    'Carlo Gesualdo': ('Renaissance', 1566, 1613),
    'John Dowland': ('Renaissance', 1563, 1626),
    'Giovanni Gabrieli': ('Renaissance', 1557, 1612),
    'Claudio Monteverdi': ('Renaissance', 1567, 1643),
    'Thomas Morley': ('Renaissance', 1557, 1602),
    'Adrian Willaert': ('Renaissance', 1490, 1562),
    'Clément Janequin': ('Renaissance', 1485, 1558),

    # Baroque (1600-1750)
    'Johann Sebastian Bach': ('Baroque', 1685, 1750),
    'J.S. Bach': ('Baroque', 1685, 1750),
    'Bach': ('Baroque', 1685, 1750),
    'George Frideric Handel': ('Baroque', 1685, 1759),
    'Handel': ('Baroque', 1685, 1759),
    'Georg Friedrich Händel': ('Baroque', 1685, 1759),
    'Antonio Vivaldi': ('Baroque', 1678, 1741),
    'Vivaldi': ('Baroque', 1678, 1741),
    'Henry Purcell': ('Baroque', 1659, 1695),
    'Arcangelo Corelli': ('Baroque', 1653, 1713),
    'Domenico Scarlatti': ('Baroque', 1685, 1757),
    'Jean-Philippe Rameau': ('Baroque', 1683, 1764),
    'François Couperin': ('Baroque', 1668, 1733),
    'Georg Philipp Telemann': ('Baroque', 1681, 1767),
    'Telemann': ('Baroque', 1681, 1767),
    'Jean-Baptiste Lully': ('Baroque', 1632, 1687),
    'Lully': ('Baroque', 1632, 1687),
    'Dietrich Buxtehude': ('Baroque', 1637, 1707),
    'Buxtehude': ('Baroque', 1637, 1707),
    'Alessandro Scarlatti': ('Baroque', 1660, 1725),
    'Tomaso Albinoni': ('Baroque', 1671, 1751),
    'Albinoni': ('Baroque', 1671, 1751),
    'Johann Pachelbel': ('Baroque', 1653, 1706),
    'Pachelbel': ('Baroque', 1653, 1706),
    'Marc-Antoine Charpentier': ('Baroque', 1643, 1704),
    'Marin Marais': ('Baroque', 1656, 1728),
    'Heinrich Schütz': ('Baroque', 1585, 1672),
    'Claudio Monteverdi': ('Baroque', 1567, 1643),
    'Barbara Strozzi': ('Baroque', 1619, 1677),
    'Antonio Soler': ('Baroque', 1729, 1783),
    'Carl Philipp Emanuel Bach': ('Baroque', 1714, 1788),
    'C.P.E. Bach': ('Baroque', 1714, 1788),
    'Wilhelm Friedemann Bach': ('Baroque', 1710, 1784),
    'W.F. Bach': ('Baroque', 1710, 1784),
    'Johann Christian Bach': ('Baroque', 1735, 1782),
    'J.C. Bach': ('Baroque', 1735, 1782),
    'Giuseppe Tartini': ('Baroque', 1692, 1770),
    'Pietro Locatelli': ('Baroque', 1695, 1764),
    'Jean-Marie Leclair': ('Baroque', 1697, 1764),
    'Johann Adolf Hasse': ('Baroque', 1699, 1783),

    # Classical (1750-1820)
    'Wolfgang Amadeus Mozart': ('Classical', 1756, 1791),
    'Mozart': ('Classical', 1756, 1791),
    'W.A. Mozart': ('Classical', 1756, 1791),
    'Joseph Haydn': ('Classical', 1732, 1809),
    'Haydn': ('Classical', 1732, 1809),
    'Ludwig van Beethoven': ('Classical', 1770, 1827),
    'Beethoven': ('Classical', 1770, 1827),
    'Christoph Willibald Gluck': ('Classical', 1714, 1787),
    'Gluck': ('Classical', 1714, 1787),
    'Luigi Boccherini': ('Classical', 1743, 1805),
    'Boccherini': ('Classical', 1743, 1805),
    'Antonio Salieri': ('Classical', 1750, 1825),
    'Muzio Clementi': ('Classical', 1752, 1832),
    'Clementi': ('Classical', 1752, 1832),
    'Johann Nepomuk Hummel': ('Classical', 1778, 1837),
    'Hummel': ('Classical', 1778, 1837),
    'Carl Maria von Weber': ('Classical', 1786, 1826),
    'Weber': ('Classical', 1786, 1826),
    'Domenico Cimarosa': ('Classical', 1749, 1801),
    'Giovanni Paisiello': ('Classical', 1740, 1816),
    'Carl Stamitz': ('Classical', 1745, 1801),
    'Johann Stamitz': ('Classical', 1717, 1757),
    'Michael Haydn': ('Classical', 1737, 1806),
    'Leopold Mozart': ('Classical', 1719, 1787),

    # Romantic (1820-1900)
    'Franz Schubert': ('Romantic', 1797, 1828),
    'Schubert': ('Romantic', 1797, 1828),
    'Robert Schumann': ('Romantic', 1810, 1856),
    'Schumann': ('Romantic', 1810, 1856),
    'Frédéric Chopin': ('Romantic', 1810, 1849),
    'Chopin': ('Romantic', 1810, 1849),
    'Franz Liszt': ('Romantic', 1811, 1886),
    'Liszt': ('Romantic', 1811, 1886),
    'Felix Mendelssohn': ('Romantic', 1809, 1847),
    'Mendelssohn': ('Romantic', 1809, 1847),
    'Hector Berlioz': ('Romantic', 1803, 1869),
    'Berlioz': ('Romantic', 1803, 1869),
    'Johannes Brahms': ('Romantic', 1833, 1897),
    'Brahms': ('Romantic', 1833, 1897),
    'Pyotr Ilyich Tchaikovsky': ('Romantic', 1840, 1893),
    'Tchaikovsky': ('Romantic', 1840, 1893),
    'Tchaïkovski': ('Romantic', 1840, 1893),
    'Antonín Dvořák': ('Romantic', 1841, 1904),
    'Dvorak': ('Romantic', 1841, 1904),
    'Dvořák': ('Romantic', 1841, 1904),
    'Giuseppe Verdi': ('Romantic', 1813, 1901),
    'Verdi': ('Romantic', 1813, 1901),
    'Richard Wagner': ('Romantic', 1813, 1883),
    'Wagner': ('Romantic', 1813, 1883),
    'Anton Bruckner': ('Romantic', 1824, 1896),
    'Bruckner': ('Romantic', 1824, 1896),
    'Edvard Grieg': ('Romantic', 1843, 1907),
    'Grieg': ('Romantic', 1843, 1907),
    'Camille Saint-Saëns': ('Romantic', 1835, 1921),
    'Saint-Saëns': ('Romantic', 1835, 1921),
    'Gabriel Fauré': ('Romantic', 1845, 1924),
    'Fauré': ('Romantic', 1845, 1924),
    'César Franck': ('Romantic', 1822, 1890),
    'Franck': ('Romantic', 1822, 1890),
    'Giacomo Puccini': ('Romantic', 1858, 1924),
    'Puccini': ('Romantic', 1858, 1924),
    'Nikolai Rimsky-Korsakov': ('Romantic', 1844, 1908),
    'Rimsky-Korsakov': ('Romantic', 1844, 1908),
    'Alexander Borodin': ('Romantic', 1833, 1887),
    'Borodin': ('Romantic', 1833, 1887),
    'Modest Mussorgsky': ('Romantic', 1839, 1881),
    'Mussorgsky': ('Romantic', 1839, 1881),
    'Bedřich Smetana': ('Romantic', 1824, 1884),
    'Smetana': ('Romantic', 1824, 1884),
    'Max Bruch': ('Romantic', 1838, 1920),
    'Bruch': ('Romantic', 1838, 1920),
    'Niccolò Paganini': ('Romantic', 1782, 1840),
    'Paganini': ('Romantic', 1782, 1840),
    'Carl Czerny': ('Romantic', 1791, 1857),
    'Czerny': ('Romantic', 1791, 1857),
    'Johann Strauss II': ('Romantic', 1825, 1899),
    'Johann Strauss': ('Romantic', 1825, 1899),
    'Charles Gounod': ('Romantic', 1818, 1893),
    'Gounod': ('Romantic', 1818, 1893),
    'Georges Bizet': ('Romantic', 1838, 1875),
    'Bizet': ('Romantic', 1838, 1875),
    'Jules Massenet': ('Romantic', 1842, 1912),
    'Massenet': ('Romantic', 1842, 1912),
    'Léo Delibes': ('Romantic', 1836, 1891),
    'Jacques Offenbach': ('Romantic', 1819, 1880),
    'Offenbach': ('Romantic', 1819, 1880),
    'Gioacchino Rossini': ('Romantic', 1792, 1868),
    'Rossini': ('Romantic', 1792, 1868),
    'Gaetano Donizetti': ('Romantic', 1797, 1848),
    'Donizetti': ('Romantic', 1797, 1848),
    'Vincenzo Bellini': ('Romantic', 1801, 1835),
    'Bellini': ('Romantic', 1801, 1835),
    'Clara Schumann': ('Romantic', 1819, 1896),
    'Fanny Mendelssohn': ('Romantic', 1805, 1847),
    'Hugo Wolf': ('Romantic', 1860, 1903),
    'Wolf': ('Romantic', 1860, 1903),

    # Late Romantic / Modern (1880-1950)
    'Gustav Mahler': ('Modern', 1860, 1911),
    'Mahler': ('Modern', 1860, 1911),
    'Richard Strauss': ('Modern', 1864, 1949),
    'R. Strauss': ('Modern', 1864, 1949),
    'Claude Debussy': ('Modern', 1862, 1918),
    'Debussy': ('Modern', 1862, 1918),
    'Maurice Ravel': ('Modern', 1875, 1937),
    'Ravel': ('Modern', 1875, 1937),
    'Sergei Rachmaninoff': ('Modern', 1873, 1943),
    'Rachmaninoff': ('Modern', 1873, 1943),
    'Rachmaninov': ('Modern', 1873, 1943),
    'Igor Stravinsky': ('Modern', 1882, 1971),
    'Stravinsky': ('Modern', 1882, 1971),
    'Béla Bartók': ('Modern', 1881, 1945),
    'Bartók': ('Modern', 1881, 1945),
    'Bartok': ('Modern', 1881, 1945),
    'Sergei Prokofiev': ('Modern', 1891, 1953),
    'Prokofiev': ('Modern', 1891, 1953),
    'Dmitri Shostakovich': ('Modern', 1906, 1975),
    'Shostakovich': ('Modern', 1906, 1975),
    'Jean Sibelius': ('Modern', 1865, 1957),
    'Sibelius': ('Modern', 1865, 1957),
    'Ralph Vaughan Williams': ('Modern', 1872, 1958),
    'Vaughan Williams': ('Modern', 1872, 1958),
    'Edward Elgar': ('Modern', 1857, 1934),
    'Elgar': ('Modern', 1857, 1934),
    'Erik Satie': ('Modern', 1866, 1925),
    'Satie': ('Modern', 1866, 1925),
    'Alexander Scriabin': ('Modern', 1872, 1915),
    'Scriabin': ('Modern', 1872, 1915),
    'Leoš Janáček': ('Modern', 1854, 1928),
    'Janáček': ('Modern', 1854, 1928),
    'Janacek': ('Modern', 1854, 1928),
    'Giacomo Puccini': ('Modern', 1858, 1924),
    'Manuel de Falla': ('Modern', 1876, 1946),
    'de Falla': ('Modern', 1876, 1946),
    'Ottorino Respighi': ('Modern', 1879, 1936),
    'Respighi': ('Modern', 1879, 1936),
    'Paul Hindemith': ('Modern', 1895, 1963),
    'Hindemith': ('Modern', 1895, 1963),
    'Francis Poulenc': ('Modern', 1899, 1963),
    'Poulenc': ('Modern', 1899, 1963),
    'Darius Milhaud': ('Modern', 1892, 1974),
    'Milhaud': ('Modern', 1892, 1974),
    'Arthur Honegger': ('Modern', 1892, 1955),
    'Honegger': ('Modern', 1892, 1955),
    'Karol Szymanowski': ('Modern', 1882, 1937),
    'Carl Orff': ('Modern', 1895, 1982),
    'Orff': ('Modern', 1895, 1982),
    'Arnold Schoenberg': ('Modern', 1874, 1951),
    'Schoenberg': ('Modern', 1874, 1951),
    'Alban Berg': ('Modern', 1885, 1935),
    'Berg': ('Modern', 1885, 1935),
    'Anton Webern': ('Modern', 1883, 1945),
    'Webern': ('Modern', 1883, 1945),
    'Zoltán Kodály': ('Modern', 1882, 1967),
    'Kodály': ('Modern', 1882, 1967),
    'Samuel Barber': ('Modern', 1910, 1981),
    'Barber': ('Modern', 1910, 1981),
    'Aaron Copland': ('Modern', 1900, 1990),
    'Copland': ('Modern', 1900, 1990),
    'George Gershwin': ('Modern', 1898, 1937),
    'Gershwin': ('Modern', 1898, 1937),
    'Heitor Villa-Lobos': ('Modern', 1887, 1959),
    'Villa-Lobos': ('Modern', 1887, 1959),
    'Aram Khachaturian': ('Modern', 1903, 1978),
    'Khachaturian': ('Modern', 1903, 1978),
    'Benjamin Britten': ('Modern', 1913, 1976),
    'Britten': ('Modern', 1913, 1976),
    'Olivier Messiaen': ('Modern', 1908, 1992),
    'Messiaen': ('Modern', 1908, 1992),
    'Witold Lutosławski': ('Modern', 1913, 1994),
    'Lutosławski': ('Modern', 1913, 1994),
    'Gustav Holst': ('Modern', 1874, 1934),
    'Holst': ('Modern', 1874, 1934),
    'Carl Nielsen': ('Modern', 1865, 1931),
    'Nielsen': ('Modern', 1865, 1931),
    'Charles Ives': ('Modern', 1874, 1954),
    'Ives': ('Modern', 1874, 1954),
    'Erich Wolfgang Korngold': ('Modern', 1897, 1957),
    'Korngold': ('Modern', 1897, 1957),
    'Mikhail Glinka': ('Romantic', 1804, 1857),
    'Glinka': ('Romantic', 1804, 1857),
    'Anton Rubinstein': ('Romantic', 1829, 1894),
    'Rubinstein': ('Romantic', 1829, 1894),
    'Mily Balakirev': ('Romantic', 1837, 1910),
    'Balakirev': ('Romantic', 1837, 1910),
    'Sergei Taneyev': ('Romantic', 1856, 1915),
    'Taneyev': ('Romantic', 1856, 1915),
    'Anton Arensky': ('Romantic', 1861, 1906),
    'Arensky': ('Romantic', 1861, 1906),
    'Nikolai Medtner': ('Modern', 1880, 1951),
    'Medtner': ('Modern', 1880, 1951),
    'Pietro Mascagni': ('Romantic', 1863, 1945),
    'Mascagni': ('Romantic', 1863, 1945),
    'Ruggero Leoncavallo': ('Romantic', 1857, 1919),
    'Leoncavallo': ('Romantic', 1857, 1919),
    'Luigi Cherubini': ('Classical', 1760, 1842),
    'Cherubini': ('Classical', 1760, 1842),
    'Florence Price': ('Modern', 1887, 1953),

    # Contemporary (1950-2000)
    'Karlheinz Stockhausen': ('Contemporary', 1928, 2007),
    'Stockhausen': ('Contemporary', 1928, 2007),
    'Pierre Boulez': ('Contemporary', 1925, 2016),
    'Boulez': ('Contemporary', 1925, 2016),
    'John Cage': ('Contemporary', 1912, 1992),
    'Cage': ('Contemporary', 1912, 1992),
    'Krzysztof Penderecki': ('Contemporary', 1933, 2020),
    'Penderecki': ('Contemporary', 1933, 2020),
    'Arvo Pärt': ('Contemporary', 1935, 0),
    'Pärt': ('Contemporary', 1935, 0),
    'Part': ('Contemporary', 1935, 0),
    'Philip Glass': ('Contemporary', 1937, 0),
    'Glass': ('Contemporary', 1937, 0),
    'Steve Reich': ('Contemporary', 1936, 0),
    'Reich': ('Contemporary', 1936, 0),
    'John Adams': ('Contemporary', 1947, 0),
    'Henryk Górecki': ('Contemporary', 1933, 2010),
    'Górecki': ('Contemporary', 1933, 2010),
    'György Ligeti': ('Contemporary', 1923, 2006),
    'Ligeti': ('Contemporary', 1923, 2006),
    'Alfred Schnittke': ('Contemporary', 1934, 1998),
    'Schnittke': ('Contemporary', 1934, 1998),
    'Sofia Gubaidulina': ('Contemporary', 1931, 0),
    'Gubaidulina': ('Contemporary', 1931, 0),
    'Toru Takemitsu': ('Contemporary', 1930, 1996),
    'Takemitsu': ('Contemporary', 1930, 1996),
    'Luciano Berio': ('Contemporary', 1925, 2003),
    'Berio': ('Contemporary', 1925, 2003),
    'Luigi Nono': ('Contemporary', 1924, 1990),
    'Iannis Xenakis': ('Contemporary', 1922, 2001),
    'Xenakis': ('Contemporary', 1922, 2001),
    'Hans Werner Henze': ('Contemporary', 1926, 2012),
    'Morton Feldman': ('Contemporary', 1926, 1987),
    'Feldman': ('Contemporary', 1926, 1987),
    'Elliott Carter': ('Contemporary', 1908, 2012),
    'Carter': ('Contemporary', 1908, 2012),
    'Terry Riley': ('Contemporary', 1935, 0),
    'La Monte Young': ('Contemporary', 1935, 0),

    # Additional Romantic
    'Nikolai Myaskovsky': ('Modern', 1881, 1950),
    'Alexander Glazunov': ('Romantic', 1865, 1936),
    'Glazunov': ('Romantic', 1865, 1936),
    'Moritz Moszkowski': ('Romantic', 1854, 1925),
    'Moszkowski': ('Romantic', 1854, 1925),
    'Isaac Albéniz': ('Romantic', 1860, 1909),
    'Albéniz': ('Romantic', 1860, 1909),
    'Albeniz': ('Romantic', 1860, 1909),
    'Enrique Granados': ('Romantic', 1867, 1916),
    'Granados': ('Romantic', 1867, 1916),
    'Joaquín Turina': ('Modern', 1882, 1949),
    'Turina': ('Modern', 1882, 1949),
    'Joaquín Rodrigo': ('Modern', 1901, 1999),
    'Rodrigo': ('Modern', 1901, 1999),
    'Pablo de Sarasate': ('Romantic', 1844, 1908),
    'Sarasate': ('Romantic', 1844, 1908),
    'Henryk Wieniawski': ('Romantic', 1835, 1880),
    'Wieniawski': ('Romantic', 1835, 1880),
    'Reinhold Glière': ('Modern', 1875, 1956),
    'Glière': ('Modern', 1875, 1956),
    'Ernő Dohnányi': ('Modern', 1877, 1960),
    'Dohnányi': ('Modern', 1877, 1960),
    'Max Reger': ('Modern', 1873, 1916),
    'Reger': ('Modern', 1873, 1916),
    'Ferruccio Busoni': ('Modern', 1866, 1924),
    'Busoni': ('Modern', 1866, 1924),
    'Alexander von Zemlinsky': ('Modern', 1871, 1942),
    'Zemlinsky': ('Modern', 1871, 1942),
    'Engelbert Humperdinck': ('Romantic', 1854, 1921),
    'Charles-Valentin Alkan': ('Romantic', 1813, 1888),
    'Alkan': ('Romantic', 1813, 1888),
    'Mikhail Ippolitov-Ivanov': ('Romantic', 1859, 1935),
    'Amy Beach': ('Romantic', 1867, 1944),
    'Beach': ('Romantic', 1867, 1944),
    'Cécile Chaminade': ('Romantic', 1857, 1944),
    'Chaminade': ('Romantic', 1857, 1944),
    'Lili Boulanger': ('Modern', 1893, 1918),
    'Nadia Boulanger': ('Modern', 1887, 1979),
    'Germaine Tailleferre': ('Modern', 1892, 1983),
    'Tailleferre': ('Modern', 1892, 1983),

    # Additional Modern
    'William Walton': ('Modern', 1902, 1983),
    'Walton': ('Modern', 1902, 1983),
    'Malcolm Arnold': ('Modern', 1921, 2006),
    'Arnold': ('Modern', 1921, 2006),
    'Michael Tippett': ('Modern', 1905, 1998),
    'Tippett': ('Modern', 1905, 1998),
    'Leonard Bernstein': ('Contemporary', 1918, 1990),
    'Bernstein': ('Contemporary', 1918, 1990),
    'Dmitri Kabalevsky': ('Modern', 1904, 1987),
    'Kabalevsky': ('Modern', 1904, 1987),
    'Nikolai Kapustin': ('Contemporary', 1937, 2020),
    'Kapustin': ('Contemporary', 1937, 2020),
    'Bohuslav Martinů': ('Modern', 1890, 1959),
    'Martinů': ('Modern', 1890, 1959),
    'Martinu': ('Modern', 1890, 1959),
    'Einojuhani Rautavaara': ('Contemporary', 1928, 2016),
    'Rautavaara': ('Contemporary', 1928, 2016),
    'Aram Khachaturian': ('Modern', 1903, 1978),

    # Additional Contemporary
    'Osvaldo Golijov': ('Contemporary', 1960, 0),
    'Kaija Saariaho': ('Contemporary', 1952, 2023),
    'Saariaho': ('Contemporary', 1952, 2023),
    'Thomas Adès': ('Contemporary', 1971, 0),
    'Adès': ('Contemporary', 1971, 0),
    'George Benjamin': ('Contemporary', 1960, 0),
    'Magnus Lindberg': ('Contemporary', 1958, 0),
    'Helmut Lachenmann': ('Contemporary', 1935, 0),
    'Lachenmann': ('Contemporary', 1935, 0),
    'Salvatore Sciarrino': ('Contemporary', 1947, 0),
    'Sciarrino': ('Contemporary', 1947, 0),
    'Wolfgang Rihm': ('Contemporary', 1952, 2024),
    'Rihm': ('Contemporary', 1952, 2024),
    'Tan Dun': ('Contemporary', 1957, 0),
    'John Corigliano': ('Contemporary', 1938, 0),
    'Corigliano': ('Contemporary', 1938, 0),
    'Jennifer Higdon': ('Contemporary', 1962, 0),
    'Mason Bates': ('Contemporary', 1977, 0),
    'Caroline Shaw': ('Contemporary', 1982, 0),
    'Missy Mazzoli': ('Contemporary', 1980, 0),
    'Nico Muhly': ('Contemporary', 1981, 0),
    'Max Richter': ('Contemporary', 1966, 0),
    'Richter': ('Contemporary', 1966, 0),
    'Ludovico Einaudi': ('Contemporary', 1955, 0),
    'Einaudi': ('Contemporary', 1955, 0),
    'Ólafur Arnalds': ('Contemporary', 1986, 0),
    'Arnalds': ('Contemporary', 1986, 0),
    'Joep Beving': ('Contemporary', 1976, 0),

    # Film composers
    'Ennio Morricone': ('Contemporary', 1928, 2020),
    'Morricone': ('Contemporary', 1928, 2020),
    'Hans Zimmer': ('Contemporary', 1957, 0),
    'Zimmer': ('Contemporary', 1957, 0),
    'John Williams': ('Contemporary', 1932, 0),
    'Howard Shore': ('Contemporary', 1946, 0),
    'James Horner': ('Contemporary', 1953, 2015),
    'Jerry Goldsmith': ('Contemporary', 1929, 2004),
    'Bernard Herrmann': ('Modern', 1911, 1975),
    'Herrmann': ('Modern', 1911, 1975),
    'Nino Rota': ('Contemporary', 1911, 1979),
    'Danny Elfman': ('Contemporary', 1953, 0),
    'Alexandre Desplat': ('Contemporary', 1961, 0),
    'Joe Hisaishi': ('Contemporary', 1950, 0),
    'Thomas Newman': ('Contemporary', 1955, 0),
    'Michael Giacchino': ('Contemporary', 1967, 0),
    'Ryuichi Sakamoto': ('Contemporary', 1952, 2023),
    'Vangelis': ('Contemporary', 1943, 2022),
    'Astor Piazzolla': ('Contemporary', 1921, 1992),
    'Piazzolla': ('Contemporary', 1921, 1992),
    'Ramin Djawadi': ('Contemporary', 1974, 0),
    'Yann Tiersen': ('Contemporary', 1970, 0),
    'Tiersen': ('Contemporary', 1970, 0),
    'Hildur Guðnadóttir': ('Contemporary', 1982, 0),
    'Alan Silvestri': ('Contemporary', 1950, 0),
    'Miklós Rózsa': ('Contemporary', 1907, 1995),
    'Rozsa': ('Contemporary', 1907, 1995),
    'John Tavener': ('Contemporary', 1944, 2013),
    'Tavener': ('Contemporary', 1944, 2013),
    'John Barry': ('Contemporary', 1933, 2011),
    'Elmer Bernstein': ('Contemporary', 1922, 2004),
    'Rachel Portman': ('Contemporary', 1960, 0),
    'Howard Blake': ('Contemporary', 1938, 0),
    'Ludovic Bource': ('Contemporary', 1970, 0),
    'Alberto Iglesias': ('Contemporary', 1955, 0),
    'Jóhann Jóhannsson': ('Contemporary', 1969, 2018),
    'Jóhannsson': ('Contemporary', 1969, 2018),
    'Nicholas Britell': ('Contemporary', 1980, 0),
    'Britell': ('Contemporary', 1980, 0),
    'Ludwig Göransson': ('Contemporary', 1984, 0),
    'Göransson': ('Contemporary', 1984, 0),
}

# Pre-built lowercase lookup map for O(1) case-insensitive matching
_COMPOSER_LOWER_MAP = {name.lower(): data for name, data in COMPOSER_PERIODS.items()}

# Period definitions (for year-based classification)
PERIODS = [
    ('Medieval', None, 1400),
    ('Renaissance', 1400, 1600),
    ('Baroque', 1600, 1750),
    ('Classical', 1750, 1820),
    ('Romantic', 1820, 1900),
    ('Modern', 1900, 1950),
    ('Contemporary', 1950, 2000),
    ('Recent', 2000, None),
]

# --- Musical Movements / Styles ---
# Maps composers to their primary musical movement(s).
# A composer can belong to multiple movements.

COMPOSER_MOVEMENTS = {
    # Ars Nova / Ars Antiqua
    'Pérotin': 'Ars Antiqua',
    'Léonin': 'Ars Antiqua',
    'Philippe de Vitry': 'Ars Nova',
    'Guillaume de Machaut': 'Ars Nova',

    # Franco-Flemish
    'Guillaume Dufay': 'Franco-Flemish School',
    'Johannes Ockeghem': 'Franco-Flemish School',
    'Josquin des Prez': 'Franco-Flemish School',
    'Orlando di Lasso': 'Franco-Flemish School',
    'Adrian Willaert': 'Venetian School',
    'Giovanni Gabrieli': 'Venetian School',

    # Venetian / Roman School
    'Giovanni Pierluigi da Palestrina': 'Roman School',
    'Palestrina': 'Roman School',

    # Impressionism
    'Claude Debussy': 'Impressionism',
    'Debussy': 'Impressionism',
    'Maurice Ravel': 'Impressionism',
    'Ravel': 'Impressionism',
    'Erik Satie': 'Impressionism',
    'Satie': 'Impressionism',
    'Ottorino Respighi': 'Impressionism',
    'Respighi': 'Impressionism',
    'Frederick Delius': 'Impressionism',
    'Manuel de Falla': 'Impressionism',
    'de Falla': 'Impressionism',
    'Isaac Albéniz': 'Impressionism',
    'Albéniz': 'Impressionism',
    'Enrique Granados': 'Impressionism',
    'Granados': 'Impressionism',

    # Expressionism / Second Viennese School
    'Arnold Schoenberg': 'Expressionism',
    'Schoenberg': 'Expressionism',
    'Alban Berg': 'Expressionism',
    'Berg': 'Expressionism',
    'Anton Webern': 'Serialism',
    'Webern': 'Serialism',

    # Neoclassicism
    'Igor Stravinsky': 'Neoclassicism',
    'Stravinsky': 'Neoclassicism',
    'Paul Hindemith': 'Neoclassicism',
    'Hindemith': 'Neoclassicism',
    'Francis Poulenc': 'Neoclassicism',
    'Poulenc': 'Neoclassicism',
    'Darius Milhaud': 'Neoclassicism',
    'Milhaud': 'Neoclassicism',
    'Arthur Honegger': 'Neoclassicism',
    'Honegger': 'Neoclassicism',
    'Sergei Prokofiev': 'Neoclassicism',
    'Prokofiev': 'Neoclassicism',
    'Germaine Tailleferre': 'Neoclassicism',
    'Tailleferre': 'Neoclassicism',

    # Nationalism (Romantic)
    'Bedřich Smetana': 'Nationalism',
    'Smetana': 'Nationalism',
    'Antonín Dvořák': 'Nationalism',
    'Dvořák': 'Nationalism',
    'Leoš Janáček': 'Nationalism',
    'Janáček': 'Nationalism',
    'Edvard Grieg': 'Nationalism',
    'Grieg': 'Nationalism',
    'Jean Sibelius': 'Nationalism',
    'Sibelius': 'Nationalism',
    'Carl Nielsen': 'Nationalism',
    'Nielsen': 'Nationalism',
    'Mikhail Glinka': 'Nationalism',
    'Glinka': 'Nationalism',
    'Modest Mussorgsky': 'Nationalism',
    'Mussorgsky': 'Nationalism',
    'Nikolai Rimsky-Korsakov': 'Nationalism',
    'Rimsky-Korsakov': 'Nationalism',
    'Alexander Borodin': 'Nationalism',
    'Borodin': 'Nationalism',
    'Mily Balakirev': 'Nationalism',
    'Balakirev': 'Nationalism',
    'Ralph Vaughan Williams': 'Nationalism',
    'Vaughan Williams': 'Nationalism',
    'Béla Bartók': 'Nationalism',
    'Bartók': 'Nationalism',
    'Zoltán Kodály': 'Nationalism',
    'Kodály': 'Nationalism',
    'Heitor Villa-Lobos': 'Nationalism',
    'Villa-Lobos': 'Nationalism',
    'Manuel de Falla': 'Nationalism',

    # Late Romanticism / Post-Romanticism
    'Gustav Mahler': 'Late Romanticism',
    'Mahler': 'Late Romanticism',
    'Richard Strauss': 'Late Romanticism',
    'R. Strauss': 'Late Romanticism',
    'Sergei Rachmaninoff': 'Late Romanticism',
    'Rachmaninoff': 'Late Romanticism',
    'Edward Elgar': 'Late Romanticism',
    'Elgar': 'Late Romanticism',
    'Anton Bruckner': 'Late Romanticism',
    'Bruckner': 'Late Romanticism',
    'Alexander Scriabin': 'Late Romanticism',
    'Scriabin': 'Late Romanticism',
    'Alexander Glazunov': 'Late Romanticism',
    'Glazunov': 'Late Romanticism',
    'Max Reger': 'Late Romanticism',
    'Reger': 'Late Romanticism',

    # Minimalism
    'Philip Glass': 'Minimalism',
    'Glass': 'Minimalism',
    'Steve Reich': 'Minimalism',
    'Reich': 'Minimalism',
    'Terry Riley': 'Minimalism',
    'La Monte Young': 'Minimalism',
    'John Adams': 'Minimalism',
    'Arvo Pärt': 'Holy Minimalism',
    'Pärt': 'Holy Minimalism',
    'Henryk Górecki': 'Holy Minimalism',
    'Górecki': 'Holy Minimalism',
    'John Tavener': 'Holy Minimalism',
    'Tavener': 'Holy Minimalism',

    # Neo-Romanticism / Post-Minimalism
    'Max Richter': 'Neo-Romanticism',
    'Richter': 'Neo-Romanticism',
    'Ludovico Einaudi': 'Neo-Romanticism',
    'Einaudi': 'Neo-Romanticism',
    'Ólafur Arnalds': 'Neo-Romanticism',
    'Arnalds': 'Neo-Romanticism',
    'Joep Beving': 'Neo-Romanticism',
    'Jóhann Jóhannsson': 'Neo-Romanticism',
    'Jóhannsson': 'Neo-Romanticism',

    # Spectralism
    'Kaija Saariaho': 'Spectralism',
    'Saariaho': 'Spectralism',
    'Magnus Lindberg': 'Spectralism',

    # Avant-Garde / Post-War
    'Karlheinz Stockhausen': 'Avant-Garde',
    'Stockhausen': 'Avant-Garde',
    'Pierre Boulez': 'Serialism',
    'Boulez': 'Serialism',
    'John Cage': 'Avant-Garde',
    'Cage': 'Avant-Garde',
    'Iannis Xenakis': 'Avant-Garde',
    'Xenakis': 'Avant-Garde',
    'György Ligeti': 'Avant-Garde',
    'Ligeti': 'Avant-Garde',
    'Krzysztof Penderecki': 'Avant-Garde',
    'Penderecki': 'Avant-Garde',
    'Luigi Nono': 'Avant-Garde',
    'Luciano Berio': 'Avant-Garde',
    'Berio': 'Avant-Garde',
    'Helmut Lachenmann': 'Avant-Garde',
    'Lachenmann': 'Avant-Garde',

    # Film Music
    'Ennio Morricone': 'Film Music',
    'Morricone': 'Film Music',
    'Hans Zimmer': 'Film Music',
    'Zimmer': 'Film Music',
    'John Williams': 'Film Music',
    'Howard Shore': 'Film Music',
    'James Horner': 'Film Music',
    'Jerry Goldsmith': 'Film Music',
    'Bernard Herrmann': 'Film Music',
    'Herrmann': 'Film Music',
    'Nino Rota': 'Film Music',
    'Danny Elfman': 'Film Music',
    'Alexandre Desplat': 'Film Music',
    'Joe Hisaishi': 'Film Music',
    'Thomas Newman': 'Film Music',
    'Michael Giacchino': 'Film Music',
    'Ramin Djawadi': 'Film Music',
    'Alan Silvestri': 'Film Music',
    'Erich Wolfgang Korngold': 'Film Music',
    'Korngold': 'Film Music',
    'Miklós Rózsa': 'Film Music',
    'Rozsa': 'Film Music',
    'Nicholas Britell': 'Film Music',
    'Britell': 'Film Music',
    'Ludwig Göransson': 'Film Music',
    'Göransson': 'Film Music',
    'Hildur Guðnadóttir': 'Film Music',
    'Jóhann Jóhannsson': 'Film Music',

    # Verismo (Opera)
    'Giacomo Puccini': 'Verismo',
    'Puccini': 'Verismo',
    'Pietro Mascagni': 'Verismo',
    'Mascagni': 'Verismo',
    'Ruggero Leoncavallo': 'Verismo',
    'Leoncavallo': 'Verismo',

    # Bel Canto (Opera)
    'Gioacchino Rossini': 'Bel Canto',
    'Rossini': 'Bel Canto',
    'Gaetano Donizetti': 'Bel Canto',
    'Donizetti': 'Bel Canto',
    'Vincenzo Bellini': 'Bel Canto',
    'Bellini': 'Bel Canto',
}

# Pre-built lowercase lookup for movements
_MOVEMENT_LOWER_MAP = {name.lower(): mov for name, mov in COMPOSER_MOVEMENTS.items()}

# Sub-period refinements (more specific than the 8 main periods)
SUB_PERIODS = {
    'Early Baroque': (1600, 1650),
    'High Baroque': (1650, 1700),
    'Late Baroque': (1700, 1750),
    'Galant Style': (1720, 1770),
    'Early Classical': (1750, 1780),
    'High Classical': (1780, 1820),
    'Early Romantic': (1820, 1850),
    'High Romantic': (1850, 1890),
    'Late Romantic': (1890, 1910),
    'Fin de Siècle': (1890, 1914),
    'Interwar Modernism': (1918, 1945),
    'Post-War Avant-Garde': (1945, 1975),
    'Post-Minimalism': (1975, 2000),
}


# --- Musical Forms / Genres (pattern → form name) ---

# Order matters: more specific patterns first
FORM_PATTERNS = [
    # Orchestral
    (r'\bSymphony\b|\bSinfonie\b|\bSymphonie\b|\bSinfonia\b', 'Symphony'),
    (r'\bConcerto\b|\bKonzert\b|\bConcierto\b', 'Concerto'),
    (r'\bOverture\b|\bOuverture\b|\bOuvertüre\b', 'Overture'),
    (r'\bSuite\b', 'Suite'),
    (r'\bTone Poem\b|\bSymphonic Poem\b|\bPoème symphonique\b|\bTondichtung\b', 'Tone Poem'),
    (r'\bDivertimento\b|\bDivertissement\b', 'Divertimento'),
    (r'\bSerenade\b|\bSérénade\b|\bSerenata\b', 'Serenade'),

    # Keyboard
    (r'\bSonata\b|\bSonate\b', 'Sonata'),
    (r'\bPrelude\b|\bPrélude\b|\bPraeludium\b|\bPreludio\b', 'Prelude'),
    (r'\bFugue\b|\bFuga\b|\bFuge\b', 'Fugue'),
    (r'\bNocturne?\b|\bNotturno\b', 'Nocturne'),
    (r'\bÉtude\b|\bEtude\b|\bStudy\b|\bEstudio\b', 'Étude'),
    (r'\bBallade\b|\bBallad\b', 'Ballade'),
    (r'\bScherzo\b', 'Scherzo'),
    (r'\bImpromptu\b', 'Impromptu'),
    (r'\bRhapsody\b|\bRhapsodie\b|\bRapsodie\b', 'Rhapsody'),
    (r'\bFantasia\b|\bFantaisie\b|\bFantasy\b|\bPhantasie\b', 'Fantasy'),
    (r'\bToccata\b', 'Toccata'),
    (r'\bVariations?\b|\bVariationen\b', 'Variations'),
    (r'\bWaltz\b|\bValse\b|\bWalzer\b', 'Waltz'),
    (r'\bPolonaise\b', 'Polonaise'),
    (r'\bMazurka\b|\bMazurek\b', 'Mazurka'),
    (r'\bInvention\b', 'Invention'),
    (r'\bBarcarolle\b|\bBarcarola\b', 'Barcarolle'),
    (r'\bBerceuse\b|\bLullaby\b', 'Berceuse'),
    (r'\bRondo\b|\bRondeau\b', 'Rondo'),
    (r'\bCapriccio\b|\bCaprice\b', 'Caprice'),
    (r'\bIntermezzo\b', 'Intermezzo'),
    (r'\bMoment musical\b|\bMoments musicaux\b', 'Moment Musical'),

    # Chamber music
    (r'\bString Quartet\b|\bStreichquartett\b|\bQuatuor à cordes\b', 'String Quartet'),
    (r'\bPiano Trio\b|\bKlaviertrio\b', 'Piano Trio'),
    (r'\bPiano Quartet\b|\bKlavierquartett\b', 'Piano Quartet'),
    (r'\bPiano Quintet\b|\bKlavierquintett\b', 'Piano Quintet'),
    (r'\bString Quintet\b|\bStreichquintett\b', 'String Quintet'),
    (r'\bString Trio\b|\bStreichtrio\b', 'String Trio'),
    (r'\bQuartet\b|\bQuartett\b|\bQuatuor\b', 'Quartet'),
    (r'\bQuintet\b|\bQuintett\b|\bQuintette\b', 'Quintet'),
    (r'\bSextet\b|\bSextett\b|\bSextuor\b', 'Sextet'),
    (r'\bOctet\b|\bOktett\b|\bOctuor\b', 'Octet'),
    (r'\bTrio\b', 'Trio'),
    (r'\bDuo\b|\bDuet\b|\bDuett\b', 'Duo'),

    # Vocal / Choral
    (r'\bOpera\b|\bOpéra\b|\bOper\b', 'Opera'),
    (r'\bRequiem\b', 'Requiem'),
    (r'\bMass\b|\bMesse\b|\bMissa\b', 'Mass'),
    (r'\bCantata\b|\bKantate\b|\bCantate\b', 'Cantata'),
    (r'\bOratorio\b', 'Oratorio'),
    (r'\bPassion\b', 'Passion'),
    (r'\bMotet\b|\bMotett?\b', 'Motet'),
    (r'\bLied\b|\bLieder\b|\bMélodie\b|\bArt Song\b', 'Lied'),
    (r'\bMadrigal\b', 'Madrigal'),
    (r'\bAria\b|\bArie\b', 'Aria'),
    (r'\bChoral\b|\bChorale?\b|\bChœur\b', 'Choral'),
    (r'\bStabat Mater\b', 'Stabat Mater'),
    (r'\bTe Deum\b', 'Te Deum'),
    (r'\bMagnificat\b', 'Magnificat'),
    (r'\bVespers\b|\bVêpres\b|\bVespro\b', 'Vespers'),

    # Dance forms
    (r'\bMinuet\b|\bMenuett?\b|\bMenuet\b', 'Minuet'),
    (r'\bGavotte\b', 'Gavotte'),
    (r'\bSarabande\b', 'Sarabande'),
    (r'\bGigue\b|\bJig\b', 'Gigue'),
    (r'\bBourrée\b|\bBourree\b', 'Bourrée'),
    (r'\bAllemande\b', 'Allemande'),
    (r'\bCourante\b|\bCorrente\b', 'Courante'),
    (r'\bPassacaglia\b|\bPassacaille\b', 'Passacaglia'),
    (r'\bChaconne\b|\bCiaccona\b', 'Chaconne'),
    (r'\bMarch\b|\bMarche\b|\bMarsch\b', 'March'),
    (r'\bBolero\b|\bBoléro\b', 'Bolero'),
    (r'\bTarantella\b|\bTarantelle\b', 'Tarantella'),
    (r'\bPolka\b', 'Polka'),

    # Other
    (r'\bSonata da chiesa\b', 'Sonata da chiesa'),
    (r'\bSonata da camera\b', 'Sonata da camera'),
    (r'\bConcerto grosso\b', 'Concerto grosso'),
    (r'\bBrandenburg\b', 'Concerto grosso'),
    (r'\bWell-Tempered\b|\bWohltemperierte\b|\bClavier bien tempéré\b', 'Prelude & Fugue'),
    (r'\bGoldberg\b', 'Variations'),
    (r'\bDiabelli\b', 'Variations'),

    # Specific well-known works/forms
    (r'\bGymnopédie\b|\bGymnopedie\b', 'Gymnopédie'),
    (r'\bGnossienne\b', 'Gnossienne'),
    (r'\bLiebestraum\b|\bLiebesträume\b', 'Liebestraum'),
    (r'\bKinderszenen\b|\bScenes from Childhood\b|\bScènes d\'enfants\b', 'Character Piece'),
    (r'\bÉtudes-Tableaux\b|\bEtudes-Tableaux\b', 'Étude'),
    (r'\bPictures at an Exhibition\b|\bTableaux d\'une exposition\b|\bBilder einer Ausstellung\b', 'Suite'),
    (r'\bCarnival of the Animals\b|\bCarnaval des animaux\b', 'Suite'),
    (r'\bSymphonic Dances?\b|\bDanses symphoniques\b', 'Symphonic Dance'),
    (r'\bLied ohne Worte\b|\bSongs? Without Words\b|\bRomances? sans paroles\b', 'Song Without Words'),

    # Additional forms
    (r'\bLitany\b|\bLitanie\b|\bLitanei\b', 'Litany'),
    (r'\bHymn\b|\bHymne\b', 'Hymn'),
    (r'\bPsalm\b|\bPsaume\b', 'Psalm'),
    (r'\bAnthem\b|\bAnthème\b', 'Anthem'),
    (r'\bElegy\b|\bÉlégie\b|\bElegie\b', 'Elegy'),
    (r'\bSerenad[ae]\b|\bNachtmusik\b|\bPetite musique de nuit\b', 'Serenade'),
    (r'\bBarcarolle\b|\bBarcarola\b|\bGondellied\b', 'Barcarolle'),
    (r'\bBagatelle\b', 'Bagatelle'),
    (r'\bHumoresque\b|\bHumoreske\b', 'Humoresque'),
    (r'\bDumka\b', 'Dumka'),
    (r'\bPavane\b|\bPavana\b', 'Pavane'),
    (r'\bSicilienne\b|\bSiciliana\b|\bSiciliano\b', 'Sicilienne'),
    (r'\bFandango\b', 'Fandango'),
    (r'\bHabanera\b|\bHavana\b', 'Habanera'),
    (r'\bSeguidilla\b', 'Seguidilla'),
    (r'\bCzárdás\b|\bCsárdás\b|\bCzardas\b', 'Czárdás'),
    (r'\bRicercar\b|\bRicercare\b', 'Ricercar'),
    (r'\bCanzona?\b', 'Canzona'),
    (r'\bSymphonic Variations\b|\bVariations symphoniques\b', 'Symphonic Variations'),
    (r'\bConcertino\b', 'Concertino'),
    (r'\bSinfonietta\b', 'Sinfonietta'),
    (r'\bConcert[oö]\b.*\borchest', 'Concerto'),
    (r'\bRomance\b|\bRomanze\b', 'Romance'),
    (r'\bNonet\b|\bNonett\b', 'Nonet'),
]

# Compile patterns for performance
_COMPILED_FORMS = [(re.compile(pat, re.IGNORECASE), form) for pat, form in FORM_PATTERNS]


# --- Catalogue number patterns ---

CATALOGUE_PATTERNS = [
    # Bach
    (r'\bBWV\s*(\d+[a-z]?)\b', 'BWV', 'J.S. Bach'),
    # Mozart
    (r'\bK\.?\s*(\d+[a-z]?)\b|\bKV\.?\s*(\d+[a-z]?)\b', 'K.', 'Mozart'),
    # Beethoven - Opus
    (r'\bOp\.?\s*(\d+)\b', 'Op.', None),
    # Haydn
    (r'\bHob\.?\s*([IVXLC]+[:/]?\d+)\b', 'Hob.', 'Haydn'),
    # Schubert
    (r'\bD\.?\s*(\d+)\b', 'D.', 'Schubert'),
    # Liszt
    (r'\bS\.?\s*(\d+)\b', 'S.', 'Liszt'),
    # Vivaldi
    (r'\bRV\s*(\d+)\b', 'RV', 'Vivaldi'),
    # Handel
    (r'\bHWV\s*(\d+)\b', 'HWV', 'Handel'),
    # Telemann
    (r'\bTWV\s*(\d+[:/]\d+)\b', 'TWV', 'Telemann'),
    # Dvořák
    (r'\bB\.?\s*(\d+)\b', 'B.', 'Dvořák'),
    # Chopin — careful, single letter
    (r'\bCT\.?\s*(\d+)\b', 'CT', 'Chopin'),
    # R. Strauss — TrV
    (r'\bTrV\s*(\d+)\b', 'TrV', 'R. Strauss'),
    # Debussy — L.
    (r'\bL\.?\s*(\d+)\b', 'L.', 'Debussy'),
]

_COMPILED_CATALOGUES = [(re.compile(pat, re.IGNORECASE), prefix, composer) for pat, prefix, composer in CATALOGUE_PATTERNS]


# --- Instrumentation detection ---

INSTRUMENT_PATTERNS = [
    # Keyboards
    (r'\bPiano\b|\bKlavier\b|\bPianoforte\b', 'Piano'),
    (r'\bOrgan\b|\bOrgue\b|\bOrgel\b', 'Organ'),
    (r'\bHarpsichord\b|\bClavecin\b|\bCembalo\b', 'Harpsichord'),
    (r'\bCelesta\b|\bCélesta\b', 'Celesta'),

    # Strings
    (r'\bViolin\b|\bViolon\b|\bGeige\b|\bVioline\b', 'Violin'),
    (r'\bViola\b|\bAlto\b|\bBratsche\b', 'Viola'),
    (r'\bCello\b|\bVioloncello\b|\bVioloncelle\b', 'Cello'),
    (r'\bDouble Bass\b|\bContrebasse\b|\bKontrabass\b', 'Double Bass'),
    (r'\bGuitar\b|\bGuitare\b|\bGitarre\b', 'Guitar'),
    (r'\bHarp\b|\bHarpe\b|\bHarfe\b', 'Harp'),
    (r'\bLute\b|\bLuth\b|\bLaute\b', 'Lute'),

    # Woodwinds
    (r'\bFlute\b|\bFlûte\b|\bFlöte\b|\bFlauto\b', 'Flute'),
    (r'\bOboe\b|\bHautbois\b|\bOboi\b', 'Oboe'),
    (r'\bClarinet\b|\bClarinette\b|\bKlarinette\b', 'Clarinet'),
    (r'\bBassoon\b|\bBasson\b|\bFagott\b', 'Bassoon'),

    # Brass
    (r'\bTrumpet\b|\bTrompette\b|\bTrompete\b', 'Trumpet'),
    (r'\bHorn\b|\bCor\b', 'Horn'),
    (r'\bTrombone\b|\bPosaune\b', 'Trombone'),
    (r'\bTuba\b', 'Tuba'),

    # Ensembles
    (r'\bOrchestra\b|\bOrchestre\b|\bOrchester\b', 'Orchestra'),
    (r'\bChamber\b|\bKammer\b|\bMusique de chambre\b', 'Chamber'),
    (r'\bChoir\b|\bChorus\b|\bChœur\b|\bChor\b', 'Choir'),
    (r'\bWind\b|\bVent\b|\bBläser\b', 'Winds'),
    (r'\bBrass\b|\bCuivres\b|\bBlechbläser\b', 'Brass'),
    (r'\bPercussion\b', 'Percussion'),
]

_COMPILED_INSTRUMENTS = [(re.compile(pat, re.IGNORECASE), instrument) for pat, instrument in INSTRUMENT_PATTERNS]


# --- Key detection ---

KEY_PATTERN = re.compile(
    r'\bin\s+([A-G])[\s\-]*(flat|sharp|#|b|♭|♯)?[\s\-]*(major|minor|maj\.?|min\.?|dur|moll|majeur|mineur)?\b',
    re.IGNORECASE
)


# --- Public API ---

def classify_track(title='', composer='', genre='', album='', year=None):
    """Classify a track based on metadata.

    Returns a dict with:
        period: str or None — musical period
        form: str or None — musical form/genre
        catalogue: str or None — catalogue number (e.g., "BWV 1043")
        instruments: list[str] — detected instruments
        key: str or None — musical key (e.g., "D minor")
        movement: str or None — musical movement/style (e.g., "Impressionism")
        sub_period: str or None — refined period (e.g., "Late Baroque")
    """
    result = {
        'period': None,
        'form': None,
        'catalogue': None,
        'instruments': [],
        'key': None,
        'movement': None,
        'sub_period': None,
    }

    # Combine text fields for searching
    search_text = f"{title} {album}"

    # 1. Period detection (from composer first, then year)
    result['period'] = detect_period(composer, year)

    # 2. Form detection
    result['form'] = detect_form(search_text)

    # 3. Catalogue number
    result['catalogue'] = detect_catalogue(title, composer)

    # 4. Instrumentation
    result['instruments'] = detect_instruments(search_text)

    # 5. Key detection
    result['key'] = detect_key(title)

    # 6. Movement / style detection
    result['movement'] = detect_movement(composer, genre)

    # 7. Sub-period refinement
    result['sub_period'] = detect_sub_period(composer, year)

    return result


def detect_period(composer='', year=None):
    """Detect musical period from composer name or year."""
    if composer:
        # Try exact match first
        entry = COMPOSER_PERIODS.get(composer)
        if not entry:
            # Try case-insensitive exact match (O(1) via pre-built lookup)
            composer_lower = composer.lower().strip()
            entry = _COMPOSER_LOWER_MAP.get(composer_lower)
            if not entry:
                # Try partial match (substring containment)
                for name_lower, data in _COMPOSER_LOWER_MAP.items():
                    if name_lower in composer_lower or composer_lower in name_lower:
                        entry = data
                        break
        if entry:
            return entry[0]

    # Fall back to year
    if year:
        for period_name, start, end in PERIODS:
            if start is None and year < end:
                return period_name
            if end is None and year >= start:
                return period_name
            if start is not None and end is not None and start <= year < end:
                return period_name

    return None


def detect_form(text):
    """Detect musical form from title/album text."""
    if not text:
        return None
    for pattern, form in _COMPILED_FORMS:
        if pattern.search(text):
            return form
    return None


def detect_catalogue(title='', composer=''):
    """Detect catalogue number from title."""
    if not title:
        return None

    for pattern, prefix, expected_composer in _COMPILED_CATALOGUES:
        m = pattern.search(title)
        if m:
            # Get the first non-None group
            num = next((g for g in m.groups() if g is not None), None)
            if num:
                # If pattern is composer-specific, verify by last name
                if expected_composer and composer:
                    comp_lower = composer.lower()
                    exp_lower = expected_composer.lower()
                    # Check full name match or last name match
                    exp_last = exp_lower.split()[-1]
                    comp_last = comp_lower.split()[-1]
                    if (exp_lower not in comp_lower
                            and comp_lower not in exp_lower
                            and exp_last != comp_last):
                        continue
                return f"{prefix} {num}"

    return None


def detect_instruments(text):
    """Detect instruments/ensemble from text."""
    if not text:
        return []
    found = []
    for pattern, instrument in _COMPILED_INSTRUMENTS:
        if pattern.search(text):
            found.append(instrument)
    return found


def detect_key(title):
    """Detect musical key from title."""
    if not title:
        return None
    m = KEY_PATTERN.search(title)
    if m:
        note = m.group(1).upper()
        accidental = m.group(2) or ''
        mode = m.group(3) or ''

        # Normalize accidental
        if accidental.lower() in ('flat', 'b', '♭'):
            accidental = '♭'
        elif accidental.lower() in ('sharp', '#', '♯'):
            accidental = '♯'
        else:
            accidental = ''

        # Normalize mode
        if mode.lower() in ('major', 'maj', 'maj.', 'dur', 'majeur'):
            mode = 'major'
        elif mode.lower() in ('minor', 'min', 'min.', 'moll', 'mineur'):
            mode = 'minor'
        else:
            mode = ''

        key = f"{note}{accidental}"
        if mode:
            key += f" {mode}"
        return key

    return None


def detect_movement(composer='', genre=''):
    """Detect musical movement/style from composer name or genre."""
    if composer:
        # Try exact match
        movement = COMPOSER_MOVEMENTS.get(composer)
        if movement:
            return movement
        # Try case-insensitive
        comp_lower = composer.lower().strip()
        movement = _MOVEMENT_LOWER_MAP.get(comp_lower)
        if movement:
            return movement
        # Try partial match
        for name_lower, mov in _MOVEMENT_LOWER_MAP.items():
            if name_lower in comp_lower or comp_lower in name_lower:
                return mov

    # Genre-based fallback
    if genre:
        gl = genre.lower()
        if 'impressionis' in gl:
            return 'Impressionism'
        if 'expressionism' in gl:
            return 'Expressionism'
        if 'minimalis' in gl:
            return 'Minimalism'
        if 'serial' in gl or 'dodecaphon' in gl or 'twelve-tone' in gl:
            return 'Serialism'
        if 'neoclassic' in gl or 'neo-classic' in gl:
            return 'Neoclassicism'
        if 'avant-garde' in gl or 'avant garde' in gl:
            return 'Avant-Garde'
        if 'film' in gl or 'soundtrack' in gl or 'motion picture' in gl or 'bande originale' in gl:
            return 'Film Music'
        if 'national' in gl:
            return 'Nationalism'

    return None


def detect_sub_period(composer='', year=None):
    """Detect sub-period refinement (more specific than main period)."""
    # Get composer birth/death years for sub-period
    birth_year = None
    if composer:
        entry = COMPOSER_PERIODS.get(composer)
        if not entry:
            comp_lower = composer.lower().strip()
            entry = _COMPOSER_LOWER_MAP.get(comp_lower)
        if entry:
            birth_year = entry[1]

    # Use birth year or track year for sub-period classification
    ref_year = birth_year or year
    if not ref_year:
        return None

    # Baroque sub-periods
    if 1580 <= ref_year < 1650:
        return 'Early Baroque'
    if 1650 <= ref_year < 1700:
        return 'High Baroque'
    if 1700 <= ref_year < 1750:
        return 'Late Baroque'

    # Classical sub-periods
    if 1720 <= ref_year < 1770 and birth_year:
        return 'Galant Style'

    # Romantic sub-periods
    if 1790 <= ref_year < 1830 and birth_year:
        return 'Early Romantic'
    if 1830 <= ref_year < 1860 and birth_year:
        return 'High Romantic'
    if 1860 <= ref_year < 1890 and birth_year:
        return 'Late Romantic'

    # Modern sub-periods
    if 1890 <= ref_year < 1914 and birth_year:
        return 'Fin de Siècle'
    if 1895 <= ref_year < 1925 and birth_year:
        return 'Interwar Modernism'

    return None


def classify_batch(tracks):
    """Classify a list of track dicts in batch.

    Each track dict should have: title, composer, genre, album, year.
    Returns list of classification dicts (same order as input).
    """
    results = []
    for track in tracks:
        result = classify_track(
            title=track.get('title', ''),
            composer=track.get('composer', ''),
            genre=track.get('genre', ''),
            album=track.get('album', ''),
            year=track.get('year'),
        )
        results.append(result)
    return results
