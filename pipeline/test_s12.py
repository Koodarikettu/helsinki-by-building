"""Self-check for placing the Heritage Agency's photos, the parking fines and the tracks: uv run python -m pipeline.test_s12"""
import tempfile
from pathlib import Path

import numpy as np
from shapely.geometry import Point

from .s03_tiles import ORIGIN
from .s12_other import place_of, reason, street_key, street_of, write_tracks

addr = {"unioninkatu 30": (1.0, 2.0)}
named = {"säätytalo": Point(3, 4)}
spot = {"senaatintori": (5.0, 6.0), "seurasaari": (7.0, 8.0)}
rec = lambda *places: {"subjectPlaces": list(places)}
assert place_of(rec("Suomi, Helsinki, Unioninkatu 30"), addr, named, spot) == ("Unioninkatu 30", 1.0, 2.0)
assert place_of(rec("Eurooppa, Suomi, Uusimaa, Helsinki, Vironniemen asemakaava-alue, Säätytalo"), addr, named, spot) == ("Säätytalo", 3, 4)
assert place_of(rec("Suomi, Helsinki, Senaatintori Helsinki"), addr, named, spot) == ("Senaatintori", 5.0, 6.0)
# the most exact part that is known: the open-air museum is not, its island is
assert place_of(rec("Suomi, Helsinki, Seurasaaren ulkomuseo, Helsinki, Seurasaari, Seurasaaren ulkomuseo"), addr, named, spot) == ("Seurasaari", 7.0, 8.0)
# the City Museum closes each address with a full stop, and names a place before its address the same way
assert place_of(rec("Helsinki, Kluuvi Helsinki, Unioninkatu 30."), addr, named, spot) == ("Unioninkatu 30", 1.0, 2.0)
assert place_of(rec("Helsinki, Kallio Helsinki, Pyöräilystadion. Unioninkatu 30."), addr, named, spot) == ("Unioninkatu 30", 1.0, 2.0)
assert place_of(rec("Suomi, Helsinki, Helsinki"), addr, named, spot) is None          # the city alone
assert place_of(rec("Suomi, Kuopio, Senaatintori"), addr, named, spot) is None        # not Helsinki
assert place_of({"subjectPlaces": ["Helsinki"], "geoLocations": ["POINT(24.94354 60.16664)"]}, addr, named, spot) is None
# Finna's own point, kept for a named place but not for a district's middle
from pyproj import Transformer
gk25 = Transformer.from_crs(4326, 3879, always_xy=True)
box = (gk25.transform(24.78, 60.09), gk25.transform(25.27, 60.33))
pt = lambda name: {"subjectPlaces": [f"Suomi, Helsinki, {name}"], "geoLocations": ["POINT(24.95 60.17)"]}
assert place_of(pt("Esplanadi"), addr, named, spot, gk25, box, {"kallio"})[0] == "Esplanadi"
assert place_of(pt("Kallio Helsinki"), addr, named, spot, gk25, box, {"kallio"}) is None
assert place_of(pt("Suomenlinna"), addr, named, spot, gk25, box, {"suomenlinna"})[0] == "Suomenlinna"
# a parking fine's main reason, without its code; a second reason after it is dropped
assert reason("0601 pysäköinti ilman p-tunnusta/p-laitetta/p-lippua ") == "Pysäköinti ilman p-tunnusta/p-laitetta/p-lippua"
assert reason("0401 Pysäköintikieltoalue liikennemerkin noudattamatta jättäminen 1501 Pysäköinti jalkakäytävälle") == \
    "Pysäköintikieltoalue liikennemerkin noudattamatta jättäminen"
assert reason("1302 Pysäköinti 5 m matkalle ennen suojatietä ") == "Pysäköinti 5 m matkalle ennen suojatietä"  # 5 m is no code
# the fines' streets and the street areas' write some names differently
assert street_key("Kolmas linja") == street_key("Kolmas Linja") and street_key("Katajanokanlaituri") == street_key("Katajanokan laituri")
assert street_key("Tarkk'ampujankatu") == street_key("Tarkk'Ampujankatu") and street_key("Kauppakatu") != street_key("Kauppatori")
assert street_key("Castréninkatu") == street_key("Castreninkatu") and street_key("Mäkitie") != street_key("Makitie")
assert street_of("Fredrikinkatu 12 A") == "Fredrikinkatu" and street_of("Tilkantori (tori tai aukio)") == "Tilkantori"
assert street_of("Kauppatori") == "Kauppatori" and street_of(None) == ""
# the tracks file reads as web/app.js trackLines reads it: three lines, so the kinds are padded to four bytes
with tempfile.TemporaryDirectory() as d:
    f = Path(d) / "t.bin"
    line = lambda n: np.array(ORIGIN) + np.arange(2 * n).reshape(n, 2)
    write_tracks(f, [(line(2), 1862, 0, 0), (line(3), 1895, 2011, 0), (line(2), 1982, 0, 1)])
    buf = f.read_bytes()
    n, nv = map(int, np.frombuffer(buf, "<u4", 2))
    start = np.frombuffer(buf, "<u4", n + 1, 8)
    at = 8 + 4 * (n + 1)
    assert (n, nv, list(start)) == (3, 7, [0, 2, 5, 7])
    assert list(np.frombuffer(buf, "<i2", n, at)) == [1862, 1895, 1982] and list(np.frombuffer(buf, "<i2", n, at + 2 * n)) == [0, 2011, 0]
    assert list(np.frombuffer(buf, "u1", n, at + 4 * n)) == [0, 0, 1]
    xz = np.frombuffer(buf, "<f4", 2 * nv, at + 4 * n + -(-n // 4) * 4)
    assert len(buf) == at + 4 * n + 4 + 8 * nv and np.allclose(xz[:2], [0, -1])  # the first point, a metre north of Senaatintori
print("ok")
