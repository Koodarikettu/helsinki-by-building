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
that the city's address points place; one dot per address. Memorials: works of the city's public art (the Service
Map; HAM's texts CC BY 4.0, its photos not open), picked by hand below.

Writes web/data/war.json and web/data/trenches.bin:
  u32 nLines, u32 nVerts, u32 start[nLines + 1], u8 state[nLines] (padded to 4), f32 xz[2 * nVerts] (local frame).
"""
import html
import json
import re
from collections import Counter
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely

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
COLORS = dict(structures="#3b2a20", register="#c1272d", photos="#e09a00", memorials="#1f4e8c")
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
                url="https://www.museovirasto.fi/fi/palvelut-ja-ohjeet/tietojarjestelmat/kulttuuriympariston-tietojarjestelmat/kulttuuriympaeristoen-paikkatietoaineistot")
MUSEUM = dict(label="Helsinki City Museum, in Finna", label_fi="Helsingin kaupunginmuseo, Finna", url="https://www.finna.fi")
ART = dict(label="HAM Helsinki Art Museum, public art, through the Service Map", label_fi="HAM, julkiset taideteokset, Palvelukartta",
           url="https://hri.fi/data/fi/dataset/paakaupunkiseudun-palvelukartan-rest-rajapinta")
SURVEY = dict(label="City of Helsinki, First World War fortifications (survey of 1996)",
              label_fi="Helsingin kaupunki, ensimmäisen maailmansodan aikaiset maalinnoitukset (kartoitus 1996)",
              url="https://hri.fi/data/fi/dataset/helsingin-ensimmaisen-maailmansodan-aikaiset-maalinnoitukset")


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


def kind(id, label, label_fi, sites, source, list=True):
    return dict(id=id, label=label, label_fi=label_fi, color=COLORS[id], sites=sites, source=source, list=list)


def main():
    mv = gpd.GeoDataFrame(gpd.pd.concat([gpd.read_file(RAW / f"{n}.geojson")
                                         for n in ("muinaisjaannos_piste", "muu_kulttuuriperintokohde_piste")]))
    structures, strongpoints, lines = land_front(mv)
    reg, pho, mem = register(mv), photos(), memorials()
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
                   "the great raids of February 1944, and anti-aircraft batteries ringed the city. The register's sites "
                   "are the batteries and other defences it dates to the war; the City Museum's photos show the bomb "
                   "damage, and the memorials remember the dead."),
             text_fi=("Talvi- ja jatkosodassa Neuvostoliiton pommikoneet hyökkäsivät Helsinkiin yhä uudelleen, rajuimmin "
                      "helmikuun 1944 suurpommituksissa, ja kaupunkia ympäröivät ilmatorjuntapatterit. Rekisterin kohteet "
                      "ovat sen sotaan ajoittamat patterit ja muut varustukset; kaupunginmuseon kuvat näyttävät "
                      "pommitusten tuhot, ja muistomerkit muistavat kuolleita."),
             caveat=("The register dates few sites to the war, and most batteries are gone. A photo stands at the address "
                     "the museum gives it; photos with no house number are left out."),
             caveat_fi=("Rekisteri ajoittaa sotaan vain harvoja kohteita, ja useimmat patterit ovat kadonneet. Kuva on museon "
                        "sille antamassa osoitteessa; kuvat ilman talonnumeroa on jätetty pois."),
             kinds=[kind("register", "Anti-aircraft batteries and other defences", "Ilmatorjuntapatterit ja muut varustukset", reg[1], REGISTER),
                    kind("photos", "Bomb damage", "Pommitusten tuhot", pho[1], MUSEUM),
                    kind("memorials", "Memorials", "Muistomerkit", mem[1], ART)]),
    ]
    (OUT / "war.json").write_text(json.dumps(dict(eras=eras), ensure_ascii=False, separators=(",", ":")))
    for e in eras:
        print(e["id"], {k["id"]: len(k["sites"]) for k in e["kinds"]}, "photos", sum(len(s.get("photos", [])) for k in e["kinds"] for s in k["sites"]))


if __name__ == "__main__":
    main()
