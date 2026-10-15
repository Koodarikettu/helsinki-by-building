"""Self-check for the War view: uv run python -m pipeline.test_s11"""
from .s11_war import clean, register_page, roman, shorten, wars_of

assert [roman(s) for s in ("I", "IV", "IX", "XIV", "XXXV", "XXXVII", "MUNKKA", None)] == [1, 4, 9, 14, 35, 37, 999, 999]
assert clean(float("nan")) == "" and clean(None) == "" and clean("  a\n b ") == "a b"  # a survey's empty field is NaN
assert shorten("One. Two. Three.", 10) == "One. Two." and shorten("short") == "short"

# A register page's fields, as kyppi.fi lays them out
page = register_page("""<tr><td class="norm">Ajoitus:</td>
  <td class="norm">moderni, toinen maailmansota 1939&ndash;1945 </td></tr>
  <tr><td class="norm">Tarkenne:</td><td class="norm">II maailmansodan varustus, ilmapuolustus</td></tr>
  <span id="kuvaus" style="display:none"><table><tr><td class="norm">Toisen maailmansodan aikainen patteri.</td></tr>""")
assert page == {"dating": "moderni, toinen maailmansota 1939–1945", "kind": "II maailmansodan varustus, ilmapuolustus",
                "text": "Toisen maailmansodan aikainen patteri."}

site = lambda dating="", kind="", text="": dict(dating=dating, kind=kind, text=text)
assert wars_of(site("moderni, toinen maailmansota 1939–1945")) == [1]
assert wars_of(site("historiallinen, 1900-luku", "I maailmansodan varustukset")) == [0]
assert wars_of(site(kind="II. maailmansodan varustus, ilmapuolustus")) == [1]                # "II" is not "I"
assert wars_of(site(kind="I ms ja II ms varustus")) == [0, 1]
assert wars_of(site(text="Mahdollisesti ensimmäisen maailmansodan aikainen luola.")) == [0]
assert wars_of(site(text="Kaksi patteria. Vieressä on ensimmäisen maailmansodan aikainen luola.")) == []  # a neighbour's
assert wars_of(site("historiallinen, 1700-luku")) == []
print("ok")
