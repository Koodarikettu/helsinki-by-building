"""Names, photos and article extracts for buildings that have a Wikidata item (P3824, the VTJ-PRT).

wiki.json: list of {label, label_fi, wiki: {lang, url, extract} | null, wiki_fi: … | null, architects, styles,
styles_fi, image: {thumb, page, artist, license, licenseUrl} | null}. data/wiki_index.parquet maps each building to
its entry. Photos are Wikimedia Commons files with their author and licence, as the Commons API reports them.
"""
import html
import json
import re
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests

from .s00_fetch import UA


def get_json(url, params):
    """GET with backoff: the Wikimedia APIs answer bursts with 429 and an HTML page, sometimes with Retry-After."""
    for attempt in range(8):
        r = requests.get(url, params=params, headers=UA, timeout=60)
        if r.ok and r.headers.get("content-type", "").startswith("application/json"):
            time.sleep(1)
            return r.json()
        time.sleep(int(r.headers.get("retry-after", 0)) or 5 * 2 ** attempt)
    r.raise_for_status()
    raise RuntimeError(f"{url}: {r.status_code} {r.text[:200]}")


def batched(xs, n):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def extracts(lang, titles):
    out = {}
    for chunk in batched(sorted(titles), 20):
        r = get_json(f"https://{lang}.wikipedia.org/w/api.php", {
            # A length, not sentences: the API ends Finnish sentences at abbreviations ("aik.", "ruots.").
            "action": "query", "format": "json", "prop": "extracts", "exintro": 1, "explaintext": 1,
            "exchars": 450, "exlimit": 20, "redirects": 1, "titles": "|".join(chunk)})
        norm = {n["to"]: n["from"] for n in r["query"].get("normalized", []) + r["query"].get("redirects", [])}
        for p in r["query"]["pages"].values():
            t = p.get("title")
            while t in norm:
                t = norm[t]
            if p.get("extract"):
                out[t] = p["extract"].strip()
    return out


def strip_html(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or ""))).strip()


def artist_of(meta):
    a = strip_html(meta.get("Artist", {}).get("value"))[:80]
    if not a or re.match(r"^\d{1,2}:\d{2}|^\d{1,2} \w+ \d{4}|^\d{4}-\d{2}-\d{2}|^unknown", a, re.I):
        return None
    return a


def images(files):
    out = {}
    for chunk in batched(sorted(files), 20):
        r = get_json("https://commons.wikimedia.org/w/api.php", {
            "action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata",
            "iiurlwidth": 500, "titles": "|".join("File:" + f for f in chunk)})
        norm = {n["to"]: n["from"] for n in r["query"].get("normalized", [])}
        for p in r["query"]["pages"].values():
            ii = (p.get("imageinfo") or [None])[0]
            if not ii:
                continue
            m = ii.get("extmetadata", {})
            key = norm.get(p["title"], p["title"])[5:]
            out[key] = dict(thumb=ii.get("thumburl"), page=ii.get("descriptionurl"),
                            artist=artist_of(m),
                            license=m.get("LicenseShortName", {}).get("value"),
                            licenseUrl=m.get("LicenseUrl", {}).get("value"))
    return out


def title_of(url):
    return unquote(url.rsplit("/wiki/", 1)[1]).replace("_", " ")


def main():
    keys = set(pd.read_parquet("data/buildings.parquet", columns=["key"]).key)
    rows = pd.read_csv("data/raw/wd_buildings.csv", dtype=str).fillna("")
    rows = rows[rows.prt.isin(keys)]
    items = {}
    for r in rows.itertuples():
        it = items.setdefault(r.i, dict(keys=set(), label=r.labelEn or r.labelFi, label_fi=r.labelFi or r.labelEn,
                                        en=r.en, fi=r.fi, image=None,
                                        architects=[a for a in r.architects.split("|") if a],
                                        styles=[s for s in r.stylesEn.split("|") if s],
                                        styles_fi=[s for s in r.stylesFi.split("|") if s]))
        it["keys"].add(r.prt)
        if r.image and not it["image"]:
            it["image"] = unquote(r.image.rsplit("/", 1)[1]).replace("_", " ")

    ex_en = extracts("en", {title_of(i["en"]) for i in items.values() if i["en"]})
    ex_fi = extracts("fi", {title_of(i["fi"]) for i in items.values() if i["fi"]})
    imgs = images({i["image"] for i in items.values() if i["image"]})
    print(f"{len(items)} items; extracts en {len(ex_en)}, fi {len(ex_fi)}; images {len(imgs)}")

    article = lambda it, lang, ex: dict(lang=lang, url=it[lang], extract=ex.get(title_of(it[lang]))) if it[lang] else None
    entries, index = [], {}
    # Rank: an article first, then a photo, so a building with two items shows the richer one.
    for it in sorted(items.values(), key=lambda i: (not (i["en"] or i["fi"]), not i["image"])):
        k = len(entries)
        entries.append(dict(label=it["label"], label_fi=it["label_fi"],
                            wiki=article(it, "en", ex_en) or article(it, "fi", ex_fi), wiki_fi=article(it, "fi", ex_fi),
                            architects=it["architects"], styles=it["styles"], styles_fi=it["styles_fi"],
                            image=imgs.get(it["image"]) if it["image"] else None))
        for key in it["keys"]:
            index.setdefault(key, k)
    Path("web/data").mkdir(parents=True, exist_ok=True)
    Path("web/data/wiki.json").write_text(json.dumps(entries, ensure_ascii=False, separators=(",", ":")))
    pd.DataFrame({"key": list(index), "wk": list(index.values())}).to_parquet("data/wiki_index.parquet")
    print(len(entries), "entries for", len(index), "buildings;", Path("web/data/wiki.json").stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
