"""The Other menu: views laid on the ground as the War view is (web/app.js reads both files alike).

- Public art: every work of the city's public art in the Service Map (HAM's texts CC BY 4.0, its photos not open), as a
  dot coloured by the period of its year, with the periods of the buildings.
- Trams: Helsinki's tram tracks through time from OpenHistoricalMap (CC0), each with the years it opened and closed;
  the map shows the network of the timeline's year and greys the tracks closed before it (trams.bin).
- The Finnish Heritage Agency's photos of Helsinki in Finna (CC BY 4.0), each at the place it names, the most exact
  that can be found: an address; a building that Wikidata names ("Säätytalo"); a square, park, island or street in
  the city's place-name register ("Senaatintori Helsinki"); or a point Finna gives other than the city's centre. A
  photo naming only the city or a district is left out: it would pile up on the district's middle. One dot per place.
- Parking fines: the city's parking fines and notices of 2014–2023 (Pysäköintivirheet Helsingissä, CC BY 4.0), by the
  street of their address, for the streets of the street-name view to be coloured by them year by year.

Writes web/data/other.json, web/data/fines.json (the parking fines by street and year) and web/data/trams.bin:
  u32 nLines, u32 nVerts, u32 start[nLines + 1], i16 opened[nLines], i16 closed[nLines] (0: never, or not known;
  padded to 4), f32 xz[2 * nVerts] (local frame).
"""
import csv
import json
import re
import zlib
from collections import Counter
from pathlib import Path

import geopandas as gpd

import numpy as np
from pyproj import Transformer

from .periods import PERIODS, period_index
from .s03_tiles import to_local
from .s08_archive import ADDRESS, keys_of, person
from .s11_war import ART, at, clean, shorten

RAW, OUT = Path("data/raw"), Path("web/data")
TRAM_COLORS = ("#0f8a4f", "#b9bfc2")  # in use in the timeline's year; closed by then
MV = dict(label="Finnish Heritage Agency, photos in Finna", label_fi="Museovirasto, kuvat Finnassa", url="https://www.finna.fi",
          licence="CC BY 4.0")
# A place's photos go to one of these shards (web/data/mvphotos/<nn>.json), which the page loads when its card opens;
# the page itself carries the places and the first photo of each.
SHARDS = 32
# The place-name register's kinds that name a spot rather than an area
SPOTS = {"Puisto", "Tori, katuaukio, aukio", "Saari, luoto, kari(kko), kivi(kko), särkkä", "Niemi, niemeke", "Katu",
         "Liikuntapaikka, urheilualue", "Silta, eritaso", "Satamaterminaali, laituri, venesatama", "Kartano",
         "Pysäkki, asema", "Lahti, poukama", "Kevyen liikenteen väylä, polku"}
PLACES_OF_THEIR_OWN = {"Saari, luoto, kari(kko), kivi(kko), särkkä", "Niemi, niemeke"}
CITY_CENTRE = "POINT(24.94354 60.16664)"  # where Finna puts a photo that names only Helsinki
# Finna's own point stands at the middle of whatever the photo names, a district as readily as a park: it is kept only
# for a name that is no district, municipality or country. Two districts are places of their own, the fortress islands.
COARSE = {"helsinki", "suomi", "vantaa", "espoo", "helsingin maalaiskunta", "helsingin pitäjä", "helsingin lähiympäristö",
          "vironniemen helsingin vanha asemakaava-alue", "töölö"}  # Töölö: Etu- and Taka-Töölö together
ISLANDS = {"suomenlinna", "santahamina"}
OHM = dict(label="OpenHistoricalMap, Helsinki's tram tracks", label_fi="OpenHistoricalMap, Helsingin raitiotiet",
           url="https://www.openhistoricalmap.org/", licence="CC0")
FINES = dict(label="City of Helsinki, parking violations", label_fi="Helsingin kaupunki, pysäköintivirheet",
             url="https://hri.fi/data/en_GB/dataset/pysakointivirheet-helsingissa",
             url_fi="https://hri.fi/data/fi/dataset/pysakointivirheet-helsingissa", licence="CC BY 4.0")
# Fines on a street in a year, from this many up, and fines per 100 metres of street: the colouring's steps (its
# colours are web/app.js FINE_COLORS).
FINE_STEPS = [1, 10, 25, 50, 100, 250, 500]
FINE_DENSE = [0, 2, 5, 10, 25, 50, 100]


def art() -> dict:
    works = json.loads((RAW / "public_art.json").read_text())
    kinds = {}
    for a in works:
        if not a.get("location"):
            continue
        # "Artist: Title, year. © Kuva: HAM / photographer": the work's credit, not the photo's; its year ends it
        credit = {k: clean(v).split("©")[0].strip().rstrip(".") for k, v in (a.get("picture_caption") or {}).items()}
        credit = {k: v for k, v in credit.items() if re.search(r"\b(1[5-9]|20)\d\d$", v)}
        year = int(credit["fi"][-4:]) if "fi" in credit else None
        name = a["name"]
        kinds.setdefault(period_index(year) if year else None, []).append(dict(
            at=at(*a["location"]["coordinates"]), name=name.get("en") or name["fi"], name_fi=name["fi"],
            sub=credit.get("en") or clean((a.get("street_address") or {}).get("en")),
            sub_fi=credit.get("fi") or clean((a.get("street_address") or {}).get("fi")),
            text=shorten((a.get("description") or {}).get("en") or ""), text_fi=shorten((a.get("description") or {}).get("fi") or ""),
            url=f"https://palvelukartta.hel.fi/en/unit/{a['id']}", url_fi=f"https://palvelukartta.hel.fi/fi/unit/{a['id']}"))
    out = [dict(id=f"p{i + 1}", label=PERIODS[i][1], color=PERIODS[i][4], menu=False, list=True, source=ART,
                sites=sorted(kinds[i], key=lambda s: s["name_fi"])) for i in range(len(PERIODS)) if i in kinds]
    if None in kinds:
        out.append(dict(id="undated", label="Year not known", label_fi="Vuosi ei tiedossa", color="#8f979b", menu=False,
                        list=True, source=ART, sites=sorted(kinds[None], key=lambda s: s["name_fi"])))
    n = sum(len(k["sites"]) for k in out)
    return dict(
        id="art", menu="other", label="Public art", label_fi="Julkiset taideteokset", years="1800s–today", years_fi="1800-luvulta tähän päivään",
        text=(f"The {n} works of the city's public art, sculptures, memorials, fountains and reliefs in streets and parks, "
              "coloured by the period of their year with the colours of the buildings. A work's card gives its artist "
              "and year and the Helsinki Art Museum's text."),
        text_fi=(f"Kaupungin {n} julkista taideteosta, veistoksia, muistomerkkejä, suihkulähteitä ja reliefejä kaduilla ja "
                 "puistoissa, valmistumisvuoden aikakauden mukaan samoin värein kuin rakennukset. Teoksen kortti kertoo "
                 "tekijän, vuoden ja Helsingin taidemuseon kuvauksen."),
        caveat="The photos are HAM's and not openly licensed: each card links the Service Map, where they are.",
        caveat_fi="Kuvat ovat HAMin eivätkä avoimesti lisensoituja: kortti linkittää Palvelukarttaan, jossa ne ovat.",
        kinds=out)


def trams() -> dict:
    # a way with no opening year cannot be placed in time (two short stretches in Kallio and Munkkiniemi): left out
    ways = [w for w in json.loads((RAW / "ohm_trams.json").read_text())["elements"] if w["tags"].get("start_date", "")[:4].isdigit()]
    gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
    year = lambda s: int(s[:4]) if s and s[:4].isdigit() else 0
    coords = [np.array(gk25.transform([p["lon"] for p in w["geometry"]], [p["lat"] for p in w["geometry"]])).T for w in ways]
    opened = np.array([year(w["tags"].get("start_date")) for w in ways], "<i2")
    closed = np.array([year(w["tags"].get("end_date")) for w in ways], "<i2")
    start = np.cumsum([0] + [len(c) for c in coords]).astype("<u4")
    xz = to_local(np.concatenate(coords)).astype("<f4")
    years = opened.tobytes() + closed.tobytes()
    (OUT / "trams.bin").write_bytes(np.array([len(ways), len(xz)], "<u4").tobytes() + start.tobytes() + years +
                                    bytes(-len(years) % 4) + xz.tobytes())
    length = np.array([np.hypot(*np.diff(c, axis=0).T).sum() for c in coords]) / 1000
    first = int(opened[opened > 0].min())
    return dict(
        id="trams", menu="other", label="Trams", label_fi="Raitiotiet", years=f"{first}–", years_fi=f"{first}–",
        text=(f"Helsinki's tram tracks through time as OpenHistoricalMap draws them, {length.sum():.0f} km in all: the "
              f"map shows the network of the timeline's year and greys the tracks closed before it ({length[closed > 0].sum():.0f} km "
              "in all). Drag the timeline or play it to watch the network grow."),
        text_fi=(f"Helsingin raitiotiet ajan mukana OpenHistoricalMapin mukaan, yhteensä {length.sum():.0f} km: kartta "
                 f"näyttää aikajanan vuoden verkon ja harmaana sitä ennen lakkautetut radat (kaikkiaan {length[closed > 0].sum():.0f} km). "
                 "Vedä aikajanaa tai toista se, niin näet verkon kasvavan."),
        caveat=("OpenHistoricalMap is drawn by volunteers: a track's years may be rounded, and some tracks may be "
                "missing."),
        caveat_fi="OpenHistoricalMapia piirtävät vapaaehtoiset: radan vuodet voivat olla pyöristettyjä, ja joitain ratoja voi puuttua.",
        tracks="trams.bin", linesTitle="Tracks", linesTitle_fi="Radat",
        legend=[dict(color=TRAM_COLORS[0], label="In use in the timeline's year", label_fi="Käytössä aikajanan vuonna"),
                dict(color=TRAM_COLORS[1], label="Closed before it", label_fi="Lakkautettu sitä ennen")],
        kinds=[dict(id="tracks", label="Tram tracks", label_fi="Raitiotiet", color=TRAM_COLORS[0], menu=False, list=False,
                    source=OHM, sites=[])])


def place_of(r: dict, addr: dict, named: dict, spot: dict, gk25=None, box=None, areas=frozenset()):
    """(name, x, y) of the most exact place a Finna record names, or None: an address, a building by name, a spot in
    the place-name register (each looked up from the last, most exact, part of a Helsinki place), else Finna's own
    point, for a name that is no area (`areas`: the register's districts)."""
    for p in r.get("subjectPlaces") or []:
        parts = [x.strip() for x in p.split(",")]
        if not any(x.startswith(("Helsinki", "Helsingfors")) for x in parts):
            continue
        for x in reversed(parts):
            n = re.sub(r"\s+Helsinki$", "", x)
            m = ADDRESS.match(n)
            if m and (k := f"{m['street'].strip().lower()} {m['num']}{(m['letter'] or '').lower()}") in addr:
                return n, *addr[k]
            if n.lower() in named:
                return n, named[n.lower()].x, named[n.lower()].y
            if n.lower() in spot:
                return n, *spot[n.lower()]
    for g in r.get("geoLocations") or []:
        m = re.match(r"POINT\(([\d.]+) ([\d.]+)\)", g)
        name = re.sub(r"\s+Helsinki$", "", (r.get("subjectPlaces") or ["Helsinki"])[-1].split(",")[-1].strip())
        coarse = name.lower() in COARSE or name.lower() in areas and name.lower() not in ISLANDS
        if m and g != CITY_CENTRE and gk25 and not coarse:
            x, y = gk25.transform(float(m[1]), float(m[2]))
            if box[0][0] < x < box[1][0] and box[0][1] < y < box[1][1]:
                return name, x, y
    return None


def mv_photos() -> dict:
    """The Heritage Agency's photos, one dot per place they name."""
    names = gpd.read_file(RAW / "Nimisto_piste_rekisteritiedot.geojson")
    # A name that is also a district's means the district ("Töölö" the stop, "Pitäjänmäki" the station), unless the
    # spot is an island or cape ("Seurasaari"). A park named for its district ("Pitäjänmäki") means the district too.
    areas = {r.nimi_suomi.lower() for r in names.itertuples() if r.nimi_suomi and r.laji_selite not in SPOTS}
    spot = {r.nimi_suomi.lower(): (r.geometry.x, r.geometry.y) for r in names.itertuples()
            if r.geometry and r.nimi_suomi and r.laji_selite in SPOTS
            and (r.nimi_suomi.lower() not in areas or r.laji_selite in PLACES_OF_THEIR_OWN)}
    areas -= set(spot)
    pts = gpd.read_file(RAW / "Osoiteluettelo_piste_rekisteritiedot.geojson")
    addr = {k: (p.geometry.x, p.geometry.y) for p in pts.itertuples() for k in keys_of(p.katunimi, str(p.osoitenumero or ""))}
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "gone", "geometry"])
    centre = dict(zip(b.key, b.geometry.representative_point()))
    named = {}
    for r in csv.DictReader(open(RAW / "wd_buildings.csv")):
        if r["prt"] in centre and r["labelFi"]:
            named.setdefault(r["labelFi"].lower(), centre[r["prt"]])
    gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
    lo, hi = gk25.transform(24.78, 60.09), gk25.transform(25.27, 60.33)

    places = {}
    for line in open(RAW / "finna_mv.jsonl"):
        r = json.loads(line)
        if not r.get("images") or r.get("imageRights", {}).get("copyright") != "CC BY 4.0":
            continue
        p = place_of(r, addr, named, spot, gk25, (lo, hi), areas)
        if not p:
            continue
        year = int(m[0]) if (m := re.search(r"\d{4}", str(r.get("year") or ""))) else None
        if year and year < 1839:  # before photography: the year of what it shows ("Helsingin tuomiokirkko, 1830")
            year = None
        maker = next((person(a["name"]) for a in r.get("nonPresenterAuthors") or [] if a.get("name")), None)
        coll = next((b["translated"] for b in r.get("buildings") or [] if b["value"].startswith("1/")), None)
        site = places.setdefault(p[0], dict(at=at(p[1], p[2]), name=p[0], photos=[]))
        site["photos"].append({k: v for k, v in dict(r=r["id"], y=year, t=clean(r.get("title")), m=maker, l="CC BY 4.0",
                                                      o=f"Museovirasto, {coll}" if coll else "Museovirasto").items() if v})
    sites, shards = [], [{} for _ in range(SHARDS)]
    for s in places.values():
        ph = sorted(s["photos"], key=lambda p: p.get("y") or 9999)  # oldest first, those with no year last
        n, years = len(ph), [p["y"] for p in ph if p.get("y")]
        shard = zlib.crc32(s["name"].encode()) % SHARDS
        shards[shard][s["name"]] = ph
        span = f"{years[0]}–{years[-1]}" if years and years[0] != years[-1] else str(years[0]) if years else ""
        sites.append(dict(at=s["at"], name=s["name"], photos=ph[:1], shard=shard, n=n,
                          sub=" · ".join(filter(None, [span, f"{n} photo{'s' if n > 1 else ''}"])),
                          sub_fi=" · ".join(filter(None, [span, f"{n} kuva{'a' if n > 1 else ''}"])),
                          url=f"https://www.finna.fi/Search/Results?lookfor={s['name']}&filter%5B%5D=building%3A%220%2FMuseovirasto%2F%22"))
    sites.sort(key=lambda s: (-s["n"], s["name"]))  # the most photographed first
    folder = OUT / "mvphotos"
    folder.mkdir(exist_ok=True)
    for i, sh in enumerate(shards):
        (folder / f"{i:02d}.json").write_text(json.dumps(sh, ensure_ascii=False, separators=(",", ":")))
    total = sum(s.pop("n") for s in sites)
    return dict(
        id="mvphotos", menu="other", label="Heritage Agency photos", label_fi="Museoviraston kuvat", years="1860s–today",
        years_fi="1860-luvulta tähän päivään",
        text=(f"{total} photos of Helsinki from the Finnish Heritage Agency's collections, at {len(sites)} places they name: "
              "an address, a building, a square, park, island or street. A card shows all of a place's photos, oldest "
              "first, with a button for each decade where there are many."),
        text_fi=(f"{total} Museoviraston kokoelmien Helsinki-kuvaa {len(sites)} paikassa, jotka kuvat nimeävät: osoite, "
                 "rakennus, tori, puisto, saari tai katu. Kortti näyttää paikan kaikki kuvat vanhimmasta alkaen, ja "
                 "kun niitä on paljon, jokaiselle vuosikymmenelle on oma painikkeensa."),
        caveat=("Most of the agency's Helsinki photos name only the city or a district, and are left out. A photo stands at "
                "the place it names, which may be what it shows rather than where it was taken from. Its year is Finna's, "
                "and is now and then the year of what it shows."),
        caveat_fi=("Useimmat Museoviraston Helsinki-kuvista nimeävät vain kaupungin tai kaupunginosan, ja ne on jätetty pois. "
                   "Kuva on nimeämässään paikassa, joka voi olla kuvan kohde eikä kuvauspaikka. Vuosi on Finnan, ja joskus "
                   "se on kuvatun kohteen vuosi."),
        kinds=[dict(id="mv", label="Places with photos", label_fi="Kuvauspaikat", color="#0a7d8c", menu=False, list=True, source=MV,
                    sites=sites, shards="mvphotos")])


def reason(field: str) -> str:
    """'0601 pysäköinti ilman p-tunnusta ' → 'Pysäköinti ilman p-tunnusta': the main reason without its code; a few
    fields carry a second reason after it."""
    r = re.split(r"\s+\d{3,4}\s+", re.sub(r"^\d+\s*", "", field).strip())[0]
    return r[:1].upper() + r[1:]


ACUTE = str.maketrans("éèáàíóú", "eeaaiou")  # not ä, ö or å: Mäkitie is not Makitie


def street_key(name: str) -> str:
    """A street's name to match on: the registers write 'Kolmas linja' and 'Kolmas Linja', 'Katajanokanlaituri' and
    'Katajanokan laituri', 'Tarkk'ampujankatu' and 'Tarkk'Ampujankatu', 'Castréninkatu' and 'Castreninkatu'."""
    return re.sub(r"[\s'’-]", "", name.lower().translate(ACUTE))


def street_of(address: str) -> str:
    """'Fredrikinkatu 12 A' → 'Fredrikinkatu'; 'Tilkantori (tori tai aukio)' → 'Tilkantori'."""
    return re.sub(r"\s+\d.*$", "", re.sub(r"\s*\(.*?\)", "", address or "").strip())


# Street areas that run beside a street's carriageway rather than along it: counted only for a street that has no other
SIDE = {"Kevyt liikenne", "Kevyt liikenne, t/h", "Erillinen kev.liik.väylä", "Pysäköintialue", "Tontti"}


def street_lengths() -> dict:
    """{street: metres}, for its fines per 100 m: its built street areas' own lengths (pituus), or an area's size over
    its mean width where it gives none, summed. A cycle and foot way or a parking area beside the carriageway counts
    only for a street that is nothing else: summed with it, Eteläinen Rautatiekatu would run 1,960 m, not 640."""
    areas = gpd.read_file(RAW / "YLRE_Katualue_alue.geojson")
    areas = areas[areas.geometry.notna() & (areas.rakentamisen_tila != "Rakentamaton")]
    areas["m"] = areas.pituus.where(areas.pituus > 0, areas.geometry.area / areas.keskim_leveys.where(areas.keskim_leveys > 0))
    areas["main"] = ~areas.kayttotarkoitus.isin(SIDE) & areas.m.notna()
    has_main = areas.groupby("kadun_nimi").main.transform("any")
    m = areas[areas.main | ~has_main].groupby("kadun_nimi").m.sum(min_count=1)
    return {k: round(v) for k, v in m.items() if v == v and v > 0}


def fine_rows():
    """(year, address, reason) of every parking fine: the yearly files of 2014–2022 (CSV, Latin-1 or UTF-8, ';' or ',')
    and 2023 from the WFS, less those it marks as not at their real place (filed under the parking control's address)."""
    for path in sorted((RAW / "fines").glob("*.csv")):
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        rows = csv.reader(text.splitlines(), delimiter=";" if text.split("\n", 1)[0].count(";") > 3 else ",")
        next(rows)
        for r in rows:  # month, year, address, stage, reason, …
            if len(r) > 4 and r[1].isdigit():
                yield int(r[1]), r[2], r[4]
    for f in json.loads((RAW / "Pysakointivirheet.geojson").read_text())["features"]:
        r = f["properties"]
        if r["todellinen_sijainti"] == "Kyllä":
            yield int(r["vuosi"]), r["osoite"], r["virheen_paasyy_ja_paaluokka"]


def fines() -> dict:
    """The parking fines of 2014–2023 by the street of their address, matched to the street areas of the street-name
    view (s07_labels' streetmap.json), for the streets to be coloured by them year by year."""
    names = json.loads((OUT / "streetmap.json").read_text())["names"]
    match = {street_key(n): n for n in names}
    per, totals = {}, Counter()
    for year, addr, why in fine_rows():
        totals[year] += 1
        name = match.get(street_key(street_of(addr)))
        if name:
            per.setdefault((name, year), Counter())[reason(why) if why else ""] += 1
    years = sorted(totals)
    reasons = sorted({w for c in per.values() for w in c if w})
    code = {w: i for i, w in enumerate(reasons)}
    streets = {}
    for (name, year), c in per.items():  # per year: the count, then the three commonest reasons and their counts
        top = [x for w, k in c.most_common() if w for x in (code[w], k)][:6]
        streets.setdefault(name, [[] for _ in years])[years.index(year)] = [sum(c.values()), *top]
    mapped = [sum(v[i][0] for v in streets.values() if v[i]) for i in range(len(years))]
    lengths = street_lengths()
    # Some 4,400 streets × ten years would add a megabyte to the page's start: they come when the view first opens.
    (OUT / "fines.json").write_text(json.dumps(dict(years=years, reasons=reasons, totals=[totals[y] for y in years],
                                                    mapped=mapped, streets=streets, lengths=lengths),
                                               ensure_ascii=False, separators=(",", ":")))
    span = f"{years[0]}–{years[-1]}"
    share = [round(100 * (1 - m / totals[y])) for m, y in zip(mapped, years)]
    left = f"{min(share)}–{max(share)}" if min(share) != max(share) else str(share[0])
    return dict(
        id="fines", menu="other", label="Parking fines", label_fi="Pysäköintivirheet", years=span, years_fi=span,
        streets="fines.json", steps=FINE_STEPS, dense=FINE_DENSE, span=[years[0], years[-1]],
        text=(f"The parking fines and notices the city's parking inspectors and the police wrote in {span}, on the street of "
              "the address each was written to. A street is coloured by its fines in the year shown, the more the redder, "
              "by all its fines or by its fines per 100 metres, so that a short street fined often stands out beside a "
              "long one; pick a year on the timeline. A click on a street gives its fines year by year and the year's "
              "commonest reasons."),
        text_fi=(f"Pysäköinninvalvonnan ja poliisin vuosina {span} kirjoittamat pysäköintivirhemaksut ja huomautukset sen "
                 "kadun mukaan, jonka osoitteeseen maksu kirjattiin. Katu on värjätty näytetyn vuoden maksujen mukaan, "
                 "sitä punaisempi mitä enemmän maksuja, joko kaikkien maksujen tai 100 metriä kohden laskettujen mukaan, "
                 "jolloin lyhyt usein sakotettu katu erottuu pitkän rinnalla; valitse vuosi aikajanalta. Katua "
                 "napsauttamalla näet sen maksut vuosittain ja vuoden yleisimmät syyt."),
        caveat=(f"{left} % of a year's fines have no address, or one on a street that is not among the city's street areas "
                "(a square, a park, a private lane), and are left out; so are the 2023 fines the register marks as not at "
                "their real place. A street's length is that of its street areas, which may run past the kerb into a "
                "square or a crossing."),
        caveat_fi=(f"Vuoden maksuista {left} % on vailla osoitetta tai kirjattu kadulle, joka ei ole kaupungin katualueissa "
                   "(tori, puisto, yksityinen kuja), ja ne on jätetty pois, samoin vuoden 2023 maksut, joiden sijainti ei "
                   "rekisterin mukaan ole todellinen. Kadun pituus on sen katualueiden pituus, johon voi kuulua osa aukiota "
                   "tai risteystä."),
        kinds=[dict(id="streets", label="Streets", label_fi="Kadut", color="#191e6a", menu=False, list=False, source=FINES, sites=[])])


def main():
    eras = [art(), trams(), mv_photos(), fines()]
    (OUT / "other.json").write_text(json.dumps(dict(eras=eras), ensure_ascii=False, separators=(",", ":")))
    for e in eras:
        print(e["id"], {k["id"]: len(k["sites"]) for k in e["kinds"]})


if __name__ == "__main__":
    main()
