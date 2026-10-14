"""Download the open data into data/raw/: Helsinki's WFS layers, the heights of its 3D city model and the buildings
it records as demolished, Museovirasto's RKY areas, HSY's solar potential, the public energy certificates, Wikidata's
buildings and the Helsinki City Museum's photos in Finna.

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
LAYERS = [  # (server, layer, extra parameters); saved as data/raw/<layer name>.geojson
    (HEL, "avoindata:Rakennukset_alue_rekisteritiedot", {}),        # buildings, EPSG:3879
    (HEL, "avoindata:Maavesi_manner", {}), (HEL, "avoindata:Maavesi_saaret", {}),                 # land
    (HEL, "avoindata:Maavesi_merialue", {}), (HEL, "avoindata:Maavesi_muut_vesialueet", {}),     # water
    (HEL, "avoindata:Asemakaavoissa_suojellut_rakennukset_alue", {}),  # protected in local plans
    (HEL, "avoindata:YLRE_Katualue_alue", {}),                       # street areas, for street names
    (HEL, "avoindata:Osoiteluettelo_piste_rekisteritiedot", {}),     # address points, to place archive photos
    (HEL, "avoindata:Nimisto_piste_rekisteritiedot", {}),            # place names, with why each was given
    (MV, "rajapinta_suojellut:rky_alue", NATIONAL),                  # RKY areas
    (HSY, "ilmasto_ja_energia:rakennukset_aurinkosahkopotentiaali", NATIONAL),  # solar potential by building, 2015
]
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


# Every image of the Helsinki City Museum in Finna (about 83,000), 100 a page; s08_archive matches them by address.
FINNA = "https://api.finna.fi/v1/search"
FINNA_PARAMS = [("filter[]", 'building:"0/HKM/"'), ("filter[]", 'format:"0/Image/"'), ("limit", 100), ("sort", "id asc")] + \
    [("field[]", f) for f in ("id", "title", "year", "images", "imageRights", "nonPresenterAuthors", "subjectPlaces", "subjects")]


def fetch_finna(out: Path):
    first = requests.get(FINNA, params=FINNA_PARAMS + [("page", 1)], headers=UA, timeout=120).json()
    pages = -(-first["resultCount"] // 100)
    with out.open("w") as f:
        for page in range(1, pages + 1):
            d = first if page == 1 else requests.get(FINNA, params=FINNA_PARAMS + [("page", page)], headers=UA, timeout=120).json()
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


def main():
    out = Path("data/raw")
    out.mkdir(parents=True, exist_ok=True)
    for server, layer, extra in LAYERS:
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
    r = requests.post(WDQS, data={"query": QUERY}, headers={**UA, "Accept": "text/csv"}, timeout=600)
    r.raise_for_status()
    (out / "wd_buildings.csv").write_bytes(r.content)
    print("wikidata rows", r.text.count("\n") - 1)
    (out / "energiatodistukset.csv").write_bytes(requests.get(ENERGY_CERTS, headers=UA, timeout=900).content)
    fetch_heights(out / "city_model_heights.csv")
    fetch_demolished(out / "demolished")
    fetch_finna(out / "finna_hkm.jsonl")


if __name__ == "__main__":
    main()
