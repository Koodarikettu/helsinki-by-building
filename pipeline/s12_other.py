"""The Other menu: views laid on the ground as the War view is (web/app.js reads both files alike).

- Public art: every work of the city's public art in the Service Map (HAM's texts CC BY 4.0, its photos not open), as a
  dot coloured by the period of its year, with the periods of the buildings.
- Trams: Helsinki's tram tracks through time from OpenHistoricalMap (CC0), each with the years it opened and closed;
  the map shows the network of the timeline's year and greys the tracks closed before it (trams.bin).
- Railways and metro: the same from OpenHistoricalMap's rail and metro tracks, cut to the city (rail.bin), and
  Wikidata's stations in the city as dots from the year of their official opening.
- The Finnish Heritage Agency's photos of Helsinki in Finna (CC BY 4.0), each at the place it names, the most exact
  that can be found: an address; a building that Wikidata names ("Säätytalo"); a square, park, island or street in
  the city's place-name register ("Senaatintori Helsinki"); or a point Finna gives other than the city's centre. A
  photo naming only the city or a district is left out: it would pile up on the district's middle. One dot per place.
- The Helsinki City Museum's photos in Finna (PDM, CC BY 4.0) the same way; some 9,000 places, which the page loads
  when the view opens (hkmphotos/places.json).
- Veterans' terraced houses and blocks of flats: the blocks of the companies Helsinki's municipal reports of 1950–1959
  name under the land acquisition act, two later veterans' blocks, and the terraced houses on Lauttasaari's veterans'
  plots.
- Parking fines: the city's parking fines and notices of 2014–2023 (Pysäköintivirheet Helsingissä, CC BY 4.0), by the
  street of their address, for the streets of the street-name view to be coloured by them year by year.

Writes web/data/other.json, web/data/fines.json (the parking fines by street and year), web/data/trams.bin and
web/data/rail.bin:
  u32 nLines, u32 nVerts, u32 start[nLines + 1], i16 opened[nLines], i16 closed[nLines] (0: never, or not known),
  u8 kind[nLines] (its colour in the view's legend; padded to 4), f32 xz[2 * nVerts] (local frame).
"""
import csv
import json
import re
import zipfile
import zlib
from collections import Counter
from functools import cache
from pathlib import Path
from urllib.parse import quote

import geopandas as gpd

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from .periods import PERIODS, period_index
from .s03_tiles import to_local
from .s08_archive import ADDRESS, OPEN, keys_of, person
from .s08_archive import OUT as ARCHIVE, SHARDS as ARCHIVE_SHARDS
from .s11_war import ART, at, clean, shorten

RAW, OUT = Path("data/raw"), Path("web/data")
TRAM_COLORS = ("#0f8a4f", "#b9bfc2")  # in use in the timeline's year; closed by then
MV = dict(label="Finnish Heritage Agency, photos in Finna", label_fi="Museovirasto, kuvat Finnassa", url="https://www.finna.fi",
          licence="CC BY 4.0")
HKM = dict(label="Helsinki City Museum, photos in Finna", label_fi="Helsingin kaupunginmuseo, kuvat Finnassa",
           url="https://www.finna.fi", licence="PDM, CC BY 4.0")
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
# The railways in HSL's colour of the commuter trains, the metro in its own orange; closed by then, as the trams'
RAIL_COLORS = ("#8c4799", "#ff6319", "#b9bfc2")
OHM_RAIL = dict(label="OpenHistoricalMap, Helsinki's railways and metro", label_fi="OpenHistoricalMap, Helsingin rautatiet ja metro",
                url="https://www.openhistoricalmap.org/", licence="CC0")
WD_STATIONS = dict(label="Wikidata, stations and their opening dates", label_fi="Wikidata, asemat ja niiden avauspäivät",
                   url="https://www.wikidata.org/", licence="CC0")
METRO_STATION = "http://www.wikidata.org/entity/Q928830"


def stations(city) -> tuple:
    """Wikidata's railway and metro stations in the city, each from the year of its official opening, oldest first. One
    with no opening date cannot be placed in time (the Malmi cemetery's office, Kivihaka): left out."""
    gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
    seen, out = {}, ([], [])
    with open(RAW / "wd_stations.csv", newline="") as f:
        for r in csv.DictReader(f):  # a row per class, label and point: the first of an item is kept, metro if any is
            if not r["open"][:4].isdigit():
                continue
            if r["i"] in seen:
                seen[r["i"]]["metro"] |= r["t"] == METRO_STATION
                continue
            x, y = gk25.transform(*map(float, r["coord"][len("Point("):-1].split()))
            if city.contains(shapely.Point(x, y)):
                year, fi = int(r["open"][:4]), r["fi"] or r["en"]
                seen[r["i"]] = dict(metro=r["t"] == METRO_STATION, site={"at": at(x, y), "name": r["en"] or fi, "name_fi": fi,
                                    "sub": f"Opened {year}", "sub_fi": f"Avattu {year}", "url": r["i"], "from": year})
    for s in seen.values():
        out[s["metro"]].append(s["site"])
    return tuple(sorted(k, key=lambda s: (s["from"], s["name_fi"])) for k in out)
FINES = dict(label="City of Helsinki, parking violations", label_fi="Helsingin kaupunki, pysäköintivirheet",
             url="https://hri.fi/data/en_GB/dataset/pysakointivirheet-helsingissa",
             url_fi="https://hri.fi/data/fi/dataset/pysakointivirheet-helsingissa", licence="CC BY 4.0")
# Fines on a street in a year, from this many up, and fines per 100 metres of street: the colouring's eight steps, one
# for each of the noise surveys' colours (web/app.js FINE_COLORS).
FINE_STEPS = [1, 5, 10, 25, 50, 100, 250, 500]
FINE_DENSE = [0, 1, 2, 5, 10, 25, 50, 100]


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


def ohm_ways(name: str) -> list:
    """OpenHistoricalMap's ways in GK25: [(coordinates (n, 2), opened, closed or 0, tags)]. A way with no opening year
    cannot be placed in time (two short tram stretches in Kallio and Munkkiniemi): left out."""
    gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
    year = lambda s: int(s[:4]) if s and s[:4].isdigit() else 0
    return [(np.array(gk25.transform([p["lon"] for p in w["geometry"]], [p["lat"] for p in w["geometry"]])).T,
             year(w["tags"].get("start_date")), year(w["tags"].get("end_date")), w["tags"])
            for w in json.loads((RAW / name).read_text())["elements"] if year(w["tags"].get("start_date"))]


def write_tracks(path: Path, lines: list):
    """[(coordinates in GK25, opened, closed, kind)] → a tracks file (above); their opened, closed, kind and km."""
    opened, closed = (np.array([l[k] for l in lines], "<i2") for k in (1, 2))
    kind = np.array([l[3] for l in lines], "u1")
    start = np.cumsum([0] + [len(l[0]) for l in lines]).astype("<u4")
    xz = to_local(np.concatenate([l[0] for l in lines])).astype("<f4")
    path.write_bytes(np.array([len(lines), len(xz)], "<u4").tobytes() + start.tobytes() + opened.tobytes() +
                             closed.tobytes() + kind.tobytes() + bytes(-len(kind) % 4) + xz.tobytes())
    return opened, closed, kind, np.array([np.hypot(*np.diff(l[0], axis=0).T).sum() for l in lines]) / 1000


def trams() -> dict:
    opened, closed, _, length = write_tracks(OUT / "trams.bin", [(c, o, x, 0) for c, o, x, _ in ohm_ways("ohm_trams.json")])
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


def rail() -> dict:
    # Cut to the city, land and water: the main line runs on to Riihimäki, the metro to Espoo, the ring rail in Vantaa.
    city = shapely.union_all([g for n in ("manner", "saaret", "merialue", "muut_vesialueet")
                              for g in gpd.read_file(RAW / f"Maavesi_{n}.geojson").geometry])
    lines = []
    for c, o, x, tags in ohm_ways("ohm_rail.json"):
        cut = shapely.LineString(c).intersection(city)
        lines += [(np.asarray(g.coords)[:, :2], o, x, int(tags["railway"] == "subway"))
                  for g in getattr(cut, "geoms", [cut]) if g.geom_type == "LineString" and not g.is_empty]
    opened, closed, kind, length = write_tracks(OUT / "rail.bin", lines)
    first, metro = int(opened.min()), int(opened[kind == 1].min())
    railway_stations, metro_stations = stations(city)
    return dict(
        id="rail", menu="other", label="Railways and metro", label_fi="Rautatiet ja metro", years=f"{first}–", years_fi=f"{first}–",
        text=("Helsinki's railways and metro through time as OpenHistoricalMap draws them within the city: the map shows "
              "the tracks in use in the timeline's year, the railways in purple and the metro in orange, and greys those "
              f"closed before it ({length[closed > 0].sum():.0f} km in all, the harbour railways and factory sidings among "
              f"them). The main line came in {first}, the metro in {metro}. The dots are the stations, each from the "
              "year Wikidata gives for its opening. Drag the timeline or play it to watch the network grow."),
        text_fi=("Helsingin rautatiet ja metro ajan mukana OpenHistoricalMapin mukaan kaupungin rajojen sisällä: kartta "
                 "näyttää aikajanan vuonna käytössä olevat radat, rautatiet violettina ja metron oranssina, ja harmaana "
                 f"sitä ennen lakkautetut (kaikkiaan {length[closed > 0].sum():.0f} km, muun muassa satamaradat ja tehtaiden "
                 f"pistoraiteet). Päärata valmistui {first}, metro {metro}. Pisteet ovat asemat, kukin siitä vuodesta, jona "
                 "se Wikidatan mukaan avattiin. Vedä aikajanaa tai toista se, niin näet verkon kasvavan."),
        caveat=("OpenHistoricalMap is drawn by volunteers: a track's years may be rounded, and some tracks are missing, "
                "such as the Vuosaari harbour railway of 2008 (its station is there). A double track is sometimes one "
                "line, sometimes two. Wikidata has no item for Tapulikaupunki's station and no stations closed since; "
                "a station keeps its name of today."),
        caveat_fi=("OpenHistoricalMapia piirtävät vapaaehtoiset: radan vuodet voivat olla pyöristettyjä, ja ratoja puuttuu, "
                   "esimerkiksi Vuosaaren satamarata vuodelta 2008 (sen asema on mukana). Kaksoisraide on joskus yksi viiva, "
                   "joskus kaksi. Wikidatassa ei ole Tapulikaupungin asemaa eikä sittemmin lakkautettuja asemia, ja asema on "
                   "nykyisellä nimellään."),
        tracks="rail.bin", linesTitle="Tracks", linesTitle_fi="Radat",
        legend=[dict(color=RAIL_COLORS[0], label="Railway in use in the timeline's year", label_fi="Rautatie käytössä aikajanan vuonna"),
                dict(color=RAIL_COLORS[1], label="Metro in use in the timeline's year", label_fi="Metro käytössä aikajanan vuonna"),
                dict(color=RAIL_COLORS[2], label="Closed before it", label_fi="Lakkautettu sitä ennen")],
        kinds=[dict(id="tracks", label="Railways and metro", label_fi="Rautatiet ja metro", color=RAIL_COLORS[0], menu=False,
                    list=False, source=OHM_RAIL, sites=[]),
               dict(id="stations", label="Railway stations", label_fi="Rautatieasemat", color=RAIL_COLORS[0], menu=False,
                    list=True, source=WD_STATIONS, sites=railway_stations),
               dict(id="metro", label="Metro stations", label_fi="Metroasemat", color=RAIL_COLORS[1], menu=False,
                    list=True, source=WD_STATIONS, sites=metro_stations)])


def place_of(r: dict, addr: dict, named: dict, spot: dict, gk25=None, box=None, areas=frozenset()):
    """(name, x, y) of the most exact place a Finna record names, or None: an address, a building by name, a spot in
    the place-name register (each looked up from the last, most exact, part of a Helsinki place), else Finna's own
    point, for a name that is no area (`areas`: the register's districts)."""
    for p in r.get("subjectPlaces") or []:
        # the City Museum ends a place with its addresses, each closed by a full stop: "Pyöräilystadion. Mäkelänkatu 70."
        parts = [y for x in p.split(",") for y in re.split(r"\.(?:\s+|$)", x.strip()) if y]
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


def en(n: int) -> str:
    return f"{n:,}"


def fi(n: int) -> str:
    return f"{n:,}".replace(",", " ")


@cache
def lookups() -> tuple:
    """What place_of looks a place up in: the address points, the buildings Wikidata names, the place-name register's
    spots, and for Finna's own points the transform, the city's box and the districts."""
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
    for k, v in list(addr.items()):  # a divided plot has only 12a and 12b, and a photo names "Uudisraivaajantie 12"
        addr.setdefault(re.sub(r"(?<=\d)[a-zåäö]$", "", k), v)
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "gone", "geometry"])
    centre = dict(zip(b.key, b.geometry.representative_point()))
    named = {}
    for r in csv.DictReader(open(RAW / "wd_buildings.csv")):
        if r["prt"] in centre and r["labelFi"]:
            named.setdefault(r["labelFi"].lower(), centre[r["prt"]])
    gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
    return addr, named, spot, gk25, (gk25.transform(24.78, 60.09), gk25.transform(25.27, 60.33)), areas


def photo_places(raw: str, licences: set, folder: str, shards: int, museum: str, credit=None, role=None) -> tuple:
    """A museum's photos in Finna, one dot per place they name (place_of): the places, each with its first photo, the
    photos placed and the records read. All of a place's photos, oldest first, go to one of `shards` files
    web/data/<folder>/<nn>.json, keyed by a CRC-32 of its name, which the page loads when its card opens. `credit` names
    the museum and the collection on each photo (the card's default is the City Museum), `role` the photographer's role
    in the record (else the first name there is)."""
    places, seen = {}, 0
    for line in open(RAW / raw):
        r = json.loads(line)
        lic = r.get("imageRights", {}).get("copyright")
        if not r.get("images") or lic not in licences:
            continue
        seen += 1
        p = place_of(r, *lookups())
        if not p:
            continue
        year = int(m[0]) if (m := re.search(r"\d{4}", str(r.get("year") or ""))) else None
        if year and year < 1839:  # before photography: the year of what it shows ("Helsingin tuomiokirkko, 1830")
            year = None
        maker = next((person(a["name"]) for a in r.get("nonPresenterAuthors") or []
                      if a.get("name") and (role is None or a.get("role") == role)), None)
        coll = next((b["translated"] for b in r.get("buildings") or [] if b["value"].startswith("1/")), None)
        site = places.setdefault(p[0], dict(at=at(p[1], p[2]), name=p[0], photos=[]))
        site["photos"].append({k: v for k, v in dict(r=r["id"], y=year, t=clean(r.get("title")), m=maker, l=lic,
                                                      o=f"{credit}, {coll}" if credit and coll else credit).items() if v})
    sites, out = [], [{} for _ in range(shards)]
    for s in places.values():
        ph = sorted(s["photos"], key=lambda p: p.get("y") or 9999)  # oldest first, those with no year last
        n, years = len(ph), [p["y"] for p in ph if p.get("y")]
        shard = zlib.crc32(s["name"].encode()) % shards
        out[shard][s["name"]] = ph
        span = f"{years[0]}–{years[-1]}" if years and years[0] != years[-1] else str(years[0]) if years else ""
        sites.append(dict(at=s["at"], name=s["name"], photos=ph[:1], shard=shard, n=n,
                          sub=" · ".join(filter(None, [span, f"{n} photo{'s' if n > 1 else ''}"])),
                          sub_fi=" · ".join(filter(None, [span, f"{n} kuva{'a' if n > 1 else ''}"])),
                          url=f"https://www.finna.fi/Search/Results?lookfor={quote(s['name'])}&filter%5B%5D=building%3A%220%2F{museum}%2F%22"))
    sites.sort(key=lambda s: (-s["n"], s["name"]))  # the most photographed first
    (OUT / folder).mkdir(exist_ok=True)
    for i, sh in enumerate(out):
        (OUT / folder / f"{i:02d}.json").write_text(json.dumps(sh, ensure_ascii=False, separators=(",", ":")))
    return sites, sum(s.pop("n") for s in sites), seen


def mv_photos() -> dict:
    """The Heritage Agency's photos, one dot per place they name."""
    sites, total, _ = photo_places("finna_mv.jsonl", {"CC BY 4.0"}, "mvphotos", 32, "Museovirasto", credit="Museovirasto")
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


def hkm_photos() -> dict:
    """The City Museum's photos the same way. Their 9,000 places would add megabytes to the page's start: they come in
    a file of their own (`file`) when the view first opens."""
    sites, total, seen = photo_places("finna_hkm.jsonl", OPEN, "hkmphotos", 128, "HKM", role="valokuvaaja")
    (OUT / "hkmphotos" / "places.json").write_text(json.dumps(sites, ensure_ascii=False, separators=(",", ":")))
    first = min(s["photos"][0]["y"] for s in sites if s["photos"][0].get("y")) // 10 * 10
    return dict(
        id="hkmphotos", menu="other", label="City Museum photos", label_fi="Kaupunginmuseon kuvat", years=f"{first}s–today",
        years_fi=f"{first}-luvulta tähän päivään",
        text=(f"{en(total)} photos from the Helsinki City Museum's collections, at {en(len(sites))} places they name: an "
              "address, a building, a square, park, island or street. A card shows all of a place's photos, oldest first, "
              "with a button for each decade where there are many."),
        text_fi=(f"{fi(total)} Helsingin kaupunginmuseon kokoelmien kuvaa {fi(len(sites))} paikassa, jotka kuvat nimeävät: "
                 "osoite, rakennus, tori, puisto, saari tai katu. Kortti näyttää paikan kaikki kuvat vanhimmasta alkaen, ja "
                 "kun niitä on paljon, jokaiselle vuosikymmenelle on oma painikkeensa."),
        caveat=(f"Of the museum's {en(seen)} openly licensed images, {en(seen - total)} name only the city or a district, or "
                "a place that cannot be found, and are left out. A photo stands at the place it names, which may be what it "
                "shows rather than where it was taken from; an interior stands at its building's address."),
        caveat_fi=(f"Kaupunginmuseon {fi(seen)} avoimesti lisensoidusta kuvasta {fi(seen - total)} nimeää vain kaupungin tai "
                   "kaupunginosan tai paikan, jota ei löydy, ja ne on jätetty pois. Kuva on nimeämässään paikassa, joka voi "
                   "olla kuvan kohde eikä kuvauspaikka; sisäkuva on rakennuksensa osoitteessa."),
        kinds=[dict(id="hkm", label="Places with photos", label_fi="Kuvauspaikat", color="#2a78d6", menu=False, list=True,
                    source=HKM, sites=[], file="hkmphotos/places.json", shards="hkmphotos")])


# Veterans' blocks of flats (rintamamieskerrostalot). The land acquisition act of 1945 gave plots to veterans, the
# families of the fallen and evacuees; its § 157 a (1949) let housing companies whose shareholders would have had a
# right to such a plot build a block of flats instead, 27 in Helsinki. Helsinki's municipal reports name them: the
# companies of the city's own programme of 1951–1958 in a table of 1958, and the plots leased to the others. Each
# company with the register addresses of its buildings: the company's own name where it is an address; else the plot
# the reports lease to it, as the register numbers it (Majavakulma: Herttoniemi's block 135, plots 3–5; Kannelmäki:
# block 33121 plot 3 and block 33126 plot 3; Tilkanrinne: block 721 plot 2; Maunulanmäki: block 28220, whose three
# blocks of 1960 stand on one plot now; the 1950 company on block 135 plot 2); else the address another source gives
# (Portimola: Länsi-Herttoniemi's home-town trail; Jussinkulma and Pitkäjussi: the City Museum's Pohjois-Haaga
# inventory, whose Pastori Jussilaisen tie 10 and 12 are Ohjaajantie 3 today, by its coordinates).
# The trails of Haaga and Länsi-Herttoniemi name Santavuorentie 8 and Majavatie 7 too: the reports' company of
# Santavuorentie 4-6-7 stands on the plots of 4, 6 and 7, and no company of the reports on Majavatie 7's; left out.
REPORT = "Kertomus Helsingin kaupungin kunnallishallinnosta"
REPORTS = {  # (year, part): the City Archives' PDF; its printed page is the PDF's less four
    (1950, 2): "https://yksa.disec.fi/Yksa4/download/141570672329500/file/5a7eb072-4d72-47c4-a0a2-c7f05257927a",
    (1954, 1): "https://yksa.disec.fi/Yksa4/download/141570680763100/file/efe6056e-cfaf-49c6-92fd-dbf2870196cc",
    (1958, 1): "https://yksa.disec.fi/Yksa4/download/141570689944000/file/7db948d5-cccf-4e48-b0c0-0cf076539f82",
    (1958, 2): "https://yksa.disec.fi/Yksa4/download/141570691149900/file/77c42e56-00ae-4e3a-a37e-23efe44e6173",
    (1959, 1): "https://yksa.disec.fi/Yksa4/download/141570692405800/file/553f4a88-e0c1-4da4-aa5b-a8c812713706",
}
TABLE = "Helsingin kaupungin lainoituksen tuella tapahtunut maanhankintalain mukainen kerrostalorakennustoiminta"
# The table of 1958 (part 2, PDF page 220): programme, company, buildings and flats as it gives them, and the addresses
PROGRAMME = [
    ("1951/52", "Mannerheimintie 71", 1, 56, ["Mannerheimintie 71"]),
    ("1951/52", "Mäyrätie 7", 1, 20, ["Mäyrätie 7"]),
    ("1951/52", "Santavuorentie 3-5", 2, 76, ["Santavuorentie 3", "Santavuorentie 5"]),
    ("1952/53", "Santavuorentie 4-6-7", 3, 62, ["Santavuorentie 4", "Santavuorentie 6", "Santavuorentie 7"]),
    ("1952/53", "Poutuntie 6 ja 8", 2, 54, ["Poutuntie 6", "Poutuntie 8"]),
    ("1952/53", "Majavakulma", 3, 60, ["Majavatie 8", "Hiihtomäentie 30", "Hiihtomäentie 32"]),
    ("1953/54", "Jussinkulma", 2, 65, ["Pastori Jussilaisen tie 4", "Näyttelijäntie 3"]),
    ("1953/54", "Portimola", 4, 80, ["Portimopolku 6", "Portimopolku 8", "Portimopolku 10", "Portimopolku 12"]),
    ("1953/54", "Poutuntie 4 ja 10", 2, 36, ["Poutuntie 4", "Poutuntie 10"]),
    ("1954/55", "Pitkäjussi", 3, 96, ["Pastori Jussilaisen tie 6", "Pastori Jussilaisen tie 8", "Ohjaajantie 3"]),
    ("1954/55", "Kivalterintie 18-20", 1, 90, ["Kivalterintie 20"]),
    ("1954/55", "Roihuvuorentie 5-7", 2, 48, ["Roihuvuorentie 5", "Roihuvuorentie 7"]),
    ("1955/56", "Roihuvuorentalo 9", 1, 18, ["Roihuvuorentie 9"]),
    ("1955/56", "Näyttelijäntie 5-7", 1, 45, ["Näyttelijäntie 5-7"]),
    ("1955/56", "Hiihtomäentie 16", 1, 50, ["Hiihtomäentie 16"]),
    ("1955/56", "Kivalterintie 17-19", 2, 120, ["Kivalterintie 17-19"]),
    ("1955/56", "Prinssintie 4", 1, 60, ["Prinssintie 4"]),
    ("1955/56", "Lumikintie 7", 1, 64, ["Lumikintie 7"]),
    ("1956/57", "Ulvilantie 27", 6, 235, ["Ulvilantie 27"]),
    ("1956/57", "Pikalähetintie 14-18", 2, 120, ["Pikalähetintie 14", "Pikalähetintie 18"]),
    ("1957/58", "Pajamäentie 1, 3 ja 5", 3, 108, ["Pajamäentie 1", "Pajamäentie 3", "Pajamäentie 5"]),
    ("1957/58", "Isonnevantie 10-12-14", 3, 36, ["Isonnevantie 10", "Isonnevantie 12", "Isonnevantie 14"]),
    ("1957/58", "Kannelmäki", 7, 181, ["Kanneltie 10", "Kanneltie 7"]),
]
# The reports' other companies of § 157 a, and the plot leased to Helsinki's veterans' land association: (company,
# addresses, (year, part, PDF page), the report's words). And two later veterans' blocks: (company, addresses, source)
OTHERS = [
    ("Aleksis Kiven katu 4–8", ["Aleksis Kiven katu 4-8"], (1950, 2, 46),
     "Rakennusliike oy. Puomi ab:n toimesta perustettavalle maanhankintalain 157a §:n mukaiselle asunto-osakeyhtiölle "
     "päätettiin vuokrata Aleksis Kiven kadun varrelta korttelin n:o 359 tontit n:o 4, 6 ja 8 toukokuun 1 p:stä 1950 "
     "joulukuun 31 p:ään 2010 …"),
    ("Herttoniemi, kortteli 135, tontti 2", ["Mäyrätie 9"], (1950, 2, 46),
     "Lautakunta päätti vuokrata arkkitehti T. Aspialan toimesta perustettavalle maanhankintalain 157 a §:ssä "
     "tarkoitetulle asunto-osakeyhtiölle Herttoniemen asuntoalueelta korttelista n:o 135 tontin n:o 2 …"),
    ("Tilkanrinne", ["Koroistentie 8"], (1954, 1, 91),
     "… korttelin n:o 721 tontin n:o 2 Koroistentien varrella … 1) perustettavan asunto-osakeyhtiön osakkaiden tulee olla "
     "Helsingin kaupungissa maansaantiin oikeutettuja ja tulee heidän asunto-osakkeen saadessaan luopua "
     "maansaantioikeudestaan tai maanhankintalain nojalla heille jo luovutetusta maasta …"),
    ("Maunulanmäki", ["Lampuotilantie 34", "Lampuotilantie 36"], (1959, 1, 93),
     "Kiinteistölautakunnalle myönnettiin oikeus vuokrata perustettavalle Asunto Oy. Maunulanmäki -nimiselle yhtiölle "
     "28. kaupunginosan korttelin n:o 28220 tontit n:o 1 ja 2 …"),
    ("Helsingin Rintamamiesten Maanhankintayhdistys", ["Soittajantie 3"], (1958, 1, 278),
     "Kiinteistölautakuntaa kehotettiin vuokraamaan kaupunginvaltuuston vahvistamilla vuokraehdoilla Helsingin "
     "Rintamamiesten Maanhankintayhdistykselle korttelin n:o 33121 tontti n:o 2 …"),
]
LATER = [
    ("Asunto Oy RM-talo 62", ["Suursuontie 10"], dict(label="Maunulan kotikaupunkipolku: punainen reitti",
                                           url="https://kaupunginosat.fi/maunula/kotiseutu/kotikaupunkipolku/punainen-reitti/"),
     "Talo oli alun perin Rintamamiesten kerrostalo ja sinne sai muuttaa ainoastaan sotaveteraaneja tai heidän leskiään."),
    ("RM-talot Klaavuntiellä", ["Klaavuntie 5"], dict(label="Helsingin kaupunginmuseo: Puotilan rakennusinventointi",
                                       url="https://www.hel.fi/static/hkm/pdf/Puotila.pdf"),
     "… esimerkiksi RM-talot Klaavuntiellä … (Rintamamiesten yhdistyksen asuntoyhdistys, Klaavuntie 5.)"),
]
INVENTORY = dict(label="Helsinki City Museum, building inventory of Lauttasaari (2001–2002)",
                 label_fi="Helsingin kaupunginmuseo, Lauttasaaren rakennusinventointi (2001–2002)",
                 url="https://hri.fi/data/fi/dataset/helsinkilaisten-rakennusten-historiatietoja", licence="CC BY 4.0")
HS_2010 = dict(label="Helsingin Sanomat 2010: Rintamamiehet tulivat kuin paratiisiin (Finna)",
               url="https://www.finna.fi/Record/arto.013512187")
VETERAN_COLORS = ("#e34948", "#2a78d6")  # blocks of flats, terraced houses


def report(year: int, part: int, page: int) -> dict:
    return dict(label=f"Helsinki's municipal report of {year}, part {'I' if part == 1 else 'II'}, p. {page - 4}",
                label_fi=f"{REPORT} {year}, {'I' if part == 1 else 'II'}, s. {page - 4}",
                url=f"{REPORTS[year, part]}#page={page}")


def veteran_blocks(b) -> list:
    """A dot on each building whose register address is one of a company's, a staircase's letter aside (the three of
    Kivalterintie 17-19a, 17-19b and 17-19c), and built by 1964 (not Isonnevantie 14c of 2017), with the company, the
    source's words and the City Museum's photos of the building that its card shows (s08_archive); and the number of
    buildings of the companies of § 157 a."""
    b = b[b.gone == 0]
    own = {}
    for r in b[b.katunimi_suomi.notna()].itertuples():
        own.setdefault(f"{r.katunimi_suomi} {re.sub(r'[a-zåäö]$', '', str(r.osoitenumero))}".lower(), []).append(r)
    photos = lambda k: json.loads((ARCHIVE / f"{zlib.crc32(k.encode()) % ARCHIVE_SHARDS:02d}.json").read_text()).get(k)
    table = report(1958, 2, 220)
    law = [(f"Asunto Oy {name}", addrs, table, f"{TABLE}: {years} {name}, {n} talo{'a' if n > 1 else ''}, {flats} asuntoa.")
           for years, name, n, flats, addrs in PROGRAMME]
    law += [(name if name.startswith("Herttoniemi") else f"Asunto Oy {name}", addrs, report(*at_page), words)
            for name, addrs, at_page, words in OTHERS[:-1]]
    association = [(OTHERS[-1][0], OTHERS[-1][1], report(*OTHERS[-1][2]), OTHERS[-1][3])]
    sites, n_law = {}, 0
    for i, (company, addrs, source, words) in enumerate(law + association + LATER):
        for a in addrs:
            found = [r for r in own.get(a.lower(), []) if r.year < 1965]
            if not found:
                print("veterans' block not found:", a)
            n_law += len(found) if i < len(law) else 0
            for r in found:
                sites.setdefault(r.key, dict(
                    at=at(*r.geometry.representative_point().coords[0]), name=f"{r.katunimi_suomi} {r.osoitenumero}".replace("-", "–"),
                    sub=f"{company} · completed {r.year}", sub_fi=f"{company} · valmistunut {r.year}", text=words,
                    source=source, year=int(r.year), **({"photos": ph} if (ph := photos(r.key)) else {})))
    return sorted(sites.values(), key=lambda s: s["name"]), n_law


def veteran_rows() -> list:
    """The terraced houses the City Museum's inventory of Lauttasaari puts on a veterans' plot, which the Tallberg estate
    sold to veterans in 1948, with its words and the year it gives for the building's first use."""
    with zipfile.ZipFile(RAW / "hkm_inventoinnit.zip") as z:
        inv = pd.read_excel(z.open(next(n for n in z.namelist() if n.endswith(".xlsx"))), sheet_name="Lauttasaari")
    inv = inv[inv.Erityispiirteet.str.contains("rintamamiestontti", na=False) & (inv.Alkup_kaytto == "rivitalot")]
    out = []
    for r in inv.itertuples():
        words = clean(r.Erityispiirteet.replace("_x000D_", " "))
        out.append(dict(at=at(r.ikooETRSGK25, r.pkooETRSGK25), name=clean(r.Katuosoite), year=int(r.Kayttottovuosi),
                        sub=f"{clean(r.Nimi)} · terraced house on a veterans' plot, in use from {r.Kayttottovuosi}",
                        sub_fi=f"{clean(r.Nimi)} · rivitalo rintamamiestontilla, käytössä vuodesta {r.Kayttottovuosi}",
                        text=words[words.index("Tontti on ns."):], source=INVENTORY))
    return sorted(out, key=lambda s: s["name"])


def veterans() -> dict:
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "year", "gone", "katunimi_suomi", "osoitenumero", "geometry"])
    (blocks, n_law), rows = veteran_blocks(b), veteran_rows()
    years = [s.pop("year") for s in blocks + rows]
    n_photos = sum(len(s.get("photos", [])) for s in blocks)
    n_companies = len(PROGRAMME) + len(OTHERS) - 1  # the association's plot is no company of § 157 a
    return dict(
        id="veterans", menu="other", label="Veterans' terraced houses and blocks of flats",
        label_fi="Rintamamiesrivi- ja kerrostalot", years=f"{min(years)}–{max(years)}", years_fi=f"{min(years)}–{max(years)}",
        text=("After the Continuation War the land acquisition act of 1945 gave plots to veterans, the families of the "
              "fallen and evacuees. A law of 1949 let a housing company whose shareholders would have had a right to such "
              "a plot build a block of flats instead. Helsinki's municipal reports of 1950–1959 name "
              f"{n_companies} such companies, and the map shows their {n_law} buildings, each with the report's "
              "words; a plot the city leased to Helsinki's veterans' land association; and two later veterans' blocks, "
              "RM-talot, that local sources name. The terraced houses are those the City Museum's inventory of "
              "Lauttasaari puts on the veterans' plots sold there in 1948, built later. A card shows the City Museum's "
              f"photos of the building where it has any ({n_photos} in all)."),
        text_fi=("Jatkosodan jälkeen vuoden 1945 maanhankintalaki antoi tontteja rintamamiehille, kaatuneiden omaisille ja "
                 "evakoille. Vuoden 1949 laki salli asunto-osakeyhtiön, jonka osakkailla olisi ollut oikeus "
                 "rintamamiestonttiin, rakentaa sen sijaan kerrostalon. Helsingin kunnalliskertomukset vuosilta "
                 f"1950–1959 nimeävät {n_companies} tällaista yhtiötä, ja kartalla ovat niiden {n_law} "
                 "rakennusta, kukin kertomuksen omin sanoin, tontti, jonka kaupunki vuokrasi Helsingin Rintamamiesten "
                 "Maanhankintayhdistykselle, sekä kaksi myöhempää rintamamiesten kerrostaloa, RM-taloa, jotka "
                 "paikalliset lähteet nimeävät. Rivitalot ovat ne, jotka kaupunginmuseon Lauttasaaren inventointi "
                 "sijoittaa vuonna 1948 myydyille rintamamiestonteille ja jotka on rakennettu myöhemmin. Kortti näyttää "
                 f"kaupunginmuseon kuvat rakennuksesta, jos niitä on (yhteensä {n_photos})."),
        caveat=("The reports count buildings otherwise than the register now does (Pitkäjussi: three in the report, five "
                "in the register), and Helsingin Sanomat counted 63 veterans' blocks in Helsinki in 2010. Later veterans' "
                "companies' blocks (RM-talot) are named in few open sources, and Olavi Haimi's study of 2010, Rintamamiehet "
                "rakentajina Helsingissä, is not online: some may be missing. The terraced houses of Lauttasaari were built "
                "in 1968–2001 on plots sold to veterans in 1948, not for veterans."),
        caveat_fi=("Kertomukset laskevat rakennukset toisin kuin rekisteri nyt (Pitkäjussi: kertomuksessa kolme, "
                   "rekisterissä viisi), ja Helsingin Sanomien mukaan rintamamieskerrostaloja oli Helsingissä vuonna 2010 "
                   "63. Myöhempien rintamamiesten yhtiöiden taloja (RM-taloja) nimeävät harvat avoimet lähteet, eikä Olavi "
                   "Haimin tutkimus Rintamamiehet rakentajina Helsingissä (2010) ole verkossa: joitain voi puuttua. "
                   "Lauttasaaren rivitalot on rakennettu 1968–2001 vuonna 1948 rintamamiehille myydyille tonteille, ei "
                   "rintamamiehille."),
        sources=[report(1958, 2, 220), HS_2010, *(x[2] for x in LATER), INVENTORY, HKM],
        kinds=[dict(id="blocks", label="Veterans' blocks of flats", label_fi="Rintamamieskerrostalot", color=VETERAN_COLORS[0],
                    menu=False, list=True, source=report(1958, 2, 220), sites=blocks),
               dict(id="rows", label="Terraced houses on veterans' plots", label_fi="Rivitalot rintamamiestonteilla",
                    color=VETERAN_COLORS[1], menu=False, list=True, source=INVENTORY, sites=rows)])


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
              "the address each was written to. A street is coloured by its fines in the year shown, in the colours of "
              "the city's noise maps, from green through yellow to red and violet, by all its fines or by its fines per 100 metres, so that a short street fined often stands out beside a "
              "long one; pick a year on the timeline. A click on a street gives its fines year by year and the year's "
              "commonest reasons."),
        text_fi=(f"Pysäköinninvalvonnan ja poliisin vuosina {span} kirjoittamat pysäköintivirhemaksut ja huomautukset sen "
                 "kadun mukaan, jonka osoitteeseen maksu kirjattiin. Katu on värjätty näytetyn vuoden maksujen mukaan "
                 "kaupungin melukarttojen värein vihreästä keltaisen kautta punaiseen ja violettiin, joko kaikkien maksujen tai 100 metriä kohden laskettujen mukaan, "
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
    eras = [art(), trams(), rail(), mv_photos(), hkm_photos(), veterans(), fines()]
    (OUT / "other.json").write_text(json.dumps(dict(eras=eras), ensure_ascii=False, separators=(",", ":")))
    for e in eras:
        print(e["id"], {k["id"]: len(k["sites"]) for k in e["kinds"]})


if __name__ == "__main__":
    main()
