"""Self-check for placing the Heritage Agency's photos: uv run python -m pipeline.test_s12"""
from shapely.geometry import Point

from .s12_other import place_of

addr = {"unioninkatu 30": (1.0, 2.0)}
named = {"säätytalo": Point(3, 4)}
spot = {"senaatintori": (5.0, 6.0), "seurasaari": (7.0, 8.0)}
rec = lambda *places: {"subjectPlaces": list(places)}
assert place_of(rec("Suomi, Helsinki, Unioninkatu 30"), addr, named, spot) == ("Unioninkatu 30", 1.0, 2.0)
assert place_of(rec("Eurooppa, Suomi, Uusimaa, Helsinki, Vironniemen asemakaava-alue, Säätytalo"), addr, named, spot) == ("Säätytalo", 3, 4)
assert place_of(rec("Suomi, Helsinki, Senaatintori Helsinki"), addr, named, spot) == ("Senaatintori", 5.0, 6.0)
# the most exact part that is known: the open-air museum is not, its island is
assert place_of(rec("Suomi, Helsinki, Seurasaaren ulkomuseo, Helsinki, Seurasaari, Seurasaaren ulkomuseo"), addr, named, spot) == ("Seurasaari", 7.0, 8.0)
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
print("ok")
