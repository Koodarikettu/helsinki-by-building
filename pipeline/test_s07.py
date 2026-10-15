"""Self-check for former street names and the street map: uv run python -m pipeline.test_s07"""
import json
import tempfile
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from . import s07_labels as s07

text = {"Liisankatu": "1819 muodossa Elisabeths Gatan. Suomenkielisenä nimenä karttaliitteessä 1866 Eliisapetinkatu."}
got = s07.former({"Liisankatu": [["Elisabeths Gatan", "1819"], ["Elisabetinkatu", "1880-luvulla"]],  # not in its text
                  "Kauhavankuja": [["Kauhavan kuja", "1923"]]}, text)                             # no text at all
assert got == {"Liisankatu": [["Elisabeths Gatan", "1819"]]}, got

s07.OUT = Path(tempfile.mkdtemp())
streets = gpd.GeoDataFrame({"kadun_nimi": ["Bkatu", "Akatu", "Ckatu", "Akatu"]},
                           geometry=[box(0, 0, 10, 100), box(20, 0, 30, 100), box(40, 0, 50, 100), box(20, 100, 30, 200)],
                           crs=3879)
s07.streetmap(streets, {"Ckatu"})
m = json.loads((s07.OUT / "streetmap.json").read_text())
# The street with a former name first, then the rest by name; a polygon per stretch, each pointing at its name.
assert m == {"names": ["Ckatu", "Akatu", "Bkatu"], "of": [0, 1, 1, 2], "old": 1}, m
print("ok")
