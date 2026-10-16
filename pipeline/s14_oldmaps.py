"""Old maps the city's map server lacks, placed on the map by control points (pipeline/oldmaps.json): the Helsinki
City Archives' scans in Finna (CC BY 4.0) of the city in 1907 and of a competition entry of 1902 for Töölö.

A map's control points pair a pixel of Finna's large image with a point in ETRS-GK25. The 1907 map's were found by
matching its features (SIFT) to the city's own georeferenced map of 1909; the 1902 drawing's by template matching to
the 1907 map, where the city already stood (README). A polynomial of the map's
order is fitted from the ground to the image by least squares, and the sheet's outline in the image leaves its
margins out.

Writes web/data/oldmaps/<Finna id>/<level>/<i>-<j>.jpg, the ground's quadtree (web/app.js groundTile): 512 px tiles
from level 0 (65,536 m) down to the map's own level, black outside the sheet as the city's server paints it. The
deepest level is sampled from the scan and each level above is made from the four tiles under it; a tile wholly
outside the sheet is not written.
"""
import json
import shutil
from math import floor
from pathlib import Path

import numpy as np
import requests
import shapely
from PIL import Image
from scipy.ndimage import map_coordinates

from .s03_tiles import ORIGIN

RAW, OUT = Path("data/raw/oldmaps"), Path("web/data/oldmaps")
MAPS = json.loads((Path(__file__).parent / "oldmaps.json").read_text())
ROOT, PX = 65536, 512  # web/app.js GROUND_ROOT and GROUND_PX
LARGE = "https://api.finna.fi/Cover/Show?source=Solr&index=0&size=large"
UA = {"User-Agent": "helsinki-by-building/0.1 (non-commercial building map)"}


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


def scan(id: str, m: dict) -> np.ndarray:
    f = RAW / f"{id}.jpg"
    if not f.exists():
        r = requests.get(LARGE, params={"id": id}, headers=UA, timeout=300)
        if not (r.ok and r.headers.get("Content-Type") == "image/jpeg"):
            raise RuntimeError(f"{id}: Finna sent no image")
        f.write_bytes(r.content)
    im = Image.open(f)
    if im.size != tuple(m["size"]):  # the control points are in the pixels of the image they were found on
        raise RuntimeError(f"{id}: Finna's large image is {im.size}, the control points are for {m['size']}")
    return np.asarray(im.convert("RGB"))


def cut(id: str, m: dict):
    img = scan(id, m)
    to_image, res = fit(m["points"], m["order"])
    to_ground, _ = fit([[e, n, x, y] for x, y, e, n in m["points"]], m["order"])
    sheet = shapely.Polygon(m["sheet"])
    w, s, e, n = shapely.MultiPoint(to_ground(np.array(shapely.segmentize(sheet, 50).exterior.coords))).bounds
    L = m["level"]
    size = ROOT / 2 ** L
    i0, j0 = floor((w - ORIGIN[0] + ROOT / 2) / size), floor((ORIGIN[1] + ROOT / 2 - n) / size)
    i1, j1 = floor((e - ORIGIN[0] + ROOT / 2) / size), floor((ORIGIN[1] + ROOT / 2 - s) / size)
    tiles = {}
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            west, north, size = tile_box(L, i, j)
            u = (np.arange(PX) + 0.5) * size / PX
            E, N = np.meshgrid(west + u, north - u)
            xy = to_image(np.c_[E.ravel(), N.ravel()])
            inside = shapely.contains_xy(sheet, xy[:, 0], xy[:, 1])
            if inside.any():
                rgb = np.stack([map_coordinates(img[..., k], [xy[:, 1], xy[:, 0]], order=1) for k in range(3)], -1)
                rgb[~inside] = 0
                tiles[i, j] = rgb.reshape(PX, PX, 3)
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
    print(f"{m['year']} {m['title']}: {len(res)} control points, residual median {np.median(res):.1f} px,"
          f" levels 0–{L}, {total / 1e6:.1f} MB")


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    for id, m in MAPS.items():
        cut(id, m)


if __name__ == "__main__":
    main()
