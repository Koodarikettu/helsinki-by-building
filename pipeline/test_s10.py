"""Self-check for energy labels and solar potential: uv run python -m pipeline.test_s10"""
import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from .s10_energy import COLS, labels, solar

b = gpd.GeoDataFrame({"key": ["100000001A", "100000002B", "100000003C"], "vtj_prt": ["100000001A", "100000002B", None],
                      "c_valmpvm": ["1960-01-01T00:00:00+02:00", "2014-06-01T00:00:00+03:00", None], "gone": [0, 0, 0]},
                     geometry=[box(0, 0, 20, 20), box(100, 0, 120, 20), box(200, 0, 220, 20)], crs=3879)
certs = pd.DataFrame([["1", "2013", "2015-01-01T10:00", "100000001A", "250", "F"],
                      ["2", "2018", "2023-05-01T10:00", "100000001A", "140", "C"],   # signed last: wins
                      ["3", "2018", "2024-01-01T10:00", "999999999Z", "90", "A"]],   # no such building
                     columns=COLS)
e = labels(b, certs)
assert e.to_dict("records") == [{"key": "100000001A", "eclass": 5, "eluku": 140, "ever": 18}]

hsy = gpd.GeoDataFrame({"elec_kwh_v": [1000.0, 500.0, 0.0, 800.0], "panel_ala": [10.0, 5.0, 0.0, 8.0]},
                       geometry=[box(1, 1, 9, 19), box(11, 1, 19, 19),   # two outlines in one building of ours: summed
                                 box(101, 1, 119, 19),                    # completed 2014: the estimate predates it
                                 box(201, 1, 219, 19)], crs=3879)
s = solar(b, hsy).set_index("key")
assert s.solar_kwh.to_dict() == {"100000001A": 1500.0, "100000003C": 800.0}
assert s.panel_m2["100000001A"] == 15.0
print("ok")
