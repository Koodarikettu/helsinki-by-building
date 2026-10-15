"""Context layers: each a set of buildings, one bit per group in a 64-bit mask per building.

A source returns {building key: group} or {key: (group, note)}. A note's `story` shows on the pinned card;
a `name` also lists the building in the layer's panel. Finnish sits next to each text as `<field>_fi`.
Writes data/layers.parquet (lay0, lay1 per building) and web/data/layers.json (the catalogue).
"""
import json
from functools import cache
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from .s03_tiles import to_local

LAYERS = []


def layer(**meta):
    def wrap(fn):
        LAYERS.append(dict(meta, source_fn=fn))
        return fn
    return wrap


@cache
def buildings() -> gpd.GeoDataFrame:
    """The layers tell of the city standing today: demolished buildings are in none."""
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "i_pyraknro", "year", "gone", "geometry"])
    return b[b.gone == 0].reset_index(drop=True)


def within(polygons: gpd.GeoDataFrame) -> pd.DataFrame:
    """Buildings whose representative point lies inside a polygon, with the polygon's columns."""
    b = buildings()
    pts = gpd.GeoDataFrame({"key": b.key}, geometry=b.representative_point(), crs=b.crs)
    return gpd.sjoin(pts, polygons.to_crs(b.crs), predicate="within").drop(columns=["geometry", "index_right"])


# ---------- layers ----------

PROTECTION = ["sr1", "sr2", "sr3", "other"]  # strongest first: a building in two plans takes the stronger


@layer(
    id="protected", section="Heritage", section_fi="Rakennusperintö", era="", era_fi="",
    title="Protected in the local plan", title_fi="Asemakaavassa suojellut",
    # sr-1/2/3 as the city's current standard regulations word them (Asemakaavalla suojeltavat rakennukset,
    # 8.6.2021, https://ahjojulkaisu.hel.fi/FC4D20F5-89E5-CD0E-93B0-82D558A00002.pdf); each plan has its own wording.
    text=("Helsinki protects buildings through its local detailed plans. In current plans sr-1 marks a building of "
          "especial architectural, historical or townscape value, sr-2 a valuable one and sr-3 one valuable to the "
          "townscape. The wording and the strength of protection vary from plan to plan, and older plans used other "
          "marks, such as s and SO. The card gives the building's own plan and marking."),
    text_fi=("Helsinki suojelee rakennuksia asemakaavoilla. Nykyisissä kaavoissa sr-1 on rakennustaiteellisesti, "
             "historiallisesti tai kaupunkikuvallisesti erityisen arvokas rakennus, sr-2 arvokas ja sr-3 "
             "kaupunkikuvallisesti arvokas. Merkintöjen sanamuoto ja suojelun vahvuus vaihtelevat kaavoittain, ja "
             "vanhemmissa kaavoissa on muita merkintöjä, kuten s ja SO. Kortissa näkyy rakennuksen oma kaava, "
             "merkintä ja kaavamääräyksen alku."),
    caveat=("A building is linked by the number the plan gives it, or by standing inside the protected outline. "
            "Plan regulations are in Finnish only."),
    caveat_fi=("Rakennus on liitetty kaavan rakennusnumerolla tai sen perusteella, että se on suojellun "
               "rajauksen sisällä."),
    source=("City of Helsinki, buildings protected in local plans", "Helsingin kaupunki, asemakaavoissa suojellut rakennukset",
            "https://hri.fi/data/fi/dataset/asemakaavoilla-suojellut-rakennukset-ja-alueet-helsingissa"),
    groups=[("sr1", "sr-1", "sr-1"), ("sr2", "sr-2", "sr-2"), ("sr3", "sr-3", "sr-3"),
            ("other", "Older markings", "Vanhemmat merkinnät")],
)
def protected():
    s = gpd.read_file("data/raw/Asemakaavoissa_suojellut_rakennukset_alue.geojson")
    mark = s.s_merk.fillna("").str.lower().str.replace(" ", "")
    s["group"] = np.select([mark.str.startswith(f"sr-{i}") for i in (1, 2, 3)], PROTECTION[:3], "other")
    b = buildings()
    numbers = b.dropna(subset=["i_pyraknro"]).assign(n=lambda d: d.i_pyraknro.astype(int).astype(str))[["key", "n"]]
    by_number = numbers.merge(s.drop(columns="geometry"), left_on="n", right_on="pys_raknro")
    hits = pd.concat([by_number, within(s)])
    hits = hits.assign(rank=hits.group.map(PROTECTION.index)).sort_values("rank").drop_duplicates("key")
    out = {}
    for r in hits.itertuples():
        year = f" ({r.voimaantulo_pvm.year})" if pd.notna(r.voimaantulo_pvm) else ""
        rule = str(r.kaavaselitys or "").strip().split(".")[0]
        out[r.key] = (r.group, dict(story=f"Local plan {r.kaava}{year}, marking {r.s_merk}.",
                                    story_fi=f"Asemakaava {r.kaava}{year}, merkintä {r.s_merk}" + (f": {rule}." if rule else ".")))
    return out


@layer(
    id="rky", section="Heritage", section_fi="Rakennusperintö", era="", era_fi="",
    title="Built heritage of national significance (RKY)",
    title_fi="Valtakunnallisesti merkittävät rakennetut kulttuuriympäristöt (RKY)",
    text=("The Finnish Heritage Agency's inventory of built cultural environments of national significance. "
          "A building lights up when it stands inside one of the areas; its card names the area and links to "
          "the inventory's description."),
    text_fi=("Museoviraston inventointi valtakunnallisesti merkittävistä rakennetuista kulttuuriympäristöistä. "
             "Rakennus näkyy, jos se on jonkin alueen sisällä. Kortti kertoo alueen nimen ja linkittää sen kuvaukseen."),
    caveat="Matched by location: a new building inside an area lights up too.",
    caveat_fi="Rakennukset on poimittu sijainnin perusteella, joten myös alueella oleva uudisrakennus näkyy.",
    source=("Finnish Heritage Agency, RKY", "Museovirasto, RKY", "https://www.rky.fi"),
    groups=[("rky", "Inside an RKY area", "RKY-alueella")],
)
def rky():
    a = gpd.read_file("data/raw/rky_alue.geojson")
    sub = a.nimi.fillna("").str.strip()
    a["area"] = a.kohdenimi.str.strip() + np.where(sub != "", ": " + sub, "")
    hits = within(a[["area", "url", "geometry"]]).drop_duplicates("key")
    return {r.key: ("rky", dict(story=r.area, source=r.url)) for r in hits.itertuples()}


@layer(
    id="wikipedia", section="Discover", section_fi="Löydä", era="", era_fi="",
    title="In Wikipedia", title_fi="Wikipediassa",
    text=("Buildings with an article in the Finnish or English Wikipedia, linked through Wikidata by their "
          "permanent building identifier. Click a name to fly there."),
    text_fi=("Rakennukset, joista on artikkeli suomen- tai englanninkielisessä Wikipediassa. Ne on yhdistetty "
             "Wikidatan kautta pysyvällä rakennustunnuksella. Napsauta nimeä, niin kartta vie rakennukseen."),
    source=("Wikidata, permanent building identifier (P3824)", "Wikidata, pysyvä rakennustunnus (P3824)",
            "https://www.wikidata.org/wiki/Property:P3824"),
    groups=[("article", "Wikipedia article", "Wikipedia-artikkeli")],
)
def wikipedia():
    w = pd.read_csv("data/raw/wd_buildings.csv", dtype=str).fillna("")
    w = w[(w.fi != "") | (w.en != "")]
    keys = set(buildings().key)
    out = {}
    for r in w.sort_values("labelFi").itertuples():
        if r.prt in keys and r.prt not in out:
            out[r.prt] = ("article", dict(name=r.labelEn or r.labelFi, name_fi=r.labelFi or r.labelEn))
    return out


@layer(
    id="residents", section="Discover", section_fi="Löydä", era="", era_fi="",
    title="Who lived here", title_fi="Kuka asui täällä",
    text=("Writers, artists, scientists and statesmen whose Finnish Wikipedia article names the Helsinki address where "
          "they lived, were born, died or worked, and the buildings Wikidata ties to a person. Pick a name to fly to the "
          "house; its card quotes the article."),
    text_fi=("Kirjailijat, taiteilijat, tiedemiehet ja valtiomiehet, joiden suomenkielinen Wikipedia-artikkeli kertoo "
             "helsinkiläisen osoitteen, jossa he asuivat, syntyivät, kuolivat tai työskentelivät, sekä rakennukset, jotka "
             "Wikidata liittää henkilöön. Napsauta nimeä, niin kartta vie taloon; kortti lainaa artikkelia."),
    caveat=("Found automatically in the articles and matched to today's address: house numbers have sometimes changed, "
            "and a house may have been rebuilt since; the card says so when the building is newer than the person."),
    caveat_fi=("Poimittu automaattisesti artikkeleista ja liitetty nykyiseen osoitteeseen: talonnumerot ovat joskus "
               "muuttuneet, ja talo on voitu rakentaa uudelleen; kortti kertoo, jos rakennus on henkilöä nuorempi."),
    source=("Finnish Wikipedia and Wikidata", "Suomenkielinen Wikipedia ja Wikidata", "https://fi.wikipedia.org"),
    groups=[("res", "Home of a well-known person", "Tunnetun henkilön koti")],
)
def residents():
    """s13_residents' rows, one note per building with everyone known to have lived there."""
    keys, out = set(buildings().key), {}
    for r in json.loads(Path("data/residents.json").read_text()):
        if r["key"] in keys:
            n = out.setdefault(r["key"], ("res", {"name": r["person"], "people": []}))[1]
            n["people"].append({k: r[k] for k in ("person", "born", "died", "desc", "desc_fi", "quote", "url", "links", "address")})
    return out


def main():
    b = buildings()
    c = to_local(np.c_[b.geometry.centroid.x, b.geometry.centroid.y]).round(1)
    where = dict(zip(b.key, c.tolist()))
    mask = np.zeros(len(b), dtype=np.uint64)
    catalogue, bit = [], 0
    for L in LAYERS:
        members = {k: v if isinstance(v, tuple) else (v, None) for k, v in L["source_fn"]().items()}
        group_of = b.key.map({k: g for k, (g, _) in members.items()})
        groups = []
        for key, label, label_fi in L["groups"]:
            hit = (group_of == key).to_numpy()
            mask[hit] |= np.uint64(1) << np.uint64(bit)
            years = b.year[hit].value_counts().sort_index()
            groups.append(dict(key=key, label=label, label_fi=label_fi, bit=bit, count=int(hit.sum()),
                               years={str(int(y)): int(n) for y, n in years.items()}))
            bit += 1
        assert bit <= 64, "out of layer bits"
        label, label_fi, url = L["source"]
        meta = {k: v for k, v in L.items() if k not in ("source_fn", "groups", "source")}
        meta.update(source=dict(label=label, label_fi=label_fi, url=url), groups=groups,
                    count=sum(g["count"] for g in groups),
                    notes={k: dict(n, at=where[k]) if n.get("name") else n for k, (_, n) in members.items() if n})
        catalogue.append(meta)
        print(f'{L["id"]:12s}', {g["key"]: g["count"] for g in groups})
    pd.DataFrame({"key": b.key, "lay0": (mask & np.uint64(0xFFFFFFFF)).astype(np.uint32),
                  "lay1": (mask >> np.uint64(32)).astype(np.uint32)}).to_parquet("data/layers.parquet")
    Path("web/data").mkdir(parents=True, exist_ok=True)
    Path("web/data/layers.json").write_text(json.dumps(catalogue, ensure_ascii=False, separators=(",", ":")))
    print(f'layers.json {Path("web/data/layers.json").stat().st_size // 1024} KB')


if __name__ == "__main__":
    main()
