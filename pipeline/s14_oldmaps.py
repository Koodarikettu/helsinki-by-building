"""Old maps the city's map server lacks, placed on the map by control points (pipeline/oldmaps.json): scans in Finna
of the Helsinki City Archives (CC BY 4.0) and of the National Library (public domain, served by Doria). And two
Wikimedia Commons scans (public domain) as Wikimaps Warper placed them, taken from its WMS once (WARPER below).

A map's control points pair a pixel of its image (Finna's large one, or the Doria file its "url" names) with a
point in ETRS-GK25. Most were found by matching the map's features (SIFT) to a map already on the ground that it
shares its drawing with; the 1902 drawing's by template matching to the 1907 map, where the city already stood
(README). A polynomial of the map's order is fitted from the ground to the image by least squares, and the sheet's
outline in the image leaves its margins out.

Writes web/data/oldmaps/<Finna id, or warper.<its map>>/<level>/<i>-<j>.jpg, the ground's quadtree (web/app.js groundTile): 512 px tiles
from level 0 (65,536 m) down to the map's own level, black outside the sheet as the city's server paints it. The
deepest level is sampled from the scan and each level above is made from the four tiles under it; a tile wholly
outside the sheet is not written.
"""
import json
import shutil
from math import floor, log2
from pathlib import Path

import numpy as np
import requests
import shapely
from PIL import Image
from pyproj import Transformer
from scipy.ndimage import map_coordinates

from .s03_tiles import ORIGIN

RAW, OUT = Path("data/raw/oldmaps"), Path("web/data/oldmaps")
MAPS = json.loads((Path(__file__).parent / "oldmaps.json").read_text())
Image.MAX_IMAGE_PIXELS = max(w * h for w, h in (m["size"] for m in MAPS.values()))  # the largest scan, 94 Mpx
ROOT, PX = 65536, 512  # web/app.js GROUND_ROOT and GROUND_PX
LARGE = "https://api.finna.fi/Cover/Show?source=Solr&index=0&size=large"
UA = {"User-Agent": "helsinki-by-building/0.1 (non-commercial building map)"}
# Wikimaps Warper's maps 1206 and 1203, Pharus's plan of 1920 and a map of 1935 from Wikimedia Commons: they fall between
# the city's 1917, 1925 and 1940, the years Töölö was built up. Warper is slow (over a second a tile), so its tiles are
# taken once, at the level nearest the scan, and served with the map. Its WMS speaks no GK25, so a tile asks for the Web
# Mercator box between its corners, as the map once did itself: the grids turn 0.07° apart by Töölö, which shifts a
# tile's picture by a pixel at most. They come as PNG, see-through outside the sheet: black there, as the city's.
WARPER = ["1206", "1203"]
WARPER_API, WARPER_WMS = "https://warper.wmflabs.org/api/v1/maps/{}.json", "https://warper.wmflabs.org/maps/wms/{}"


def design(gk: np.ndarray, centre: np.ndarray, order: int) -> np.ndarray:
    x, y = ((gk - centre) / 1000).T
    return np.c_[(np.ones_like(x), x, y) + ((x * x, x * y, y * y) if order == 2 else ())]


def fit(points, order: int):
    """From [x, y, E, N] points: a function taking GK25 points (n, 2) to the image's pixels, and its residuals (px)."""
    p = np.asarray(points, float)
    centre = p[:, 2:].mean(0)
    co, *_ = np.linalg.lstsq(design(p[:, 2:], centre, order), p[:, :2], rcond=None)
    to_image = lambda gk: design(gk, centre, order) @ co
    return to_image, np.linalg.norm(to_image(p[:, 2:]) - p[:, :2], axis=1)


def tile_box(L: int, i: int, j: int):
    """A quadtree tile's west and north edges and its size, in metres (web/app.js groundTile)."""
    s = ROOT / 2 ** L
    return ORIGIN[0] - ROOT / 2 + i * s, ORIGIN[1] + ROOT / 2 - j * s, s


def tile_range(L: int, w: float, s: float, e: float, n: float):
    """The quadtree tiles of level L over a box in GK25."""
    size = ROOT / 2 ** L
    i0, j0 = floor((w - ORIGIN[0] + ROOT / 2) / size), floor((ORIGIN[1] + ROOT / 2 - n) / size)
    i1, j1 = floor((e - ORIGIN[0] + ROOT / 2) / size), floor((ORIGIN[1] + ROOT / 2 - s) / size)
    return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]


def write(id: str, tiles: dict, L: int) -> int:
    """Level L's tiles {(i, j): RGB} and every level above, each made from the four under it; bytes written."""
    out = OUT / id
    shutil.rmtree(out, ignore_errors=True)
    total = 0
    for level in range(L, -1, -1):
        (out / str(level)).mkdir(parents=True)
        for (i, j), t in tiles.items():
            f = out / str(level) / f"{i}-{j}.jpg"
            Image.fromarray(t).save(f, quality=82)
            total += f.stat().st_size
        parents = {}
        for (i, j), t in tiles.items():
            p = parents.setdefault((i // 2, j // 2), np.zeros((2 * PX, 2 * PX, 3), np.uint8))
            p[j % 2 * PX:(j % 2 + 1) * PX, i % 2 * PX:(i % 2 + 1) * PX] = t
        tiles = {k: np.asarray(Image.fromarray(p).resize((PX, PX), Image.Resampling.BOX)) for k, p in parents.items()}
    return total


def scan(id: str, m: dict) -> np.ndarray:
    f = RAW / f"{id}.jpg"
    if not f.exists():
        r = requests.get(m["url"], headers=UA, timeout=300) if "url" in m else \
            requests.get(LARGE, params={"id": id}, headers=UA, timeout=300)
        if not (r.ok and r.headers.get("Content-Type", "").startswith("image/jpeg")):  # Doria adds ";charset=UTF-8"
            raise RuntimeError(f"{id}: no image came")
        f.write_bytes(r.content)
    im = Image.open(f)
    if im.size != tuple(m["size"]):  # the control points are in the pixels of the image they were found on
        raise RuntimeError(f"{id}: the image is {im.size}, the control points are for {m['size']}")
    return np.asarray(im.convert("RGB"))


def cut(id: str, m: dict):
    img = scan(id, m)
    to_image, res = fit(m["points"], m["order"])
    to_ground, _ = fit([[e, n, x, y] for x, y, e, n in m["points"]], m["order"])
    sheet = shapely.Polygon(m["sheet"])
    w, s, e, n = shapely.MultiPoint(to_ground(np.array(shapely.segmentize(sheet, 50).exterior.coords))).bounds
    L = m["level"]
    tiles = {}
    for i, j in tile_range(L, w, s, e, n):
        west, north, size = tile_box(L, i, j)
        u = (np.arange(PX) + 0.5) * size / PX
        E, N = np.meshgrid(west + u, north - u)
        xy = to_image(np.c_[E.ravel(), N.ravel()])
        inside = shapely.contains_xy(sheet, xy[:, 0], xy[:, 1])
        if inside.any():
            rgb = np.stack([map_coordinates(img[..., k], [xy[:, 1], xy[:, 0]], order=1) for k in range(3)], -1)
            rgb[~inside] = 0
            tiles[i, j] = rgb.reshape(PX, PX, 3)
    total = write(id, tiles, L)
    print(f"{m['year']} {m['title']}: {len(res)} control points, residual median {np.median(res):.1f} px,"
          f" levels 0–{L}, {total / 1e6:.1f} MB")


def warper(id: str):
    """Warper's map `id` from its WMS, one tile at a time (kept in data/raw/oldmaps/warper.<id>/), down to the level
    nearest its scan: its box's pixel size, as if the scan filled the box."""
    meta = RAW / f"warper.{id}.json"
    if not meta.exists():
        meta.write_bytes(requests.get(WARPER_API.format(id), headers=UA, timeout=60).content)
    a = json.loads(meta.read_text())["data"]["attributes"]
    lon0, lat0, lon1, lat1 = map(float, a["bbox"].split(","))
    E, N = Transformer.from_crs(4326, 3879, always_xy=True).transform([lon0, lon1, lon0, lon1], [lat0, lat0, lat1, lat1])
    w, e, s, n = min(E), max(E), min(N), max(N)
    mpx = ((e - w) * (n - s) / (a["width"] * a["height"])) ** 0.5
    L = round(log2(ROOT / PX / mpx))
    merc = Transformer.from_crs(3879, 3857, always_xy=True)
    raw = RAW / f"warper.{id}" / str(L)
    raw.mkdir(parents=True, exist_ok=True)
    tiles = {}
    for i, j in tile_range(L, w, s, e, n):
        f = raw / f"{i}-{j}.png"
        if not f.exists():
            west, north, size = tile_box(L, i, j)
            box = [*merc.transform(west, north - size), *merc.transform(west + size, north)]
            r = requests.get(WARPER_WMS.format(id), headers=UA, timeout=120, params=dict(
                service="WMS", version="1.1.1", request="GetMap", layers="image", styles="", srs="EPSG:3857",
                bbox=",".join(map(str, box)), width=PX, height=PX, format="image/png", transparent="true"))
            if not (r.ok and r.headers.get("Content-Type", "").startswith("image/png")):
                raise RuntimeError(f"warper {id} {L}/{i}-{j}: no image came")
            f.write_bytes(r.content)
        rgba = np.asarray(Image.open(f).convert("RGBA"))
        if rgba[..., 3].any():  # a tile wholly outside the sheet is not written
            tiles[i, j] = np.where(rgba[..., 3:] > 127, rgba[..., :3], 0).astype(np.uint8)
    total = write(f"warper.{id}", tiles, L)
    print(f"Warper {id} {a['title']}: {mpx:.2f} m a pixel, levels 0–{L}, {len(tiles)} tiles, {total / 1e6:.1f} MB")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for id, m in MAPS.items():
        cut(id, m)
    for id in WARPER:
        warper(id)


if __name__ == "__main__":
    main()
