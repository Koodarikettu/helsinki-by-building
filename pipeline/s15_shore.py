"""The shore through time: when each part of the land the city has filled in from the sea first shows as land.

The city's fill areas (Meritayttoalueet, CC BY 4.0) say where the sea was, not when it was filled. The when is read here
from the city's dated maps and aerial photos on its map server (those of the Map menu), 1870–2025:
- Each source is taken in 2 km tiles over the fill areas, with a margin of 250 m, at 2.5 m a pixel (data/raw/shore/).
- A pixel is water or land by its 25 nearest pixels, in colour and in the spread of brightness around it, among those
  of the same tile and source that are surely water (today's sea and lakes, 25 m or more from their shore) or surely land (today's
  land outside the fill areas, as far from their edge): over 0.65 land, under 0.35 water, else not known. A source that
  tells its own sure water from sure land less than 75 % right in a tile is left out there.
- A pixel of the fill turns from water to land once: at the latest source where that disagrees least with the sources,
  each weighted by the log-odds of how well it tells water from land in the tile. Its years are that source's ("to",
  the first to show it as land) and that of the last source before it to show water ("from", 0 if none did). A pixel
  no source reads takes its nearest neighbour's years, and a 9-pixel median smooths them.
Left out: the parish map of 1749 (its water and land are one colour), the reconnaissance map of 1780–1782 (some 100 m
off), the town plans of 1820, 1838 and 1878 (they draw planned blocks on the water) and the bird's-eye drawing of 2014.
So the first source is the Senate's map of 1870: what is land in it was filled before 1870, and when is not known here.

Writes web/data/shore.bin, s04_water's polygons with their years between the ring table and the vertices:
  i16 from[nPoly] (0: before the first source); i16 to[nPoly]; u8 kind[nPoly] (its colour in the legend; padded to 4)
and data/shore.json, the view, which s12_other puts in the Other menu.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import shapely
from PIL import Image, ImageDraw
from scipy.ndimage import binary_erosion, distance_transform_edt, median_filter, uniform_filter
from scipy.spatial import cKDTree

from .periods import PERIODS, period_index
from .s00_fetch import UA
from .s04_water import pack

RAW, OUT = Path("data/raw"), Path("web/data")
WMS = "https://kartta.hel.fi/ws/geoserver/avoindata/wms"
SOURCES = sorted([
    (1870, "Senaatinkartta_1870"), (1900, "Plan_af_Helsingfors_1900"),
    (1909, "Kartta_Helsingin_kaupungista_ja_sen_alueista_1909"), (1917, "Helsingin_kaupunki_1917_1918"),
    (1925, "Helsingin_kaupungin_kartta_1925"), (1940, "Helsinki_1940"), (1952, "Helsingin_matkailijakartta_1952"),
    (1962, "Helsingin_keskustan_kartta_1962"),
    *[(y, f"Opaskartta_{y}") for y in (1965, 1966, 1971, 1975, 1977, 1979, 1983, 1985, 1987, 1989, 1991, 1999)],
    *[(y, f"Ortoilmakuva_{y}") for y in (1932, 1943, 1950, 1964, 1969, 1976, 1988, 1996)],
    (2008, "Ortoilmakuva_2008_25cm"), (2017, "Ortoilmakuva_2017_20cm"), (2021, "Ortoilmakuva_2021_10cm"),
    (2025, "Ortoilmakuva_2025_5cm")])
YEARS = np.array([y for y, _ in SOURCES])
T, M, PX = 2000, 250, 2.5    # tile, margin, pixel (m)
WIDE = 2000                  # the margin of a tile with too little sure water or land in the first (a pond inland)
SURE = np.ones((21, 21), bool)  # 25 m from a shore
BEFORE = "#8a8178"           # filled before the first source: no period of its own


def raster(geoms, x0, y1, w, h) -> np.ndarray:
    im = Image.new("1", (w, h))
    d = ImageDraw.Draw(im)
    px = lambda ring: [((x - x0) / PX, (y1 - y) / PX) for x, y in ring.coords]
    for g in geoms:
        for p in getattr(g, "geoms", [g]):
            if p.geom_type == "Polygon":
                d.polygon(px(p.exterior), fill=1)
                for h_ in p.interiors:
                    d.polygon(px(h_), fill=0)
    return np.array(im, bool)


def image(layer: str, i: int, j: int, m: int = M) -> np.ndarray:
    f = RAW / "shore" / layer / (f"{i}_{j}.jpg" if m == M else f"{i}_{j}_{m}.jpg")
    if not f.exists():
        x0, y0, n = i * T - m, j * T - m, int((T + 2 * m) / PX)
        r = requests.get(WMS, headers=UA, timeout=300, params=dict(
            service="WMS", version="1.3.0", request="GetMap", layers=f"avoindata:{layer}", styles="", crs="EPSG:3879",
            bbox=f"{y0},{x0},{y0 + n * PX},{x0 + n * PX}", width=n, height=n, format="image/jpeg"))
        r.raise_for_status()
        assert r.headers["content-type"].startswith("image/"), r.text[:300]
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
    return np.asarray(Image.open(f).convert("RGB"))


def features(img: np.ndarray) -> np.ndarray:
    a = img.astype(np.float32)
    mean = [uniform_filter(a[..., c], 5) for c in range(3)]
    L = a.mean(-1)
    spread = np.sqrt(np.maximum(uniform_filter(L * L, 7) - uniform_filter(L, 7) ** 2, 0))
    return np.stack([*mean, spread], -1).reshape(-1, 4)


def read(img, water, land, q, rng):
    """Each pixel q as 1 land, 0 water, -1 not known, and the source's weight in the tile (0: left out)."""
    nodata = ((img.max(-1) < 20) | (img.min(-1) > 245)).reshape(-1)  # outside the sheet: black, or the paper
    X = features(img)
    wi, li = (np.flatnonzero(m.reshape(-1) & ~nodata) for m in (water, land))
    if min(len(wi), len(li)) < 500:
        return None, 0.0
    wi, li = (rng.choice(s, min(20000, len(s)), replace=False) for s in (wi, li))
    train, y = np.r_[X[wi], X[li]], np.r_[np.zeros(len(wi)), np.ones(len(li))]
    scale = train.std(0) + 1e-6
    tree = cKDTree(train / scale)
    _, nn = tree.query(train[::20] / scale, k=26, workers=-1)  # leave itself out
    acc = min(((y[nn[:, 1:]].mean(1) > 0.5) == y[::20]).mean(), 0.99)
    if acc < 0.75:
        return None, 0.0
    _, nn = tree.query(X[q] / scale, k=25, workers=-1)
    p = y[nn].mean(1)
    obs = np.where(p > 0.65, 1, np.where(p < 0.35, 0, -1)).astype(np.int8)
    obs[nodata[q]] = -1
    return obs, float(np.log(acc / (1 - acc)))


def step(obs: np.ndarray, w: np.ndarray):
    """(S, n) observations → the source index where each pixel first shows as land (S: never) and the last before it
    to show water (-1: none)."""
    S = len(obs)
    land, water = (obs == 1) * w[:, None], (obs == 0) * w[:, None]
    cost = (np.r_[np.zeros((1, obs.shape[1])), np.cumsum(land, 0)]                      # land before the step
            + np.r_[np.cumsum(water[::-1], 0)[::-1], np.zeros((1, obs.shape[1]))])     # water from it on
    k = S - np.argmin(cost[::-1], 0)
    k[(land.sum(0) == 0)] = S  # never seen as land: not known
    ar = np.arange(S)[:, None]
    last_water = np.where((obs == 0) & (ar < k), ar, -1).max(0)
    return k, last_water


def date_tile(i, j, m, fill, sea, land, rng):
    """The fill's pixels in a tile (rows and columns from its north-west corner) and their codes (below), and the
    number of sources read there."""
    S, n, c = len(SOURCES), int((T + 2 * m) / PX), int(m / PX)
    x0, y1 = i * T - m, (j + 1) * T + m
    box = shapely.box(x0, y1 - n * PX, x0 + n * PX, y1)
    f, w_, l_ = (raster(g.clip(box).geometry, x0, y1, n, n) for g in (fill, sea, land))
    water, sure_land = binary_erosion(w_ & ~f, SURE), binary_erosion(l_ & ~f, SURE)
    core = np.zeros_like(f)
    core[c:-c, c:-c] = True
    q = np.flatnonzero((f & core).reshape(-1))
    obs, w = np.full((S, len(q)), -1, np.int8), np.zeros(S)
    for s, (_, layer) in enumerate(SOURCES):
        o, w[s] = read(image(layer, i, j, m), water, sure_land, q, rng)
        if o is not None:
            obs[s] = o
    k, last = step(obs, w)
    r, col = np.divmod(q, n)
    return r - c, col - c, np.where(k < S, k * (S + 1) + last + 1, -1), int((w > 0).sum())


def main():
    fill = gpd.read_file(RAW / "Meritayttoalueet.geojson")
    sea = pd.concat([gpd.read_file(RAW / f"Maavesi_{n}.geojson") for n in ("merialue", "muut_vesialueet")])
    land = pd.concat([gpd.read_file(RAW / f"Maavesi_{n}.geojson") for n in ("manner", "saaret")])
    u = fill.union_all()
    x0, y0, x1, y1 = fill.total_bounds
    I, J = range(int(x0 // T), int(x1 // T) + 1), range(int(y0 // T), int(y1 // T) + 1)
    tiles = [(i, j) for i in I for j in J if u.intersects(shapely.box(i * T, j * T, (i + 1) * T, (j + 1) * T))]
    with ThreadPoolExecutor(6) as ex:  # the map server, once; then from data/raw/shore
        list(ex.map(lambda a: image(a[1], *a[0]), [(t, l) for t in tiles for _, l in SOURCES]))

    gx0, gy1 = I[0] * T, (J[-1] + 1) * T
    gw, gh = len(I) * int(T / PX), len(J) * int(T / PX)
    S = len(SOURCES)
    code = np.full((gh, gw), -1, np.int32)  # k * (S + 1) + last water + 1; -1: not fill, or not known
    rng = np.random.default_rng(0)
    for i, j in tiles:
        r, col, c, read_by = date_tile(i, j, M, fill, sea, land, rng)
        if not read_by:
            r, col, c, read_by = date_tile(i, j, WIDE, fill, sea, land, rng)
        code[int((gy1 - (j + 1) * T) / PX) + r, int((i * T - gx0) / PX) + col] = c
        print(f"tile {i},{j}: {len(c)} px, {(c >= 0).mean():.0%} read, sources {read_by}/{S}")

    mask = raster(fill.geometry, gx0, gy1, gw, gh)
    near = distance_transform_edt(code < 0, return_distances=False, return_indices=True)
    code = median_filter(code[near[0], near[1]], 9)  # the median of 81 neighbours is one of them: a real pair of years
    code[~mask] = -1

    # Runs of one code along each row → boxes → a polygon per code, cut to the fill's own outline.
    r, a = np.nonzero(np.diff(np.pad(code, ((0, 0), (1, 1)), constant_values=-1), axis=1))
    same = r[1:] == r[:-1]  # each change opens a run that the next change in its row closes
    rr, aa, bb = r[:-1][same], a[:-1][same], a[1:][same]
    cc = code[rr, aa]
    rr, aa, bb, cc = rr[cc >= 0], aa[cc >= 0], bb[cc >= 0], cc[cc >= 0]
    boxes = shapely.box(gx0 + aa * PX, gy1 - (rr + 1) * PX, gx0 + bb * PX, gy1 - rr * PX)
    polys, meta = [], []
    for c in np.unique(cc):
        g = shapely.union_all(boxes[cc == c]).intersection(u).simplify(1.0)
        k, last = divmod(int(c), S + 1)
        for p in getattr(g, "geoms", [g]):
            if p.geom_type == "Polygon" and p.area >= 25:
                polys.append(p)
                meta.append((int(YEARS[last - 1]) if last else 0, int(YEARS[k])))

    # Colours: before the first source, else the period of the first source to show land.
    kind_of = lambda fr, to: 0 if to == YEARS[0] else 1 + period_index(to)
    kinds = sorted({kind_of(*m) for m in meta})
    legend = [dict(color=BEFORE, label=f"Before {YEARS[0]}", label_fi=f"Ennen vuotta {YEARS[0]}") if k == 0 else
              dict(color=PERIODS[k - 1][4], label=PERIODS[k - 1][1]) for k in kinds]
    kind = np.array([kinds.index(kind_of(*m)) for m in meta], "u1")
    area = np.array([p.area for p in polys])
    for i, g in enumerate(legend):
        g["n"] = round(area[kind == i].sum() / 1e4)
    fr, to = (np.array(x, "<i2") for x in zip(*meta))
    extra = fr.tobytes() + to.tobytes() + kind.tobytes() + bytes(-len(kind) % 4)
    (OUT / "shore.bin").write_bytes(pack(polys, extra))
    total, before = area.sum() / 1e4, area[to == YEARS[0]].sum() / 1e4
    Path("data/shore.json").write_text(json.dumps(view(legend, total, before), ensure_ascii=False))
    print(f"shore.bin {len(polys)} polygons, {total:.0f} ha, {before:.0f} ha before {YEARS[0]},"
          f" {(OUT / 'shore.bin').stat().st_size / 1e6:.2f} MB;", {g["label"]: g["n"] for g in legend})


def view(legend, total, before) -> dict:
    first, last = int(YEARS[0]), int(YEARS[-1])
    return dict(
        id="shore", menu="other", label="The shore through time", label_fi="Rantaviiva ajan mukana",
        years=f"{first}–{last}", years_fi=f"{first}–{last}",
        text=(f"Where Helsinki has filled in the sea, {total:.0f} ha, coloured by when each part first shows as land in "
              f"the city's dated maps and aerial photos ({len(SOURCES)} of them, {first}–{last}), with the periods of the "
              "buildings. Drag the timeline or play it: a part is sea until the last source that still shows water there, "
              f"pale until the first that shows land, and in its colour from then on. {before:.0f} ha was land already in "
              f"{first}."),
        text_fi=(f"Mereen täytetty Helsinki, {total:.0f} ha, värjättynä sen mukaan, milloin kukin osa näkyy ensi kertaa "
                 f"maana kaupungin ajoitetuissa kartoissa ja ilmakuvissa ({len(SOURCES)} lähdettä, {first}–{last}), samoin "
                 "kausivärein kuin rakennukset. Vedä aikajanaa tai toista se: osa on merta viimeiseen lähteeseen asti, "
                 "jossa siinä vielä näkyy vettä, haalea siihen asti, kun ensimmäinen lähde näyttää maata, ja sen jälkeen "
                 f"oman värinsä. Vuonna {first} maata oli jo {before:.0f} ha."),
        caveat=("Read automatically from the colours of the maps and photos, within the city's estimate of the natural "
                "shore (for 1:25,000): the edges are rough, and a ship, a pier or ice can make the sea read as land for a "
                f"year. What is land in the Senate's map of {first} was filled earlier, when is not known here: the older "
                "maps cannot be read reliably. Two filled ponds, Tölö träsk and Sörnäs träsk, are in too."),
        caveat_fi=("Luettu automaattisesti karttojen ja ilmakuvien väreistä kaupungin arvioiman luonnontilaisen rannan "
                   "sisältä (mittakaava 1:25 000): reunat ovat karkeita, ja laiva, laituri tai jää voi saada meren näyttämään "
                   f"vuoden ajan maalta. Mikä on maata senaatin kartassa {first}, on täytetty jo aiemmin, eikä aikaa tiedetä: "
                   "vanhempia karttoja ei voi lukea luotettavasti. Mukana on myös kaksi täytettyä lampea, Tölö träsk ja "
                   "Sörnäs träsk."),
        fill="shore.bin", linesTitle="First shows as land, ha", linesTitle_fi="Ensi kertaa maana, ha", legend=legend,
        kinds=[dict(id="shore", label="Land filled in from the sea", label_fi="Mereen täytetty maa", color=legend[-1]["color"],
                    menu=False, list=False, sites=[],
                    source=dict(label="City of Helsinki, reclaimed land in Helsinki", label_fi="Helsingin kaupunki, Helsingin meritäyttöalueet",
                                url="https://hri.fi/data/fi/dataset/helsingin-meritayttoalueet", licence="CC BY 4.0"))],
        sources=[dict(label="City of Helsinki, old maps and aerial photos", label_fi="Helsingin kaupunki, vanhat kartat ja ilmakuvat",
                      url="https://kartta.hel.fi", licence="CC BY 4.0")])


if __name__ == "__main__":
    main()
