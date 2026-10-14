"""Years, floors, heights per building.

Year sources, in order of trust:
  exact      the register's completion date (c_valmpvm), as recorded
  faint      a round decade before 1930 in excess of what neighbouring years predict (1900: 170 buildings on record,
             against about 33 a year around it; 1850, 1880 and 1890 run five to ten times over too). The register
             rounds old dates to the decade, so the excess is spread across it, paler on the map
  property   no year, or a placeholder (1700 or earlier: the register's 1000 and 1001); median year of the
             dated buildings on the same property (c_kiinteistotunnus)
  estimated  as above, on a property with no dated building; median year of the nearest dated buildings
Floors: the register's i_kerrlkm, or one where it gives none.
Height: from the city's 3D model (LoD2), linked by VTJ-PRT: the 70th percentile of the roof's height (s00_fetch),
else its measured height (to the highest point), else, for a demolished building, the model's LoD1 height, else
floors × 3.2 m. A demolished building's year falls before the year it was demolished, estimated or not.
"""
import hashlib

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .periods import period_index

# The viewer draws flags 1, 2 and 4 paler and writes "n." before their year; 3 and 5 were Amsterdam's monument dates.
FLAG_EXACT, FLAG_FAINT, FLAG_ESTIMATED, FLAG_PROPERTY = 0, 1, 2, 4
PLACEHOLDER_MAX = 1700
ROUND_BEFORE = 1930
FLOORS_REGISTER, FLOORS_ASSUMED = 0, 1
HEIGHT_MODEL, HEIGHT_FLOORS = 0, 1
STOREY_M = 3.2


def unit_hash(ids: pd.Series, salt: str) -> np.ndarray:
    """Deterministic uniform [0,1) per id, so reruns give the same picture."""
    return np.array([int(hashlib.md5((salt + i).encode()).hexdigest()[:8], 16) / 2**32 for i in ids])


def smooth_round_years(p: pd.DataFrame) -> pd.DataFrame:
    """Keep as many buildings on a round decade as the years around it predict; spread the rest over the decade."""
    exact = p.date_flag.values == FLAG_EXACT
    y = p.year.values
    counts = pd.Series(y[exact]).value_counts()
    u, u2 = unit_hash(p.key, "round"), unit_hash(p.key, "spread")
    for year, n in sorted(counts.items()):
        if year >= ROUND_BEFORE or year % 10:
            continue
        expected = max(1.0, float(np.mean([counts.get(year + d, 0) for d in (-4, -3, -2, -1, 1, 2, 3, 4)])))
        if n <= expected:
            continue
        idx = np.where((y == year) & exact)[0]
        faint = idx[np.argsort(u[idx])][int(round(expected)):]
        p.iloc[faint, p.columns.get_loc("year")] = np.round(year - 5 + u2[faint] * 10).astype(int)
        p.iloc[faint, p.columns.get_loc("date_flag")] = FLAG_FAINT
        print(f"{year}: {n} on record, {expected:.0f} expected, {len(faint)} spread over {year - 5}–{year + 5}")
    return p


def estimate_missing(p: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Same property first, then the twelve nearest dated buildings."""
    known = p.date_flag.values != FLAG_ESTIMATED
    prop = p[known].groupby("c_kiinteistotunnus").year.median()
    by_prop = p.c_kiinteistotunnus.map(prop)
    hit = ~known & by_prop.notna().values
    p.loc[hit, "year"] = by_prop[hit].astype(int)
    p.loc[hit, "date_flag"] = FLAG_PROPERTY
    rest = np.where(~known & ~hit)[0]
    pts = np.c_[p.geometry.centroid.x, p.geometry.centroid.y]
    _, nn = cKDTree(pts[known]).query(pts[rest], k=12)
    p.iloc[rest, p.columns.get_loc("year")] = np.median(p.year.values[known][nn], axis=1).astype(int)
    return p


def main():
    p = gpd.read_parquet("data/buildings.parquet")

    p["orig"] = pd.to_numeric(p.c_valmpvm.str.slice(0, 4), errors="coerce").fillna(0).astype(int)  # 0: no year
    p["year"] = p.orig
    p["date_flag"] = np.where(p.orig > PLACEHOLDER_MAX, FLAG_EXACT, FLAG_ESTIMATED).astype(np.uint8)
    print("no year or a placeholder:", int((p.date_flag == FLAG_ESTIMATED).sum()))
    p = smooth_round_years(p)
    p = estimate_missing(p)
    p["year"] = np.where(p.gone > 0, np.minimum(p.year, p.gone - 1), p.year)
    p["period"] = p.year.map(period_index).astype(np.uint8)

    p["floors"] = p.i_kerrlkm.fillna(1).clip(1, 99).astype(np.uint8)
    p["floors_src"] = np.where(p.i_kerrlkm.notna(), FLOORS_REGISTER, FLOORS_ASSUMED).astype(np.uint8)
    model = pd.read_csv("data/raw/city_model_heights.csv", dtype={"vtj_prt": str})
    model["h"] = model.roof_p70.fillna(model.measured).where(lambda h: h > 0)
    modelled = p.vtj_prt.map(model.dropna(subset=["h"]).groupby("vtj_prt").h.max())  # a building cut by a tile edge
    modelled = modelled.fillna(p.lod1_height.where(p.lod1_height > 0))
    p["height_src"] = np.where(modelled.notna(), HEIGHT_MODEL, HEIGHT_FLOORS).astype(np.uint8)
    p["height"] = modelled.fillna(p.floors * STOREY_M).clip(lower=2.0)

    p = p.sort_values("key").reset_index(drop=True)
    p.to_parquet("data/buildings.parquet")

    print({
        "buildings": len(p),
        "exact": int((p.date_flag == FLAG_EXACT).sum()),
        "faint_round": int((p.date_flag == FLAG_FAINT).sum()),
        "property": int((p.date_flag == FLAG_PROPERTY).sum()),
        "estimated": int((p.date_flag == FLAG_ESTIMATED).sum()),
        "floors_register": int((p.floors_src == FLOORS_REGISTER).sum()),
        "floors_assumed": int((p.floors_src == FLOORS_ASSUMED).sum()),
        "height_model": int((p.height_src == HEIGHT_MODEL).sum()),
        "demolished": int((p.gone > 0).sum()),
    })
    print(p.groupby("period").size().to_dict())


if __name__ == "__main__":
    main()
