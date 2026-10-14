"""Street names, placed along their own outlines.

Source: the street areas of Helsinki's register of public areas (YLRE_Katualue_alue, a polygon per stretch of street,
CC BY 4.0). Each polygon is cut into 300 m cells; every piece longer than it is wide gets one label at its centre,
turned along its long side. Tier 1 (main streets and motorways, by the register's own class) shows from afar,
tier 2 only up close. Streets not built yet are left out.

Also why each street in an address got its name, for the building card: the city's place-name register
(Nimisto_piste_rekisteritiedot, CC BY 4.0) gives the reason, and for many an older history of the name, in Finnish.
"""
import json
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry import box

from .s03_tiles import ORIGIN

CELL = 300.0
TIER1 = {"Pääkatu", "Moottoriväylä"}


def pieces(geom):
    x0, y0, x1, y1 = geom.bounds
    for cx in np.arange(math.floor(x0 / CELL) * CELL, x1, CELL):
        for cy in np.arange(math.floor(y0 / CELL) * CELL, y1, CELL):
            part = geom.intersection(box(cx, cy, cx + CELL, cy + CELL))
            for p in getattr(part, "geoms", [part]):
                if p.geom_type == "Polygon" and p.area > 200:
                    yield p


def placement(p):
    """Centre and angle (degrees, local frame) of a piece, or None if it is not elongated."""
    r = p.minimum_rotated_rectangle
    c = np.array(r.exterior.coords)[:4]
    e1, e2 = c[1] - c[0], c[2] - c[1]
    long, short = (e1, e2) if np.hypot(*e1) >= np.hypot(*e2) else (e2, e1)
    if np.hypot(*long) < 2.2 * np.hypot(*short) or np.hypot(*long) < 60:
        return None
    pt = p.representative_point() if not p.contains(p.centroid) else p.centroid
    ang = math.degrees(math.atan2(-long[1], long[0]))  # local z points south
    ang = (ang + 90) % 180 - 90  # keep text upright
    # The piece's width: area over length is the street's mean width, steadier than the rectangle's short side.
    width = p.area / max(np.hypot(*long), 1)
    return [round(pt.x - ORIGIN[0], 1), round(-(pt.y - ORIGIN[1]), 1), round(ang, 1), round(float(np.hypot(*long))),
            round(float(width), 1)]


def origins() -> dict:
    """{street name: [why it was given, its history]} for the streets in the buildings' addresses."""
    names = set(pd.read_parquet("data/buildings.parquet", columns=["katunimi_suomi"]).katunimi_suomi.dropna())
    n = gpd.read_file("data/raw/Nimisto_piste_rekisteritiedot.geojson")
    n = n[n.nimi_suomi.isin(names) & (n.nimeamisperuste.notna() | n.lisatieto.notna())]
    n = n.sort_values("laji_selite", key=lambda s: s != "Katu").drop_duplicates("nimi_suomi")  # a street before a park
    n = n.fillna({"nimeamisperuste": "", "lisatieto": ""})
    return {r.nimi_suomi: [r.nimeamisperuste.strip(), r.lisatieto.strip()] for r in n.itertuples()}


def main():
    names = origins()
    Path("web/data/streets.json").write_text(json.dumps(names, ensure_ascii=False, separators=(",", ":")))
    print(len(names), "street names explained;", Path("web/data/streets.json").stat().st_size // 1024, "KB")
    streets = gpd.read_file("data/raw/YLRE_Katualue_alue.geojson")
    streets = streets[streets.geometry.notna() & (streets.rakentamisen_tila != "Rakentamaton")]
    labels = []
    for r in streets.itertuples():
        pts = [pl for p in pieces(shapely.make_valid(r.geometry)) if (pl := placement(p))]
        if pts:
            labels.append(dict(name=r.kadun_nimi, water=False, tier=1 if r.kayttotarkoitus in TIER1 else 2, pts=pts))
    # One entry per name: a street is registered in many stretches; a name is tier 1 if any stretch is.
    merged = {}
    for l in sorted(labels, key=lambda l: l["tier"]):
        m = merged.setdefault(l["name"], dict(l, pts=[]))
        m["pts"] += l["pts"]
    labels = []
    for m in merged.values():
        # Keep placements at least 350 m apart, longest stretches first.
        kept = []
        for p in sorted(m["pts"], key=lambda p: -p[3]):
            if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 > 350 ** 2 for q in kept):
                kept.append(p)
        m["pts"] = kept
        labels.append(m)
    Path("web/data/labels.json").write_text(json.dumps(labels, ensure_ascii=False, separators=(",", ":")))
    print(len(labels), "names,", sum(len(l["pts"]) for l in labels), "placements,",
          sum(l["tier"] == 1 for l in labels), "tier 1;", Path("web/data/labels.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
