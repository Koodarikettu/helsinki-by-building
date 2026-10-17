"""Download the open data into data/raw/: Helsinki's WFS layers, the heights of its 3D city model and the buildings
it records as demolished, Museovirasto's RKY areas, HSY's solar potential, the public energy certificates, Wikidata's
buildings, the Helsinki City Museum's photos in Finna, the land front of 1914–1918, Museovirasto's register of
ancient and historic remains and its protected buildings, the city's public art and its parking fines, and
OpenHistoricalMap's tram, rail and metro tracks and Wikidata's stations.

Each WFS layer comes whole in one GetFeature request (no paging); the check below fails if a server ever caps it.
Licences: see README.
"""
import csv
import json
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests

HEL = "https://kartta.hel.fi/ws/geoserver/avoindata/wfs"
MV = "https://geoserver.museovirasto.fi/geoserver/rajapinta_suojellut/wfs"
HSY = "https://kartta.hsy.fi/geoserver/wfs"
NATIONAL = {"srsName": "EPSG:3879", "bbox": "25488000,6644000,25515000,6688000,EPSG:3879"}  # Helsinki's box
MV_HELSINKI = {"srsName": "EPSG:3879", "CQL_FILTER": "kunta='Helsinki'"}  # the register names the municipality
LAYERS = [  # (server, layer, extra parameters); saved as data/raw/<layer name>.geojson
    (HEL, "avoindata:Rakennukset_alue_rekisteritiedot", {}),        # buildings, EPSG:3879
    (HEL, "avoindata:Maavesi_manner", {}), (HEL, "avoindata:Maavesi_saaret", {}),                 # land
    (HEL, "avoindata:Maavesi_merialue", {}), (HEL, "avoindata:Maavesi_muut_vesialueet", {}),     # water
    (HEL, "avoindata:Asemakaavoissa_suojellut_rakennukset_alue", {}),  # protected in local plans
    (HEL, "avoindata:YLRE_Katualue_alue", {}),                       # street areas, for street names
    (HEL, "avoindata:Osoiteluettelo_piste_rekisteritiedot", {}),     # address points, to place archive photos
    (HEL, "avoindata:Nimisto_piste_rekisteritiedot", {}),            # place names, with why each was given
    (HEL, "avoindata:Maalinnoitus_kohteet", {}),                     # the land front of 1914–1918: lines,
    (HEL, "avoindata:Maalinnoitus_yksikot", {}),                     # its structures,
    (HEL, "avoindata:Maalinnoitus_rajaukset", {}),                   # and its strongpoints' outlines
    (HEL, "avoindata:Pysakointivirheet", {}),                        # parking fines, by address and month
    (MV, "rajapinta_suojellut:muinaisjaannos_piste", MV_HELSINKI),   # ancient and historic remains
    (MV, "rajapinta_suojellut:muu_kulttuuriperintokohde_piste", MV_HELSINKI),  # other heritage sites
    (MV, "rajapinta_suojellut:rky_alue", NATIONAL),                  # RKY areas
    (MV, "rajapinta_suojellut:suojellut_rakennukset_piste", NATIONAL),  # protected by law, decree or agreement; its
                                                                     # field is Kunta, padded: s05_layers picks Helsinki
    (HSY, "ilmasto_ja_energia:rakennukset_aurinkosahkopotentiaali", NATIONAL),  # solar potential by building, 2015
]
# Public art in Helsinki, from the city's Service Map (service 767; texts CC BY 4.0, photos HAM's own): war memorials.
SERVICEMAP = "https://api.hel.fi/servicemap/v2/unit/"
# Every energy certificate in force, as Varke's register publishes them (about 110 MB); those of houses with one or
# two homes are not public.
ENERGY_CERTS = "https://www.energiatodistusrekisteri.fi/api/public/energiatodistukset/csv/energiatodistukset.csv"

# Every Wikidata item with a permanent building identifier (VTJ-PRT, P3824), in all of Finland:
# s06_wiki keeps those that match a building on the map.
WDQS = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "helsinki-by-building/0.1 (non-commercial building map)"}  # add a contact before publishing
QUERY = """
SELECT ?i ?prt ?labelFi ?labelEn ?fi ?en ?image ?inception
  (GROUP_CONCAT(DISTINCT ?archLabel; separator="|") AS ?architects)
  (GROUP_CONCAT(DISTINCT ?styleFi; separator="|") AS ?stylesFi)
  (GROUP_CONCAT(DISTINCT ?styleEn; separator="|") AS ?stylesEn)
WHERE {
  ?i wdt:P3824 ?prt .
  OPTIONAL { ?i rdfs:label ?labelFi FILTER(LANG(?labelFi) = "fi") }
  OPTIONAL { ?i rdfs:label ?labelEn FILTER(LANG(?labelEn) = "en") }
  OPTIONAL { ?fi schema:about ?i; schema:isPartOf <https://fi.wikipedia.org/> }
  OPTIONAL { ?en schema:about ?i; schema:isPartOf <https://en.wikipedia.org/> }
  OPTIONAL { ?i wdt:P18 ?image }
  OPTIONAL { ?i wdt:P571 ?inception }
  OPTIONAL { ?i wdt:P84 ?arch . ?arch rdfs:label ?archLabel FILTER(LANG(?archLabel) = "fi") }
  OPTIONAL { ?i wdt:P149 ?style .
             OPTIONAL { ?style rdfs:label ?styleFi FILTER(LANG(?styleFi) = "fi") }
             OPTIONAL { ?style rdfs:label ?styleEn FILTER(LANG(?styleEn) = "en") } }
}
GROUP BY ?i ?prt ?labelFi ?labelEn ?fi ?en ?image ?inception
"""
# The railway and metro stations in Wikidata within Helsinki's box (it takes in some of Espoo and Vantaa; s12_other
# keeps the city's), with their official opening date (P1619). None in the city carries a closing date.
STATIONS = """
SELECT ?i ?fi ?en ?t ?open ?coord WHERE {
  VALUES ?t { wd:Q55488 wd:Q928830 wd:Q55678 wd:Q18543139 }
  SERVICE wikibase:box { ?i wdt:P625 ?coord .
    bd:serviceParam wikibase:cornerSouthWest "Point(24.78 60.10)"^^geo:wktLiteral .
    bd:serviceParam wikibase:cornerNorthEast "Point(25.26 60.32)"^^geo:wktLiteral . }
  ?i wdt:P31 ?t .
  OPTIONAL { ?i wdt:P1619 ?open }
  OPTIONAL { ?i rdfs:label ?fi FILTER(LANG(?fi) = "fi") } OPTIONAL { ?i rdfs:label ?en FILTER(LANG(?en) = "en") }
}
"""


def fetch_wdqs(out: Path, query: str):
    r = requests.post(WDQS, data={"query": query}, headers={**UA, "Accept": "text/csv"}, timeout=600)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(out.stem, "rows", r.text.count("\n") - 1)


# Every image of the Helsinki City Museum in Finna (about 83,000), 100 a page; s08_archive matches them by address.
FINNA = "https://api.finna.fi/v1/search"
FINNA_PARAMS = [("filter[]", 'building:"0/HKM/"'), ("filter[]", 'format:"0/Image/"'), ("limit", 100), ("sort", "id asc")] + \
    [("field[]", f) for f in ("id", "title", "year", "images", "imageRights", "nonPresenterAuthors", "subjectPlaces", "subjects")]


# The Finnish Heritage Agency's openly licensed photos of Helsinki in Finna (about 71,000, CC BY 4.0), with the places
# they name; s12_other puts those whose place it can find on the map.
FINNA_MV_PARAMS = [("lookfor", "Helsinki"), ("filter[]", 'building:"0/Museovirasto/"'), ("filter[]", 'format:"0/Image/"'),
                   ("filter[]", 'usage_rights_str_mv:"usage_B"'), ("limit", 100), ("sort", "id asc")] + \
    [("field[]", f) for f in ("id", "title", "year", "images", "imageRights", "nonPresenterAuthors", "subjectPlaces", "geoLocations",
                              "buildings")]  # the collection, which the licence asks to credit


# The Defence Forces' photos of the Second World War (SA-kuva, the Military Museum's archive, CC BY 4.0) that name
# Helsinki, about 10,000; s11_war puts those whose title names a place it can find in the War view.
FINNA_SA_PARAMS = [("lookfor", "Helsinki"), ("filter[]", 'building:"0/SA-kuva/"'), ("filter[]", 'format:"0/Image/"'),
                   ("limit", 100), ("sort", "id asc")] + \
    [("field[]", f) for f in ("id", "title", "year", "images", "imageRights", "nonPresenterAuthors", "subjectPlaces", "subjects",
                              "geoLocations")]


def fetch_finna(out: Path, params=FINNA_PARAMS):
    first = requests.get(FINNA, params=params + [("page", 1)], headers=UA, timeout=120).json()
    pages = -(-first["resultCount"] // 100)
    with out.open("w") as f:
        for page in range(1, pages + 1):
            d = first if page == 1 else requests.get(FINNA, params=params + [("page", page)], headers=UA, timeout=120).json()
            if d.get("status") != "OK":
                raise RuntimeError(f"finna page {page}: {d}")
            for r in d.get("records", []):
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("finna records", first["resultCount"])


# The city's 3D city model, LoD2 buildings as 3D Tiles (CC BY 4.0), about 650 MB: each tile is read, reduced to
# heights and dropped. Per building: its VTJ-PRT and measured height (to the highest point) from the attribute table,
# and from the roof surfaces the 70th percentile of their height above the building's lowest point, area-weighted,
# as Amsterdam's 3D BAG does: a tower or a dome stops pulling the whole block up (station 50 m → 21 m).
CITY_MODEL = "https://kartta.hel.fi/3d/datasource-data/16fc3fd5-df6d-4f48-bfd5-9aeee430a02f/"
GLTF_TYPES = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}


def read_b3dm(b: bytes):
    """b3dm → (feature table, batch table, glTF, accessor(i) → numpy array)."""
    _, _, _, ftj, ftb, btj, btb = struct.unpack("<4sIIIIII", b[:28])
    features = json.loads(b[28:28 + ftj])
    o = 28 + ftj + ftb
    table = json.loads(b[o:o + btj])
    glb = b[o + btj + btb:]
    jl = struct.unpack("<I", glb[12:16])[0]
    gltf, buf = json.loads(glb[20:20 + jl]), glb[20 + jl + 8:]

    def accessor(i):
        a = gltf["accessors"][i]
        v = gltf["bufferViews"][a["bufferView"]]
        dt, n = np.dtype(GLTF_TYPES[a["componentType"]]), {"SCALAR": 1, "VEC3": 3}[a["type"]]
        stride = v.get("byteStride") or n * dt.itemsize  # positions and normals are interleaved
        raw = np.lib.stride_tricks.as_strided(np.frombuffer(buf, np.uint8, offset=v.get("byteOffset", 0) + a.get("byteOffset", 0)),
                                              (a["count"], n * dt.itemsize), (stride, 1))
        return np.ascontiguousarray(raw).view(dt).reshape(a["count"], n).squeeze()

    return features, table, gltf, accessor


def roof_heights(b: bytes):
    """b3dm → [(VTJ-PRT, measured height, roof p70, storeys)]. glTF is y-up: y is the height in metres."""
    _, table, gltf, accessor = read_b3dm(b)
    y, area, flat, bid, ground = [], [], [], [], {}
    for prim in (p for m in gltf["meshes"] for p in m["primitives"]):
        pos, ids = accessor(prim["attributes"]["POSITION"]), accessor(prim["attributes"]["_BATCHID"]).astype(int)
        tri = accessor(prim["indices"]).astype(int).reshape(-1, 3)
        a, b_, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
        n = np.cross(b_ - a, c - a)
        ar = np.linalg.norm(n, axis=1) / 2
        y.append((a[:, 1] + b_[:, 1] + c[:, 1]) / 3); area.append(ar); bid.append(ids[tri[:, 0]])
        flat.append(np.abs(n[:, 1]) / np.maximum(2 * ar, 1e-9))
        for i in np.unique(ids):
            ground[i] = min(ground.get(i, np.inf), pos[ids == i, 1].min())
    y, area, flat, bid = map(np.concatenate, (y, area, flat, bid))
    rows = []
    for i, attr in enumerate(table["attributes"]):
        if not attr or not attr.get("VTJ_PRT") or i not in ground:
            continue
        roof = (bid == i) & (flat > 0.3) & (y > ground[i] + 1)  # roof planes, not walls or the ground floor
        p70 = None
        if roof.any():
            order = np.argsort(y[roof])
            cum = np.cumsum(area[roof][order])
            p70 = round(float(y[roof][order][np.searchsorted(cum, 0.7 * cum[-1])] - ground[i]), 1)
        rows.append((attr["VTJ_PRT"], attr.get("measuredHeight"), p70, attr.get("storeysAboveGround")))
    return rows


def tile_uris(base: str) -> list:
    tiles, stack = [], [requests.get(base + "tileset.json", headers=UA, timeout=120).json()["root"]]
    while stack:
        node = stack.pop()
        if node.get("content"):
            tiles.append(node["content"].get("uri") or node["content"]["url"])
        stack += node.get("children", [])
    return tiles


def fetch_heights(out: Path):
    tiles = tile_uris(CITY_MODEL)
    get = lambda t: roof_heights(requests.get(CITY_MODEL + t, headers=UA, timeout=300).content)
    with ThreadPoolExecutor(4) as ex:
        rows = [r for tile in ex.map(get, tiles) for r in tile]
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["vtj_prt", "measured", "roof_p70", "storeys"])
        w.writerows(rows)
    print("city model buildings with a VTJ-PRT", len(rows), "in", len(tiles), "tiles")


# The buildings the city model records as demolished, 2008 to now (LoD1, 3D Tiles, CC BY 4.0): about 4,800 in 871
# tiles, 10 MB, kept whole for s01_load. Each carries its year of demolition, and often its year of construction.
DEMOLISHED = "https://kartta.hel.fi/3d/datasource-data/9f75214e-0db3-4e7f-ad35-10509cb0d4e5/"


def fetch_demolished(out: Path):
    out.mkdir(exist_ok=True)
    get = lambda t: (out / t.replace("/", "_")).write_bytes(requests.get(DEMOLISHED + t, headers=UA, timeout=300).content)
    with ThreadPoolExecutor(8) as ex:
        n = len(list(ex.map(get, tile_uris(DEMOLISHED))))
    print("demolished buildings' tiles", n)


def fetch_wfs(out: Path, server: str, layer: str, extra: dict):
    name = layer.split(":")[1]
    r = requests.get(server, timeout=900, params=dict(service="WFS", version="2.0.0", request="GetFeature",
                                                      typeNames=layer, outputFormat="application/json", **extra))
    r.raise_for_status()
    d = r.json()  # GeoServer reports errors as XML with status 200: this raises on them
    n = len(d["features"])
    if n != d.get("numberMatched", n):
        raise RuntimeError(f"{name}: got {n} of {d['numberMatched']} features")
    (out / f"{name}.geojson").write_bytes(r.content)
    print(name, n)


# Helsinki's tram tracks, and its railways and metro, through time from OpenHistoricalMap (CC0): each way with the years
# it opened and closed. The box takes in some of Espoo and Vantaa too; s12_other cuts the railways to Helsinki.
OHM = "https://overpass-api.openhistoricalmap.org/api/interpreter"
TRAMS = '[out:json][timeout:120];way["railway"="tram"](60.10,24.78,60.32,25.26);out tags geom;'
RAIL = '[out:json][timeout:120];way["railway"~"^(rail|narrow_gauge|subway)$"](60.10,24.78,60.32,25.26);out tags geom;'


def fetch_ohm(out: Path, query: str):
    r = requests.post(OHM, data={"data": query}, headers=UA, timeout=300)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(out.stem, "ways", len(r.json()["elements"]))


# The register's own page for each defence site (other than the land front's strongpoints, which the city's survey
# draws): its dating ("toinen maailmansota 1939–1945"), the kind of defence ("I maailmansodan varustukset") and its
# description, none of which the WFS carries. s11_war sorts the sites into the two world wars by them.
REGISTER_PAGE = "https://www.kyppi.fi/to.aspx?id=112.{}"


def fetch_register(raw: Path):
    out = raw / "register"
    out.mkdir(exist_ok=True)
    sites = [f["properties"] for n in ("muinaisjaannos_piste", "muu_kulttuuriperintokohde_piste")
             for f in json.loads((raw / f"{n}.geojson").read_text())["features"]]
    ids = {p["mjtunnus"] for p in sites if "puolustus" in (p.get("tyyppi") or "")
           and not (p.get("kohdenimi") or "").strip().startswith("Tukikohta")}
    for i in sorted(ids):
        r = requests.get(REGISTER_PAGE.format(i), headers=UA, timeout=60)
        r.raise_for_status()
        (out / f"{i}.html").write_bytes(r.content)
    print("register pages", len(ids))


def fetch_public_art(out: Path):
    r = requests.get(SERVICEMAP, headers=UA, timeout=300, params=dict(
        service=767, municipality="helsinki", page_size=1000, srid=3879, geometry="true"))
    r.raise_for_status()
    d = r.json()
    if d["count"] != len(d["results"]):
        raise RuntimeError(f"public art: got {len(d['results'])} of {d['count']}")
    out.write_text(json.dumps(d["results"], ensure_ascii=False))
    print("public art", d["count"])


# The parking fines of the years before 2023, which the WFS does not serve: the city's yearly files on HRI (CC BY 4.0),
# into data/raw/fines/ for s12_other.
FINES = "https://www.hel.fi/hel2/tietokeskus/data/helsinki/hkr/"
FINE_FILES = ["Pysakointivirheet_2014-17.csv", "Pysakointivirheet_2018-.csv"] + [f"Pysakointivirheet_{y}.csv" for y in range(2019, 2023)]


def fetch_fines(out: Path):
    out.mkdir(exist_ok=True)
    for name in FINE_FILES:
        r = requests.get(FINES + name, headers=UA, timeout=600)
        r.raise_for_status()
        (out / name).write_bytes(r.content)
    print("parking fine files", len(FINE_FILES))


def main():
    out = Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    for server, layer, extra in LAYERS:
        fetch_wfs(out, server, layer, extra)
    fetch_wdqs(out / "wd_buildings.csv", QUERY)
    fetch_wdqs(out / "wd_stations.csv", STATIONS)
    (out / "energiatodistukset.csv").write_bytes(requests.get(ENERGY_CERTS, headers=UA, timeout=900).content)
    fetch_heights(out / "city_model_heights.csv")
    fetch_demolished(out / "demolished")
    fetch_finna(out / "finna_hkm.jsonl")
    fetch_finna(out / "finna_mv.jsonl", FINNA_MV_PARAMS)
    fetch_finna(out / "finna_sa.jsonl", FINNA_SA_PARAMS)
    fetch_public_art(out / "public_art.json")
    fetch_register(out)
    fetch_ohm(out / "ohm_trams.json", TRAMS)
    fetch_ohm(out / "ohm_rail.json", RAIL)
    fetch_fines(out / "fines")


if __name__ == "__main__":
    main()
