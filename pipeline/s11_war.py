"""The War view: what the two world wars left in Helsinki, on the ground rather than on its buildings.

The First World War, 1914–1918:
- The land front Russia built around the city (City of Helsinki, Maalinnoitus_*, CC BY 4.0, from its survey of 1996):
  trenches, firing positions, gun batteries, gun roads and caves as lines (trenches.bin), coloured by what the survey
  found of them, and each structure it describes as a dot. A strongpoint is named for the places that Museovirasto's
  register gives its remains ("Tukikohta XXXV:4 (Kivikko)").
- The capture of Helsinki in April 1918, at the end of the Civil War, and its dead: the City Museum's photos of the
  damage, and the memorials of 1918.
The Second World War, 1939–1945: the bombings in the City Museum's photos, and the memorials to the war's dead.
Both: the defence sites in Museovirasto's register of ancient and historic remains (CC BY 4.0) that the register dates
to the war, in its dating or its kind of defence ("toinen maailmansota 1939–1945", "I maailmansodan varustukset"), or
whose description opens by saying so ("Ensimmäisen maailmansodan aikainen luola…"). The register's records of the
land front's strongpoints are left to the city's survey, which draws them.

Photos: the Helsinki City Museum's in Finna (s00_fetch), from the war's years, of bomb or battle damage at an address
that the city's address points place; one dot per address. And the Defence Forces' photos of 1939–1945 (SA-kuva, the
Military Museum's archive, CC BY 4.0) whose title or place names an address, a building or a spot in the city, inflected
or not ("Silakoita Kauppatorilla", "Asemiesilta Messuhallissa"); a district is too coarse and is left out. One dot per
place; its photos come from shards (web/data/saphotos/<nn>.json) when its card opens.
Memorials: works of the city's public art (the Service Map; HAM's texts CC BY 4.0, its photos not open), picked by hand
below.

Writes web/data/war.json and web/data/trenches.bin:
  u32 nLines, u32 nVerts, u32 start[nLines + 1], u8 state[nLines] (padded to 4), f32 xz[2 * nVerts] (local frame).
"""
import csv
import html
import json
import re
import zlib
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from pyproj import Transformer

from .s03_tiles import to_local
from .s08_archive import OPEN, addresses, keys_of, person

RAW, OUT = Path("data/raw"), Path("web/data")

# What the 1996 survey found of a line: (its words, colour, legend in English and Finnish). The rest, planned or not
# known, go last.
STATES = [
    ("olemassaoleva", "#a3301f", "Still there", "Jäljellä"),
    ("olemassaoleva, täytetty/peitetty", "#dd9a7a", "Filled in or covered", "Täytetty tai peitetty"),
    ("tuhoutunut", "#8f979b", "Destroyed", "Tuhoutunut"),
    (None, "#cfc9bb", "Planned, or not known", "Suunniteltu tai ei tietoa"),
]
COLORS = dict(structures="#3b2a20", register="#c1272d", known="#7b3fa0", photos="#e09a00", memorials="#1f4e8c", sa="#2e9a49")
# Museovirasto's words for the kinds of site, in English.
KINDS = {
    "tykkiasemat": "gun positions", "linnoitukset": "fortifications", "linnakkeet": "forts", "luolat": "caves",
    "maavallit": "earthworks", "kivivarustukset": "stone defences", "tykkitiet": "gun roads",
    "suojahuoneet": "shelters", "valonheitinasemat": "searchlight positions", "tornit": "towers",
    "ammusvarastot": "ammunition stores", "taistelukaivannot": "trenches", "tulipesäkkeet": "firing positions",
}
WAR = [  # how the register names each war in its dating and its kind of defence, and how a description opens on it
    re.compile(r"ensimmäi(nen|sen) maailmanso[dt]|\bI\.? maailmanso[dt]|\bI ms\b", re.I),  # -sota, -sodan
    re.compile(r"toi(nen|sen) maailmanso[dt]|\bII\.? maailmanso[dt]|\bII ms\b", re.I),
]
OPENS = [re.compile(r"^(mahdollisesti )?ensimmäisen maailmansodan ?aikai", re.I),
         re.compile(r"^(mahdollisesti )?toisen maailmansodan ?aikai", re.I)]
# The City Museum's photos of a war's damage, by their title or subject words: both damage and war (a fire of 1945 is
# not the war's); shelters, splinter boards and aircraft are another story.
DAMAGE = re.compile(r"pommitu|pommivauri|tuho|vauri")
WARTIME = re.compile(r"pommitu|pommivauri|valtau|valloitu|sisällisso|kansalaisso|sota|sodan|ilmahyök|tykkitul")
NOT_DAMAGE = re.compile(r"pommisuoj|pommikone|sirpalesuoj")
# The Service Map's public art (ids) that remember each war or its dead; the Civil War of 1918 goes with the first.
MEMORIALS = [
    [23221,   # Suomalaisten sotilaiden hauta (the Whites who fell taking Helsinki, 12.4.1918)
     23208,   # Saksalaisten sotilaiden hauta
     23210,   # Kurt Seibtin ja Arthur Beukertin muistomerkki (German soldiers, 1918)
     23191,   # Punaisten teloitettujen ja vankileirillä kuolleiden hautamuistomerkki
     22996,   # Crescendo / Vuoden 1918 Kansalaissodan uhrien muistomerkki
     23217,   # Habsburg-höyrylaivan muistomerkki (1918)
     23175,   # Pellingin retken muistomerkki (1918)
     23371],  # Suomenlinnan vankileirin muistomerkki (1918–1919)
    [55958,   # Talvisodan kansallinen muistomerkki
     23214,   # Sodanajan naisen muistomerkki
     23309,   # Juutalaispakolaisten muistomerkki / Apua anovat kädet
     23156,   # Juutalaisuhrien muistomerkki
     23073,   # Karjalaan jääneiden vainajien muistomerkki
     23181,   # Pitäjänmäen sankarihautamuistomerkki
     23179,   # Haagan sankaripatsas
     23075,   # Katkaistu elämä, Sankarihauta (Lauttasaari)
     23115,   # Kuoleva Soturi (Kulosaari's dead of 1939–1944)
     23125,   # Ässärykmentin muistomerkki / Jalkaväkirykmentti 11
     23487],  # Inkeriläisten ja karjalaisten heimoveteraanien muistomerkki (1941–1944)
]
YEARS = [(1914, 1918), (1939, 1945)]
ROMAN = dict(I=1, V=5, X=10, L=50)
REGISTER = dict(label="Finnish Heritage Agency, register of ancient and historic remains",
                label_fi="Museovirasto, muinaisjäännösrekisteri",
                url="https://www.museovirasto.fi/fi/palvelut-ja-ohjeet/tietojarjestelmat/kulttuuriympariston-tietojarjestelmat/kulttuuriympaeristoen-paikkatietoaineistot",
                licence="CC BY 4.0")
MUSEUM = dict(label="Helsinki City Museum, in Finna", label_fi="Helsingin kaupunginmuseo, Finna", url="https://www.finna.fi")
SA = dict(label="SA-kuva, the Military Museum's photo archive, in Finna", label_fi="SA-kuva, Sotamuseon kuva-arkisto, Finna",
          url="https://www.finna.fi/Search/Results?filter%5B%5D=building%3A%220%2FSA-kuva%2F%22&lookfor=Helsinki", licence="CC BY 4.0")
SHARDS = 16
# Places of the register whose names are words or names of people in the photos' titles ("Prinssi tutustuu …",
# "Liisan saunassa"), and Loppi, a town as well as a spot.
NOT_PLACES = {"prinssi", "sauna", "loppi", "akseli", "bunkkeri", "kalervo", "komentosilta", "vuorenjuuri"}
ART = dict(label="HAM Helsinki Art Museum, public art, through the Service Map", label_fi="HAM, julkiset taideteokset, Palvelukartta",
           url="https://hri.fi/data/fi/dataset/paakaupunkiseudun-palvelukartan-rest-rajapinta", licence="CC BY 4.0")
# The city's own account of the raids of 1944, with its air defence in numbers.
HISTORY = dict(label="City of Helsinki, Helsinki's history: the great raids of 1944",
               label_fi="Helsingin kaupunki, Helsingin historia: suurpommitukset 1944",
               url="https://historia.hel.fi/en/kaannekohdat/20th-century/the-great-raids-against-helsinki-1944",
               url_fi="https://historia.hel.fi/fi/kaannekohdat/1900-luku/helsingin-suurpommitukset-1944")
SURVEY = dict(label="City of Helsinki, First World War fortifications (survey of 1996)",
              label_fi="Helsingin kaupunki, ensimmäisen maailmansodan aikaiset maalinnoitukset (kartoitus 1996)",
              url="https://hri.fi/data/fi/dataset/helsingin-ensimmaisen-maailmansodan-aikaiset-maalinnoitukset", licence="CC BY 4.0")

# Positions of the city's air defence in 1939–1944 that the register lacks, gathered by hand from the sources below; the
# ones the register has (Myllykallio "Lautta", Taivaskallio, Patterimäki "Paja", Munkkiniemi "Torppa" and others) are
# left to it. Each stands where its source puts it: an address, or a place in the city's place-name register (a park,
# field, street, island or district) or a memorial's coordinates, and says how close that is. Outside Helsinki
# (Westend, Mäkkylä) and guesses ("Kasapelto", probably Roihupelto) are left out.
SRC = dict(
    museum=("Ilmatorjuntamuseo, tykit", "https://www.ilmatorjuntamuseo.fi/ilmatorjuntamuseo/kokoelmat/tykit/"),
    lehti=("Ilmatorjunta-lehti 2/2023 (Ahti Lappi)", "https://bin.yhdistysavain.fi/1601152/jLzVxzwJKBzageTXi4Z90_dH2C/Ilmatorjunta%202-2023.pdf"),
    lappi=("Ahti Lappi: Helsingin ilmapuolustuskyvyn parantaminen 1943–1944",
           "https://www.sshs.fi/content/uploads/2023/02/Helsingin_ilmapuolustuskyvyn_parantaminen_1943-1944.pdf"),
    kauppi=("Kauppi, kandidaatintutkielma, Maanpuolustuskorkeakoulu 2013", "https://www.doria.fi/bitstream/handle/10024/93428/SK1517_Kauppi_VM.pdf"),
    roihuvuori=("Wikipedia: Roihuvuori", "https://fi.wikipedia.org/wiki/Roihuvuori"),
    vuosaari=("Vuosaari-lehti 2.3.2022", "https://www.vuosaarilehti.fi/2022/03/02/syyta-muistaa-helsingin-ilmapuolustusta-talvella-1944/"),
    ilmatorjunta=("Wikipedia: Helsingin ilmatorjunta", "https://fi.wikipedia.org/wiki/Helsingin_ilmatorjunta"),
    raids=("Wikipedia: Helsingin suurpommitukset", "https://fi.wikipedia.org/wiki/Helsingin_suurpommitukset"),
    patterimaki=("Museovirasto, muinaisjäännösrekisteri: Patterimäki", "https://www.kyppi.fi/to.aspx?id=112.1000030675"),
)
NAMES_FI = {"1st heavy battery": "1. raskas patteri", "2nd heavy battery": "2. raskas patteri",
            "101st light battery": "101. kevyt patteri", "105th light battery": "105. kevyt patteri", "Fire-control centre": "Tulenjohtokeskus"}
HOW_NEAR = {  # what the dot stands for
    "exact": ("The dot is at the address.", "Piste on osoitteessa."),
    "place": ("The sources name the place, not the spot within it.", "Lähteet kertovat paikan, eivät kohtaa sen sisällä."),
    "area": ("The sources name only the district or island: the dot marks its middle, not the position.",
             "Lähteet kertovat vain alueen tai saaren: piste on sen keskellä, ei aseman kohdalla."),
}
# (name, kind in English and Finnish, years, where: ("name", place, kind of place) | ("addr", address) | ("wgs", lat, lon),
#  how near, what it was in English and Finnish, source)
POSITIONS = [
    ("Kaivo", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1944", ("name", "Kaivopuisto", "Puisto"), "place",
     "Osasto Kaivo, the 61st and 62nd Heavy Anti-Aircraft Batteries, twelve 88 mm guns. In 1941 a light section stood in the park too.",
     "Osasto Kaivo, 61. ja 62. raskas ilmatorjuntapatteri, yhteensä kaksitoista 88 mm:n tykkiä. Vuonna 1941 puistossa oli myös kevyt ilmatorjuntajaos.", "museum"),
    ("Rata", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1943–1944", ("name", "Santahamina", "Kaupunginosa"), "area",
     "The 7th Heavy Anti-Aircraft Battery, six 88 mm guns and an Irja fire-control radar. The 91st (February 1944) and the 66th (August 1944) heavy batteries were on the island too.",
     "7. raskas ilmatorjuntapatteri, kuusi 88 mm:n tykkiä ja Irja-tulenjohtotutka. Santahaminassa olivat myös 91. (helmikuu 1944) ja 66. raskas patteri (elokuu 1944).", "lehti"),
    ("Käpy", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1943–1944", ("name", "Käpylä", "Kaupunginosa"), "area",
     "The 9th Heavy Anti-Aircraft Battery at Käpylä's trotting track, six 88 mm guns and an Irja radar; the 78th heavy battery was in Käpylä in February 1944.",
     "9. raskas ilmatorjuntapatteri Käpylän raviradalla, kuusi 88 mm:n tykkiä ja Irja-tutka; Käpylässä oli helmikuussa 1944 myös 78. raskas patteri.", "lehti"),
    ("Lato", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1943–1944", ("name", "Patteripellonraitti", "Kevyen liikenteen väylä, polku"), "place",
     "The 108th Heavy Anti-Aircraft Battery on the fields of Latokartano in Viikki, four 75 mm Škoda guns and an Irja radar. The path is named after the battery's field.",
     "108. raskas ilmatorjuntapatteri Viikin Latokartanon pellolla, neljä 75 mm:n Škoda-tykkiä ja Irja-tutka. Patteripellonraitti on nimetty patterin pellon mukaan.", "lehti"),
    ("Kasa", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1944", ("name", "Prinsessantie", "Katu"), "place",
     "The 107th Heavy Anti-Aircraft Battery, four 75 mm guns and an anti-aircraft machine gun, where the houses of Prinsessantie in Roihuvuori now stand.",
     "107. raskas ilmatorjuntapatteri, neljä 75 mm:n tykkiä ja ilmatorjuntakonekivääri, nykyisten Prinsessantien talojen paikalla Roihuvuoressa.", "roihuvuori"),
    ("Pommi", "Decoy battery", "Valepatteri", "1944", ("name", "Nordsjön kartano", "Kartano"), "place",
     "A battery of three guns on the grounds of Vuosaari's Nordsjö manor, about 200 metres from the main building, from the raid of 26–27 February 1944.",
     "Kolmen tykin patteri Vuosaaren Nordsjön kartanon mailla, noin 200 metrin päässä päärakennuksesta, 26.–27.2.1944 pommituksesta alkaen.", "vuosaari"),
    ("1st heavy battery", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1941", ("name", "Länsi-Mustasaari", "Saari, luoto, kari(kko), kivi(kko), särkkä"), "area",
     "The 1st Heavy Anti-Aircraft Battery on Länsi-Mustasaari in Suomenlinna; a memorial gun stands on the island.",
     "1. raskas ilmatorjuntapatteri Suomenlinnan Länsi-Mustasaaressa; saarella on muistotykki.", "lappi"),
    ("2nd heavy battery", "Heavy anti-aircraft", "Raskas ilmatorjunta", "1941", ("name", "Kustaanmiekka", "Saari, luoto, kari(kko), kivi(kko), särkkä"), "area",
     "The 2nd Heavy Anti-Aircraft Battery on Kustaanmiekka in Suomenlinna.", "2. raskas ilmatorjuntapatteri Suomenlinnan Kustaanmiekassa.", "lappi"),
    *[(f"{isle}", "Coastal anti-aircraft", "Rannikon ilmatorjunta", "1944", ("name", isle, "Saari, luoto, kari(kko), kivi(kko), särkkä"), "area",
       "One of the coast artillery's three anti-aircraft batteries on the islands, under the city's air-defence regiment in the raids of 1944.",
       "Yksi rannikkotykistön kolmesta ilmatorjuntapatterista saarilla, alistettuna kaupungin ilmatorjuntarykmentille vuoden 1944 pommituksissa.", "kauppi")
      for isle in ("Melkki", "Harmaja", "Isosaari")],
    ("105th light battery", "Light anti-aircraft", "Kevyt ilmatorjunta", "1941", ("name", "Ilmalankatu", "Katu"), "area",
     "The 105th Light Anti-Aircraft Battery at Ilmala.", "105. kevyt ilmatorjuntapatteri Ilmalassa.", "lappi"),
    ("101st light battery", "Light anti-aircraft", "Kevyt ilmatorjunta", "1941", ("name", "Helsinki-Malmin lentoasema", "Pysäkki, asema"), "area",
     "The 101st Light Anti-Aircraft Battery at Malmi airport.", "101. kevyt ilmatorjuntapatteri Malmin lentoasemalla.", "lappi"),
    *[(place, "Light anti-aircraft", "Kevyt ilmatorjunta", "1941", ("name", place, laji), "area",
       f"A light anti-aircraft section at {place}.", f"Kevyt ilmatorjuntajaos: {place}.", "lappi")
      for place, laji in (("Verkkosaari", "Osa-alue"), ("Hernesaari", "Osa-alue"), ("Koskela", "Osa-alue"))],
    ("Eläintarha", "Anti-aircraft machine guns", "Ilmatorjuntakonekiväärit", "1941", ("name", "Eläintarha", "Puisto"), "place",
     "Anti-aircraft machine guns of the 105th company in Eläintarha, by Pasila.", "105. ilmatorjuntakonekiväärikomppanian konekiväärejä Eläintarhassa Pasilan laidalla.", "lappi"),
    ("Alppila", "Anti-aircraft machine guns", "Ilmatorjuntakonekiväärit", "1941", ("name", "Alppila", "Osa-alue"), "area",
     "An anti-aircraft machine-gun section in Alppila.", "Ilmatorjuntakonekiväärijaos Alppilassa.", "lappi"),
    ("Postitalo", "Light anti-aircraft", "Kevyt ilmatorjunta", "1941", ("addr", "mannerheiminaukio 1"), "exact",
     "An anti-aircraft machine-gun section at the main post office, with a 20 mm Breda gun.", "Ilmatorjuntakonekiväärijaos Postitalolla, jossa oli 20 mm:n Breda-tykki.", "lappi"),
    ("Kokkokallio", "Searchlights", "Valonheittimet", "1943–1944", ("name", "Kokkokallio", "Puisto"), "place",
     "Searchlights on Kokkokallio in Reimarla, named by the register's page on the nearby battery of Patterimäki.",
     "Valonheittimiä Reimarlan Kokkokalliolla; mainittu muinaisjäännösrekisterissä läheisen Patterimäen kohdalla.", "patterimaki"),
    ("Raija II", "Air-surveillance radar", "Ilmavalvontatutka", "1943–1944", ("wgs", 60.1340056, 25.0201889), "place",
     "One of the two German Freya radars, called Raija, that watched for the bombers; its memorial plaque is on Kuninkaansaari.",
     "Toinen pommikoneita valvoneista saksalaisista Freya-tutkista, Raija; sen muistolaatta on Kuninkaansaaressa.", "ilmatorjunta"),
    ("Fire-control centre", "Command post", "Tulenjohtokeskus", "1944", ("addr", "korkeavuorenkatu 26"), "exact",
     "The air defence's fire-control centre in the rock shelter at Korkeavuorenkatu 26; a bronze plaque by its door remembers it.",
     "Ilmapuolustuksen tulenjohtokeskus Korkeavuorenkatu 26:n kalliosuojassa; oven pielessä on muistolaatta.", "raids"),
]


def roman(s: str) -> int:
    """XXXV → 35; a strongpoint with a name (MUNKKA, SKATTA) sorts last."""
    if not s or set(s) - set(ROMAN):
        return 999
    v = [ROMAN[c] for c in s]
    return sum(-a if a < b else a for a, b in zip(v, v[1:] + [0]))


def at(x: float, y: float) -> list:
    lx, lz = to_local(np.array([[x, y]]))[0]
    return [round(float(lx), 1), round(float(lz), 1)]


def clean(s) -> str:
    return "" if s is None or s != s else re.sub(r"\s+", " ", html.unescape(str(s))).strip()  # s != s: pandas' NaN


def shorten(text: str, limit: int = 700) -> str:
    """The first sentences, up to about `limit` characters."""
    text = clean(text)
    if len(text) <= limit:
        return text
    cut = text.rfind(". ", 0, limit)
    return text[:cut + 1] if cut > 0 else text[:limit].rstrip() + " …"


def register_page(page: str) -> dict:
    """A register page's dating, kind of defence (Tarkenne) and description."""
    field = lambda label: clean(re.sub(r"<[^>]+>", " ", m[1])) if (m := re.search(
        rf'<td class="norm">{label}:</td>\s*<td class="norm"[^>]*>(.*?)</td>', page, re.S)) else ""
    m = re.search(r'<span id="kuvaus"[^>]*>.*?<td class="norm">(.*?)</td>', page, re.S)
    return dict(dating=field("Ajoitus"), kind=field("Tarkenne"), text=clean(re.sub(r"<[^>]+>", " ", m[1])) if m else "")


def wars_of(page: dict) -> list[int]:
    head = f"{page['dating']} | {page['kind']}"
    return [w for w in (0, 1) if WAR[w].search(head) or OPENS[w].search(page["text"])]


def land_front(mv: gpd.GeoDataFrame):
    lines = gpd.read_file(RAW / "Maalinnoitus_kohteet.geojson")
    state = lines.olotila.map({w: i for i, (w, *_) in enumerate(STATES[:-1])}).fillna(len(STATES) - 1).astype(int)
    km = (lines.length.groupby(state).sum() / 1000).round(1)
    coords = [shapely.get_coordinates(g) for g in lines.geometry]
    start = np.cumsum([0] + [len(c) for c in coords]).astype("<u4")
    xz = to_local(np.concatenate(coords)).astype("<f4")
    states = state.to_numpy().astype("u1")
    (OUT / "trenches.bin").write_bytes(np.array([len(coords), len(xz)], "<u4").tobytes() + start.tobytes() +
                                       states.tobytes() + bytes(-len(states) % 4) + xz.tobytes())

    units = gpd.read_file(RAW / "Maalinnoitus_yksikot.geojson")
    sites = []
    for u in units.itertuples():
        what = clean(u.yksikko) or clean(u.laji)
        when = {"alkuvuosi": ("early ", "alkuvuonna "), "loppuvuosi": ("late ", "loppuvuonna ")}.get(u.ajoitushuom, ("", ""))
        year = int(u.ajoitus) if u.ajoitus == u.ajoitus and u.ajoitus else None
        rows = [[k, clean(v)] for k, v in (("Type", u.yksikkotyyppi), ("Construction", u.rakennustapa),
                                           ("History", u.rakennushistoria)) if clean(v)]
        sites.append(dict(
            at=at(u.geometry.x, u.geometry.y), name=f"{what[:1].upper()}{what[1:]} {u.tunnistenumero}",
            sub=f"Strongpoint {u.tukikohtanumero}" + (f" · built {when[0]}{year}" if year else ""),
            sub_fi=f"Tukikohta {u.tukikohtanumero}" + (f" · rakennettu {when[1]}{year}" if year else ""),
            rows=rows))

    # Each strongpoint where its outline lies, or else amid its structures; named for the places of its remains.
    places = Counter()
    for name in mv.kohdenimi.map(clean):
        m = re.match(r"Tukikohta ([IVXL]+):\S* \((.+)\)$", name)
        for place in re.split(r"[,/]", m[2]) if m else []:  # "(Kivikko, Jakomäki)", "(Vartioharju/Puotila)"
            places[m[1], place.strip()] += 1
    outline = gpd.read_file(RAW / "Maalinnoitus_rajaukset.geojson").query("rajaustyyppi == 'tukikohta'")
    centre = {r.tukikohtanumero: r.geometry.centroid for r in outline.itertuples()}
    strongpoints = []
    for tk in sorted(set(units.tukikohtanumero.dropna()), key=roman):
        g = centre.get(tk) or units[units.tukikohtanumero == tk].geometry.union_all().centroid
        names = [p for (k, p), _ in sorted(((k, n) for k, n in places.items() if k[0] == tk), key=lambda kv: -kv[1])]
        strongpoints.append(dict(at=at(g.x, g.y), name=f"Strongpoint {tk}", name_fi=f"Tukikohta {tk}", sub=", ".join(names[:3])))
    legend = [dict(color=c, label=en, label_fi=fi, n=float(km.get(i, 0))) for i, (_, c, en, fi) in enumerate(STATES)]
    return sites, strongpoints, legend


def register(mv: gpd.GeoDataFrame) -> list[list]:
    """The register's defence sites of each war."""
    out = [[], []]
    d = mv[mv.tyyppi.fillna("").str.contains("puolustus") & ~mv.kohdenimi.map(clean).str.startswith("Tukikohta")]
    for r in d.drop_duplicates("mjtunnus").itertuples():
        page = register_page((RAW / "register" / f"{r.mjtunnus}.html").read_text(encoding="utf-8", errors="replace"))
        kind = clean(r.alatyyppi) if clean(r.alatyyppi) != "ei määritelty" else ""
        for w in wars_of(page):
            out[w].append(dict(at=at(r.geometry.x, r.geometry.y), name=clean(r.kohdenimi),
                               sub=KINDS.get(kind, kind), sub_fi=kind, text=shorten(page["text"]), url=r.url))
    return [sorted(s, key=lambda s: s["name"]) for s in out]


def photos() -> list[list]:
    """The City Museum's photos of damage in each war's years, one dot per address."""
    pts = gpd.read_file(RAW / "Osoiteluettelo_piste_rekisteritiedot.geojson")[["katunimi", "osoitenumero", "geometry"]]
    place = {k: (p.geometry.x, p.geometry.y) for p in pts.itertuples() for k in keys_of(p.katunimi, str(p.osoitenumero or ""))}
    by_war = [{}, {}]
    for line in open(RAW / "finna_hkm.jsonl"):
        r = json.loads(line)
        year = int(r["year"][:4]) if str(r.get("year", ""))[:4].isdigit() else None
        w = next((i for i, (a, b) in enumerate(YEARS) if year and a <= year <= b), None)
        words = " ".join([r.get("title") or ""] + [s[0] for s in r.get("subjects") or [] if s]).lower()
        if w is None or not (DAMAGE.search(words) and WARTIME.search(words)) or NOT_DAMAGE.search(words) or not r.get("images") \
                or r.get("imageRights", {}).get("copyright") not in OPEN:
            continue
        a = next((a for a in addresses(r) if a in place or a.rstrip("abcdefghijklmnopqrstuvwxyzåäö") in place), None)
        if a is None:
            continue
        xy = place.get(a) or place[a.rstrip("abcdefghijklmnopqrstuvwxyzåäö")]
        maker = next((person(x["name"]) for x in r.get("nonPresenterAuthors") or [] if x.get("role") == "valokuvaaja"), None)
        site = by_war[w].setdefault(a, dict(at=at(*xy), name=" ".join(x[:1].upper() + x[1:] for x in a.split()), photos=[]))
        site["photos"].append({k: v for k, v in dict(r=r["id"], y=year, t=clean(r.get("title")), m=maker,
                                                      l=r["imageRights"]["copyright"]).items() if v})
    out = []
    for sites in by_war:
        for s in sites.values():
            s["photos"].sort(key=lambda p: p["y"])
            years = sorted({p["y"] for p in s["photos"]})
            n = len(s["photos"])
            s["sub"] = f"{', '.join(map(str, years))} · {n} photo{'s' if n > 1 else ''}"
            s["sub_fi"] = f"{', '.join(map(str, years))} · {n} kuva{'a' if n > 1 else ''}"
        out.append(sorted(sites.values(), key=lambda s: s["name"]))
    return out


# Finnish case forms of a place name's last word: (ending, weak stem, strong stem) for the endings whose consonants
# change (Kauppakatu → Kauppakadulla, Lauttasaari → Lauttasaaressa); any other name inflects on itself.
GRADE = [("katu", "kadu", "katu"), ("saari", "saare", "saare"), ("kaari", "kaare", "kaare"), ("niemi", "nieme", "nieme"),
         ("lahti", "lahde", "lahte"), ("mäki", "mäe", "mäke"), ("ranta", "ranna", "ranta"), ("silta", "silla", "silta"),
         ("kenttä", "kentä", "kenttä"), ("kirkko", "kirko", "kirkko"), ("puistikko", "puistiko", "puistikko"),
         ("klinikka", "klinika", "klinikka"), ("luoto", "luodo", "luoto"), ("vuori", "vuore", "vuore"), ("pelto", "pello", "pelto"),
         ("portti", "porti", "portti"), ("kallio", "kallio", "kallio"), ("joki", "joe", "joke"), ("lampi", "lammi", "lampe")]


def forms(name: str) -> set[str]:
    """A place name and its case forms, lower case: Kauppatori, -torin, -torilla, -torille, -torilta, -torissa, -torista, -toriin."""
    n = name.lower()
    weak = strong = n if n[-1] in "aeiouyäö" else n + "i"  # Ateneum → Ateneumissa
    for end, w, st in GRADE:
        if n.endswith(end):
            weak, strong = n[:-len(end)] + w, n[:-len(end)] + st
            break
    a = "a" if re.search(r"[aou]", n.split()[-1]) else "ä"
    return {n, weak + "n", strong + strong[-1] + "n"} | {weak + e for e in (f"ll{a}", "lle", f"lt{a}", f"ss{a}", f"st{a}")}


def places() -> dict:
    """{a case form of a place's name: (name, x, y)}: the buildings Wikidata names and the spots of the city's place-name
    register (squares, parks, islands, streets, stations; not districts). A form two places share finds neither."""
    from .s12_other import ISLANDS, PLACES_OF_THEIR_OWN, SPOTS  # s12 imports this module
    names = gpd.read_file(RAW / "Nimisto_piste_rekisteritiedot.geojson")
    areas = {r.nimi_suomi.lower() for r in names.itertuples() if r.nimi_suomi and r.laji_selite not in SPOTS}
    found = {}
    for r in names.itertuples():
        n = r.nimi_suomi
        if r.geometry and n and r.laji_selite in SPOTS and (n.lower() not in areas or r.laji_selite in PLACES_OF_THEIR_OWN
                                                            or n.lower() in ISLANDS):
            found.setdefault(n.lower(), (n, r.geometry.x, r.geometry.y))
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "gone", "geometry"])
    centre = dict(zip(b.key, b.geometry.representative_point()))
    for r in csv.DictReader(open(RAW / "wd_buildings.csv")):
        if r["prt"] in centre and r["labelFi"]:
            found.setdefault(r["labelFi"].lower(), (r["labelFi"], centre[r["prt"]].x, centre[r["prt"]].y))
    out, shared = {}, set()
    for place in found.values():
        for f in forms(place[0]):
            if f in out and out[f][0] != place[0]:
                shared.add(f)
            out.setdefault(f, place)
    return {f: v for f, v in out.items() if f not in shared}


def place_named(text: str, spots: dict):
    """The place a photo's place or title names: the longest name found. A name in the nominative opening the title and
    going on as a sentence is a word, not the place ("Prinssi saapuu …")."""
    words = list(re.finditer(r"[\wåäöÅÄÖ-]+", text))
    best = None
    for n in (3, 2, 1):
        for i in range(len(words) - n + 1):
            g = " ".join(w[0] for w in words[i:i + n]).lower()
            place = spots.get(g)
            if place and place[0].lower() in NOT_PLACES:
                continue
            after = text[words[i + n - 1].end():][:2]
            if not place or (words[i].start() == 0 and g == place[0].lower() and re.match(r"\s[a-zåäö]", after)):
                continue
            if not best or len(place[0]) > len(best[0]):
                best = place
    return best


def sa_photos(addr: dict, spots: dict) -> list:
    """The SA-kuva photos whose place or title names one place in the city, one dot per place; the first photo stays on
    the page, the rest go to shards. The record's own place goes before its title."""
    by = {}
    for line in open(RAW / "finna_sa.jsonl"):
        r = json.loads(line)
        if not r.get("images") or r.get("imageRights", {}).get("copyright") != "CC BY 4.0":
            continue
        own = ", ".join(x.strip() for p in r.get("subjectPlaces") or [] for x in p.split(",")[1:])  # after "Helsinki"
        title = r.get("title") or ""
        place = None
        for text in (own, title):
            hit = next((a for a in addresses({"subjectPlaces": [f"Helsinki, {m[0]}" for m in re.finditer(
                r"[A-ZÅÄÖ][\wåäö-]+(?:\s[A-ZÅÄÖ]?[\wåäö-]+)?\s+\d+[a-zåäö]?", text)]}) if a in addr), None)
            place = (" ".join(x[:1].upper() + x[1:] for x in hit.split()), *addr[hit]) if hit else place_named(text, spots)
            if place:
                break
        if not place:
            continue
        year = int(r["year"][:4]) if str(r.get("year", ""))[:4].isdigit() else None
        maker = next((person(a["name"]) for a in r.get("nonPresenterAuthors") or [] if a.get("name") and a["name"] != "Tuntematon"), None)
        site = by.setdefault(place[0], dict(at=at(place[1], place[2]), name=place[0], photos=[]))
        site["photos"].append({k: v for k, v in dict(r=r["id"], y=year, t=clean(title), m=maker, l="CC BY 4.0",
                                                      o="SA-kuva").items() if v})
    sites, shards = [], [{} for _ in range(SHARDS)]
    for s in by.values():
        ph = sorted(s["photos"], key=lambda p: p.get("y") or 9999)
        n, years = len(ph), sorted({p["y"] for p in ph if p.get("y")})
        shard = zlib.crc32(s["name"].encode()) % SHARDS
        shards[shard][s["name"]] = ph
        span = f"{years[0]}–{years[-1]}" if len(years) > 1 else str(years[0]) if years else ""
        sites.append(dict(at=s["at"], name=s["name"], photos=ph[:1], shard=shard, n=n,
                          sub=" · ".join(filter(None, [span, f"{n} photo{'s' if n > 1 else ''}"])),
                          sub_fi=" · ".join(filter(None, [span, f"{n} kuva{'a' if n > 1 else ''}"]))))
    folder = OUT / "saphotos"
    folder.mkdir(exist_ok=True)
    for i, sh in enumerate(shards):
        (folder / f"{i:02d}.json").write_text(json.dumps(sh, ensure_ascii=False, separators=(",", ":")))
    return sorted(sites, key=lambda s: (-s["n"], s["name"]))


def positions() -> list:
    """POSITIONS placed: an address point, a place in the place-name register, or WGS84 coordinates."""
    names = gpd.read_file(RAW / "Nimisto_piste_rekisteritiedot.geojson")
    place = {(r.nimi_suomi, r.laji_selite): (r.geometry.x, r.geometry.y) for r in names.itertuples() if r.geometry}
    pts = gpd.read_file(RAW / "Osoiteluettelo_piste_rekisteritiedot.geojson")
    addr = {f"{r.katunimi} {r.osoitenumero}".lower(): (r.geometry.x, r.geometry.y) for r in pts.itertuples()}
    gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
    out = []
    for name, kind_en, kind_fi, years, where, near, text, text_fi, src in POSITIONS:
        xy = place[where[1], where[2]] if where[0] == "name" else addr[where[1]] if where[0] == "addr" \
            else gk25.transform(where[2], where[1])
        label, url = SRC[src]
        out.append(dict(at=at(*xy), name=name, name_fi=NAMES_FI.get(name, name), sub=f"{kind_en} · {years}", sub_fi=f"{kind_fi} · {years}",
                        text=f"{text} {HOW_NEAR[near][0]}", text_fi=f"{text_fi} {HOW_NEAR[near][1]}",
                        source=dict(label=label, url=url)))
    return sorted(out, key=lambda s: s["name_fi"])


def memorials() -> list[list]:
    art = {a["id"]: a for a in json.loads((RAW / "public_art.json").read_text())}
    out = []
    for ids in MEMORIALS:
        sites = []
        for i in ids:
            a = art[i]
            # "Artist: Title, year. © Kuva: HAM / photographer": the work's credit, not the photo's; else the address
            credit = {k: clean(v).split("©")[0].strip().rstrip(".") for k, v in (a.get("picture_caption") or {}).items()}
            credit = {k: v for k, v in credit.items() if re.search(r"\b(1[5-9]|20)\d\d$", v)}
            sites.append(dict(
                at=at(*a["location"]["coordinates"]), name=a["name"].get("en") or a["name"]["fi"], name_fi=a["name"]["fi"],
                sub=credit.get("en") or clean(a["street_address"].get("en")), sub_fi=credit.get("fi") or clean(a["street_address"]["fi"]),
                text=shorten((a.get("description") or {}).get("en") or ""), text_fi=shorten((a.get("description") or {}).get("fi") or ""),
                url=f"https://palvelukartta.hel.fi/en/unit/{i}", url_fi=f"https://palvelukartta.hel.fi/fi/unit/{i}"))
        out.append(sorted(sites, key=lambda s: s["name_fi"]))
    return out


def kind(id, label, label_fi, sites, source, list=True, group=None, **more):
    """A kind of site; kinds of one group are a single choice in the menu."""
    return dict(id=id, label=label, label_fi=label_fi, color=COLORS[id], sites=sites, source=source, list=list,
                **({"group": group} if group else {}), **more)


def main():
    mv = gpd.GeoDataFrame(gpd.pd.concat([gpd.read_file(RAW / f"{n}.geojson")
                                         for n in ("muinaisjaannos_piste", "muu_kulttuuriperintokohde_piste")]))
    structures, strongpoints, lines = land_front(mv)
    reg, pho, mem = register(mv), photos(), memorials()
    pts = gpd.read_file(RAW / "Osoiteluettelo_piste_rekisteritiedot.geojson")
    sa = sa_photos({k: (p.geometry.x, p.geometry.y) for p in pts.itertuples() for k in keys_of(p.katunimi, str(p.osoitenumero or ""))},
                   places())
    sa_n = sum(s.pop("n") for s in sa)
    sa_fi = f"{sa_n:,}".replace(",", " ")  # 1 562
    total, there = sum(g["n"] for g in lines), lines[0]["n"]
    eras = [
        dict(id="ww1", label="First World War", label_fi="1. maailmansota", years="1914–1918",
             text=("Russia made Helsinki part of Peter the Great's Naval Fortress, which was to bar the sea road to "
                   "Petrograd, and built a land front of strongpoints around the city: trenches, firing positions, "
                   "shelters, caves and gun batteries, joined by gun roads. The lines are what the city's survey of 1996 "
                   f"found of them, {total:.0f} km, {there:.0f} km still there. In April 1918, at the end of the Civil War, "
                   "a German division took Helsinki from the Reds: the City Museum's photos show the damage, and the "
                   "memorials remember the dead of both sides."),
             text_fi=("Venäjä liitti Helsingin Pietari Suuren merilinnoitukseen, jonka piti suojata meritie Pietariin, ja "
                      "rakensi kaupungin ympärille maarintaman: tukikohtia taisteluhautoineen, tulipesäkkeineen, "
                      "suojahuoneineen, luolineen ja tykkipattereineen sekä niiden välisiä tykkiteitä. Viivat ovat se, "
                      f"minkä kaupungin vuoden 1996 kartoitus niistä löysi, {total:.0f} km, josta {there:.0f} km yhä "
                      "paikallaan. Huhtikuussa 1918, sisällissodan lopulla, saksalainen divisioona valtasi Helsingin "
                      "punaisilta: kaupunginmuseon kuvat näyttävät tuhot, ja muistomerkit muistavat molempien puolten "
                      "kuolleita."),
             caveat=("Since 1996 more of the land front may have been filled in or built over. The survey's and the "
                     "register's texts are in Finnish. A photo stands at the address the museum gives it."),
             caveat_fi=("Vuoden 1996 jälkeen maarintamaa on voitu täyttää tai rakentaa umpeen. Kuva on museon sille "
                        "antamassa osoitteessa."),
             lines="trenches.bin", linesTitle="Lines in 1996, km", linesTitle_fi="Linjat vuonna 1996, km", legend=lines,
             places=strongpoints,
             kinds=[kind("structures", "The land front", "Maalinnoitus", structures, SURVEY, list=False),
                    kind("register", "Batteries and caves in the register", "Rekisterin patterit ja luolat", reg[0], REGISTER),
                    kind("photos", "Damage in the capture of Helsinki, 1918", "Helsingin valtauksen tuhot 1918", pho[0], MUSEUM),
                    kind("memorials", "Memorials of 1918", "Vuoden 1918 muistomerkit", mem[0], ART)]),
        dict(id="ww2", label="Second World War", label_fi="2. maailmansota", years="1939–1945",
             text=("In the Winter War and the Continuation War Soviet bombers struck Helsinki again and again, hardest in "
                   "the great raids of February 1944. By then the city's air defence had 13–15 heavy anti-aircraft "
                   "batteries with 77 guns, 41 light guns, 36 searchlights, 13 sound locators and three coastal "
                   "anti-aircraft batteries on the islands. Only a few of their sites are in the heritage register, those "
                   "whose remains it has surveyed; more are known from the regiment's history and articles, many only "
                   "to the park, field or island. The City Museum's photos show the bomb damage, the Defence Forces' "
                   f"photographers the city at war, {sa_n:,} photos at the {len(sa)} places they name, "
                   "and the memorials remember the dead."),
             text_fi=("Talvi- ja jatkosodassa Neuvostoliiton pommikoneet hyökkäsivät Helsinkiin yhä uudelleen, rajuimmin "
                      "helmikuun 1944 suurpommituksissa. Silloin kaupungin ilmapuolustuksessa oli 13–15 raskasta "
                      "ilmatorjuntapatteria ja niissä 77 tykkiä, 41 kevyttä it-tykkiä, 36 valonheitintä, 13 kuulosuunninta "
                      "sekä kolme rannikkoilmatorjuntapatteria saarilla. Muinaisjäännösrekisterissä on vain harvat niiden "
                      "paikoista, ne joiden jäänteet on inventoitu; useampia tunnetaan ilmatorjunnan historiikeista ja "
                      "artikkeleista, monia vain puiston, kentän tai saaren tarkkuudella. Kaupunginmuseon kuvat "
                      "näyttävät pommitusten tuhot, puolustusvoimien kuvaajat sotavuosien kaupungin, "
                      f"{sa_fi} kuvaa {len(sa)} paikassa, jotka kuvat nimeävät, "
                      "ja muistomerkit muistavat kuolleita."),
             caveat=("Most batteries were temporary and are gone or built over; the city's archaeological inventory of "
                     "2024–2025 is still adding sites to the register. A photo stands at the address the museum gives it; "
                     "photos with no house number are left out. The Defence Forces' photos are found by the place their "
                     "title names, which may be what they show rather than where they were taken; most name only "
                     "Helsinki and are left out."),
             caveat_fi=("Useimmat patterit olivat tilapäisiä, ja ne ovat kadonneet tai jääneet rakennusten alle; kaupungin "
                        "arkeologinen inventointi 2024–2025 lisää rekisteriin yhä kohteita. Kuva on museon sille antamassa "
                        "osoitteessa; kuvat ilman talonnumeroa on jätetty pois. Puolustusvoimien kuvat on sijoitettu "
                        "otsikon nimeämään paikkaan, joka voi olla kuvan kohde eikä kuvauspaikka; useimmat nimeävät vain "
                        "Helsingin, ja ne on jätetty pois."),
             sources=[HISTORY],
             groups=dict(defences=dict(label="Defences and anti-aircraft positions", label_fi="Varustukset ja ilmatorjunta-asemat")),
             kinds=[kind("register", "Defences in the heritage register", "Rekisteriin kirjatut varustukset", reg[1], REGISTER,
                         group="defences"),
                    kind("known", "Positions known from other sources", "Muista lähteistä tunnetut asemat", positions(),
                         dict(label="Literature and articles; each card names its own", label_fi="Kirjallisuus ja artikkelit; kortti kertoo omansa",
                              url=HISTORY["url"], url_fi=HISTORY["url_fi"]), group="defences"),
                    kind("photos", "Bomb damage", "Pommitusten tuhot", pho[1], MUSEUM),
                    # its photos are originals of 4–8 MB, which Finna serves at no smaller size: loaded on a click only
                    kind("sa", "The city at war, SA-kuva", "Sodan kaupunki, SA-kuva", sa, SA, shards="saphotos", large=True),
                    kind("memorials", "Memorials", "Muistomerkit", mem[1], ART)]),
    ]
    (OUT / "war.json").write_text(json.dumps(dict(eras=eras), ensure_ascii=False, separators=(",", ":")))
    for e in eras:
        print(e["id"], {k["id"]: len(k["sites"]) for k in e["kinds"]}, "photos", sum(s.get("n", len(s.get("photos", []))) for k in e["kinds"] for s in k["sites"]))


if __name__ == "__main__":
    main()
