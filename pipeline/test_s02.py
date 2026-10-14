"""Self-check for the year logic: uv run python -m pipeline.test_s02"""
import geopandas as gpd
import numpy as np
from shapely.geometry import Point

from .s02_attributes import FLAG_ESTIMATED, FLAG_EXACT, FLAG_FAINT, FLAG_PROPERTY, estimate_missing, smooth_round_years

# A round-decade spike: twelve on 1900 against one a year around it; 1935 is not a decade and stays.
years = [1900] * 12 + [1896, 1897, 1898, 1899, 1901, 1902, 1903, 1904] + [1935] * 5
p = gpd.GeoDataFrame(dict(key=[f"b{i}" for i in range(len(years))], year=years, date_flag=FLAG_EXACT,
                          c_kiinteistotunnus=None), geometry=[Point(i, 0) for i in range(len(years))])
p = smooth_round_years(p)
assert (p.year == 1900).sum() >= 1 and (p.date_flag == FLAG_FAINT).sum() == 11
assert p[p.date_flag == FLAG_FAINT].year.between(1895, 1905).all()
assert (p.year == 1935).sum() == 5

# Missing years: the same property first, else the twelve nearest dated buildings.
n = 12
p = gpd.GeoDataFrame(dict(key=[f"b{i}" for i in range(n + 4)], year=[1950, 1960, 0, 0] + [2000] * n,
                          date_flag=[FLAG_EXACT, FLAG_EXACT, FLAG_ESTIMATED, FLAG_ESTIMATED] + [FLAG_EXACT] * n,
                          c_kiinteistotunnus=["P", "P", "P", None] + [None] * n),
                     geometry=[Point(0, 0), Point(1, 0), Point(9000, 0), Point(2, 0)] + [Point(9000 + i, 0) for i in range(n)])
p = estimate_missing(p)
assert p.year[2] == 1955 and p.date_flag[2] == FLAG_PROPERTY    # among 2000s, but on property P
assert p.year[3] == int(np.median([1950, 1960] + [2000] * 10)) and p.date_flag[3] == FLAG_ESTIMATED
print("ok")
