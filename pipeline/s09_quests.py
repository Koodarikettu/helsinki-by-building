"""Resolve every quest step (pipeline/quests.py) to its buildings and check it; write web/data/quests.json.

A step is dropped, and its quest with it, when: an article lacks a checked string; the place is not found; a year
step's year is not the map's year for the building (within one year); a photo clue has no photo. Articles are cached
in data/raw/articles.json; delete it to check against today's Wikipedia.
"""
import json
from functools import cache
from pathlib import Path
from urllib.parse import quote, unquote

import geopandas as gpd
import pandas as pd

from .quests import QUESTS
from .s06_wiki import get_json
from .s08_archive import OPEN, address_index, keys_of, person

CACHE = Path("data/raw/articles.json")


@cache
def articles() -> dict:
    return json.loads(CACHE.read_text()) if CACHE.exists() else {}


def article(ref):
    """'fi:Title' → (plain text, url) of the whole article."""
    a = articles()
    if ref not in a:
        lang, title = ref.split(":", 1)
        r = get_json(f"https://{lang}.wikipedia.org/w/api.php", {
            "action": "query", "format": "json", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
        p = next(iter(r["query"]["pages"].values()))
        a[ref] = dict(text=p.get("extract", ""),
                      url=f"https://{lang}.wikipedia.org/wiki/{quote(p.get('title', title).replace(' ', '_'))}")
        CACHE.write_text(json.dumps(a, ensure_ascii=False))
    return a[ref]["text"], a[ref]["url"]


def main():
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "year", "floors", "katunimi_suomi", "osoitenumero", "geometry"])
    years = dict(zip(b.key, b.year))
    index = address_index(b)
    wd = pd.read_csv("data/raw/wd_buildings.csv", dtype=str).fillna("")
    by_article = {}
    for r in wd.itertuples():
        for lang in ("fi", "en"):
            url = getattr(r, lang)
            if url and r.prt in years:
                by_article.setdefault(f"{lang}:{unquote(url.rsplit('/wiki/', 1)[1]).replace('_', ' ')}", set()).add(r.prt)
    wiki = json.load(open("web/data/wiki.json"))
    wk = pd.read_parquet("data/wiki_index.parquet").set_index("key").wk
    finna = {}
    for line in open("data/raw/finna_hkm.jsonl"):
        r = json.loads(line)
        maker = next((person(a["name"]) for a in r.get("nonPresenterAuthors") or [] if a.get("role") == "valokuvaaja"), None)
        finna[r["id"]] = (r.get("imageRights", {}).get("copyright"), maker)

    def where(at):
        kind, _, ref = at.partition(":")
        if kind == "wd":
            return sorted(by_article.get(ref, ()))
        if kind == "addr":
            street, _, num = ref.rpartition(" ")
            return [index[k] for k in keys_of(street, num)[:1] if k in index]
        raise ValueError(at)

    out, problems = [], []
    for q in QUESTS:
        steps = []
        for i, s in enumerate(q["steps"]):
            here = f'{q["id"]} {i + 1}'
            keys = where(s["at"])
            if not keys:
                problems.append(f"{here}: nothing at {s['at']}")
                continue
            missing = [(ref, c) for ref, cs in s["checks"] for c in cs if c.lower() not in article(ref)[0].lower()]
            if missing:
                problems.append(f"{here}: not in the article {missing}")
                continue
            if s["kind"] == "year" and not any(abs(years[k] - s["year"]) <= 1 for k in keys):
                problems.append(f"{here}: map says {sorted({int(years[k]) for k in keys})}, step says {s['year']}")
                continue
            step = {k: v for k, v in s.items() if k not in ("checks", "at") and v is not None}
            step["bags"] = keys  # the viewer's name for building ids
            step["sources"] = sorted({article(ref)[1] for ref, _ in s["checks"]})
            if s.get("clue") == "today":
                img = next((wiki[wk[k]]["image"] for k in keys if k in wk.index and wiki[wk[k]].get("image")), None)
                if not img:
                    problems.append(f"{here}: no photo")
                    continue
                step["clue"] = dict(thumb=img["thumb"], page=img.get("page"), artist=img.get("artist"),
                                    license=img.get("license"))
            elif isinstance(s.get("clue"), dict):
                licence, maker = finna.get(s["clue"]["id"], (None, None))
                if licence not in OPEN:
                    problems.append(f"{here}: archive photo {s['clue']['id']} missing or not openly licensed")
                    continue
                step["clue"] = dict(s["clue"], l=licence, **({"m": maker} if maker else {}))
            steps.append(step)
        if len(steps) == len(q["steps"]):
            out.append(dict({k: v for k, v in q.items() if k != "steps"}, steps=steps))
        print(f'{q["id"]:14s} level {q["level"]}  {len(steps)}/{len(q["steps"])}')
    for p in problems:
        print("problem:", p)
    Path("web/data/quests.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(len(out), "quests")


if __name__ == "__main__":
    main()
