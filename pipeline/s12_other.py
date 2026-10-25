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
- Veterans' blocks of flats: those the neighbourhoods' home-town trails name, with the City Museum's photos of them that
  the building cards show.
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
import zlib
from collections import Counter
from functools import cache
from pathlib import Path
from urllib.parse import quote

import geopandas as gpd

import numpy as np
import shapely
from pyproj import Transformer

from .periods import PERIODS, period_index
from .s03_tiles import to_local
from .s08_archive import ADDRESS, OPEN, address_index, keys_of, person
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
# families of the fallen and evacuees; a law of 1949 let housing companies whose shareholders would have had a right to
# such a plot borrow to build a block of flats instead, 58 of them, 27 in Helsinki. No open list of these blocks was
# found: these are the ones the neighbourhoods' home-town trails name, each with the trail's own words:
# (trail, words, addresses).
TRAILS = {
    "alppila": ("Alppiharjun kotikaupunkipolku",
                "https://kaupunginosat.fi/alppila/wp-content/uploads/sites/9/2018/12/alppila_seura_kohteet_161218_nettiin-3.pdf"),
    "oulunkyla": ("Oulunkylän kotikaupunkipolut: Mäkitorppa",
                  "https://kaupunginosat.fi/oulunkyla/wp-content/uploads/sites/44/2020/11/makitorpan-kaupunkipolku-kartta-ja-teksti.pdf"),
    "roihuvuori": ("Roihuvuoren kotikaupunkipolut", "https://www.roihuvuori.fi/kotikaupunkipolut/"),
    "herttoniemi": ("Länsi-Herttoniemen kotikaupunkipolku",  # gone from the society's site; the Internet Archive's copy
                    "https://web.archive.org/web/20250116051439/https://kaupunginosat.fi/herttoniemi/wp-content/uploads/sites/19/2017/08/Kaupunkipolut_Lansi_Herttoniemi_Lansi-Herttoniemi.pdf"),
    "haaga": ("Haagan kotikaupunkipolut",
              "https://kaupunginosat.fi/etelahaaga/wp-content/uploads/sites/35/2013/06/tiedostot_haagan_kotikaupukipolut_vihko.pdf"),
}
OULUNKYLA = "Oulunkylässä on kuusi rintamamieskerrostaloa kaupungin vuokratonteilla."
BLOCKS = [
    ("alppila", "Itäpäädyssä kadun maamerkkinä numerossa 4–8 on massiivinen rintamamieskerrostalo vuodelta 1952.",
     ["Aleksis Kiven katu 4-8"]),
    ("oulunkyla", f'{OULUNKYLA} Kivalterintie 20 vuodelta 1955, kutsumanimeltään "Kilometritalo" on 130-metrinen rakennus, '
                  "jossa 90 asuntoa.", ["Kivalterintie 20"]),
    ("oulunkyla", f'{OULUNKYLA} … Numero 17–19 "Rintamamiestalot" (1956) käsittää 120 asuntoa kolmessa talossa.',
     ["Kivalterintie 17-19"]),
    ("oulunkyla", f'{OULUNKYLA} … Alhaalla Pikalähetintiellä numeroissa 14 ja 18 ovat "Monttutalot" (1957), joissa 120 '
                  "asuntoa kahdessa talossa.", ["Pikalähetintie 14", "Pikalähetintie 18"]),
    ("roihuvuori", "Rintamamieskerrostaloja on mm. Pohjois-Haagassa, Oulunkylässä ja Länsi-Herttoniemessä sekä "
                   "Roihuvuoressakin viisi: Lumikintie 7, Prinssintie 4 sekä Roihuvuorentie 5, 7 ja 9.",
     ["Lumikintie 7", "Prinssintie 4", "Roihuvuorentie 5", "Roihuvuorentie 7", "Roihuvuorentie 9"]),
    ("herttoniemi", "Rintamamieskerrostaloja on Herttoniemessä kahdeksan: Hiihtomäentie 16, Mäyrätie 7 ja 9, Majavatie 7 "
                    "sekä Portimopolku 6–12.",
     ["Hiihtomäentie 16", "Mäyrätie 7", "Mäyrätie 9", "Majavatie 7", "Portimopolku 6-12"]),
    ("haaga", "Ensimmäiset asuinrakennukset alueliitoksen jälkeen valmistuivat Santavuorentie 3:een ja 5:een vuonna 1952. "
              "Nämä talot ovat harvinaisia rintamamieskerrostaloja.", ["Santavuorentie 3", "Santavuorentie 5"]),
    ("haaga", "Niistä huomattava osa on Pohjois-Haagassa: Santavuorentie 4, 6 ja 8, Poutuntie 4,6 ja 8, Näyttelijäntie 3 ja "
              "5–7 sekä Pastori Jussilaisen tie 4 ja 8.",
     ["Santavuorentie 4", "Santavuorentie 6", "Santavuorentie 8", "Poutuntie 4", "Poutuntie 6", "Poutuntie 8",
      "Näyttelijäntie 3", "Näyttelijäntie 5-7", "Pastori Jussilaisen tie 4", "Pastori Jussilaisen tie 8"]),
]
TRAIL_SITE = dict(label="Helsinki's home-town trails", label_fi="Helsingin kotikaupunkipolut", url="https://www.kotikaupunkipolut.fi/")
HISTORY_AKK = dict(label="Kyllikki Torkkel: Asunto Oy Aleksis Kivenkatu 4-6-8. Puoli vuosisataa funkkistalossa Harjussa",
                   url="https://kaupunginosat.fi/alppila/wp-content/uploads/sites/9/2019/11/Historiikki_AKK468_Torkkel.pdf")
HS_2010 = dict(label="Helsingin Sanomat 2010: Rintamamiehet tulivat kuin paratiisiin (Finna)",
               url="https://www.finna.fi/Record/arto.013512187")


def veteran_blocks(b, index: dict) -> list:
    """A dot on each building whose register address is one the trails name, a staircase's letter aside (three for
    "Kivalterintie 17–19": 17-19a, 17-19b and 17-19c; four for "Portimopolku 6–12"), else on the building under its
    address point, which may stand nearer a neighbour (Lumikintie 7's), with the trail's words and the City Museum's
    photos of the building that its card shows (s08_archive)."""
    b = b[b.gone == 0]
    own = {}
    for r in b[b.katunimi_suomi.notna()].itertuples():
        own.setdefault(f"{r.katunimi_suomi} {re.sub(r'[a-zåäö]$', '', str(r.osoitenumero))}".lower(), []).append(r)
    by_key = b.set_index("key", drop=False)
    photos = lambda k: json.loads((ARCHIVE / f"{zlib.crc32(k.encode()) % ARCHIVE_SHARDS:02d}.json").read_text()).get(k)
    sites = {}
    for trail, words, addresses in BLOCKS:
        for a in addresses:
            keys = keys_of(*a.rsplit(" ", 1))
            found = own.get(a.lower()) or [r for k in keys for r in own.get(k, [])] or \
                [r for _, r in by_key.loc[[index[k] for k in keys if k in index]].iterrows()]
            if not found:
                print("veterans' block not found:", a)
            for r in found:
                name = f"{r.katunimi_suomi} {r.osoitenumero}" if isinstance(r.katunimi_suomi, str) else a
                sites.setdefault(r.key, dict(
                    at=at(*r.geometry.representative_point().coords[0]), name=name.replace("-", "–"),
                    sub=f"Completed {r.year}", sub_fi=f"Valmistunut {r.year}", text=words, year=int(r.year),
                    source=dict(label=TRAILS[trail][0], url=TRAILS[trail][1]), **({"photos": ph} if (ph := photos(r.key)) else {})))
    return sorted(sites.values(), key=lambda s: s["name"])


def veterans() -> dict:
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "year", "gone", "floors", "katunimi_suomi", "osoitenumero",
                                                            "geometry"])
    blocks = veteran_blocks(b, address_index(b))
    years = [s.pop("year") for s in blocks]
    n_photos = sum(len(s.get("photos", [])) for s in blocks)
    return dict(
        id="veterans", menu="other", label="Veterans' terraced houses and blocks of flats",
        label_fi="Rintamamiesrivi- ja kerrostalot", years=f"{min(years)}–{max(years)}", years_fi=f"{min(years)}–{max(years)}",
        text=("After the Continuation War the land acquisition act of 1945 gave plots to veterans, the families of the "
              "fallen and evacuees. A law of 1949 let a housing company whose shareholders would have had a right to such "
              "a plot build a block of flats instead: 58 companies, 27 of them in Helsinki. The map shows the "
              f"{len(blocks)} buildings of them that five neighbourhoods' home-town trails name, each with the trail's own "
              f"words, and the City Museum's photos of the building where it has any ({n_photos} in all)."),
        text_fi=("Jatkosodan jälkeen vuoden 1945 maanhankintalaki antoi tontteja rintamamiehille, kaatuneiden omaisille ja "
                 "evakoille. Vuoden 1949 laki salli asunto-osakeyhtiön, jonka osakkailla olisi ollut oikeus "
                 "rintamamiestonttiin, rakentaa sen sijaan kerrostalon: yhtiöitä perustettiin 58, joista 27 Helsinkiin. "
                 f"Kartalla ovat ne {len(blocks)} niiden rakennusta, jotka viiden kaupunginosan kotikaupunkipolut nimeävät, "
                 f"kukin polun omin sanoin, ja kaupunginmuseon kuvat rakennuksesta, jos niitä on (yhteensä {n_photos})."),
        caveat=("No open list of Helsinki's veterans' blocks was found, and the trails name only some of them: Helsingin "
                "Sanomat counted 63 such buildings in Helsinki in 2010. The history of the company at Aleksis Kiven katu "
                "4–8 says they were built in Ruskeasuo, Lauttasaari and on Mannerheimintie in Taka-Töölö too, but names "
                "no addresses, and those are not on the map."),
        caveat_fi=("Helsingin rintamamieskerrostaloista ei löytynyt avointa luetteloa, ja kotikaupunkipolut nimeävät niistä "
                   "vain osan: Helsingin Sanomien mukaan niitä oli Helsingissä vuonna 2010 63. Aleksis Kiven katu 4–8:n "
                   "taloyhtiön historiikin mukaan niitä rakennettiin myös Ruskeasuolle, Lauttasaareen ja Mannerheimintielle "
                   "Taka-Töölöön, mutta osoitteita se ei kerro, eivätkä ne ole kartalla."),
        sources=[*(dict(label=label, url=url) for label, url in TRAILS.values()), HISTORY_AKK, HS_2010, HKM],
        kinds=[dict(id="blocks", label="Veterans' terraced houses and blocks of flats", label_fi="Rintamamiesrivi- ja kerrostalot",
                    color="#e34948", menu=False, list=True, source=TRAIL_SITE, sites=blocks)])


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
