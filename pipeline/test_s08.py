"""Self-check for the archive's address parsing: uv run python -m pipeline.test_s08"""
from .s08_archive import addresses, keys_of

assert keys_of("Aleksanterinkatu", "14-18") == ["aleksanterinkatu 14", "aleksanterinkatu 16", "aleksanterinkatu 18"]
assert keys_of("Unioninkatu", "33b") == ["unioninkatu 33b"]
assert keys_of("Kaivokatu", "1") == ["kaivokatu 1"]
assert keys_of("Puistotie", "") == []

place = lambda last: {"subjectPlaces": [f"Eurooppa, Pohjoismaat, Suomi, Uusimaa, Helsinki, Kluuvi Helsinki, {last}"]}
assert addresses(place("Läntinen Teatterikuja 1. Vilhonkatu 11.")) == ["läntinen teatterikuja 1", "vilhonkatu 11"]
assert addresses(place("Ruoholahdenkatu 24 D")) == ["ruoholahdenkatu 24"]   # D is a staircase
assert addresses(place("Hakaniemenpuisto")) == []
assert addresses({"subjectPlaces": ["Eurooppa, Pohjoismaat, Suomi, Uusimaa, Vihti, Saunarannantie 5"]}) == []
print("ok")
