"""Who lived here: well-known people whose Finnish Wikipedia article names the Helsinki address where they lived,
were born, died or worked → data/residents.json (one row per person and building), for s05_layers.

1. People: those Wikidata ties to Helsinki (born, died, lived or worked there) with a Finnish article. (Searching the
   articles for every street name as well, as Amsterdam's map did, runs into Wikimedia's rate limits.)
2. Each article's text is split into sentences. A sentence counts when it is about living, moving, being born, dying
   or working somewhere (asui, muutti, syntyi, kuoli, koti, ateljee …), is about the person (their surname, or hän/he),
   names a Helsinki street and a house number, Helsinki or one of its districts is named in it or the three before,
   and no other town in it: many towns have a Kauppakatu. Burials are left out.
3. The address goes to a building through the city's address points, as the archive photos do (s08_archive).
4. The other way round: the Finnish articles of the buildings Wikidata links by VTJ-PRT, their sentences about living,
   being born or dying there ("Talossa asuivat mm. …"), and the people linked in them.
5. Wikidata's own links from a person to a building (residence or place of work, by its VTJ-PRT) are added; its birth
   and death places are nearly all hospitals, and are left out.
The sentence is kept as the source quote. House numbers have sometimes changed since, and the building standing at
an address may be newer than the person: the card says so then.
"""
import csv
import io
import json
import re
import time
from pathlib import Path

import geopandas as gpd
import requests

from .s08_archive import address_index, keys_of

RAW = Path("data/raw")
UA = {"User-Agent": "helsinki-by-building/0.1 (non-commercial building map)"}
WDQS, API = "https://query.wikidata.org/sparql", "https://fi.wikipedia.org/w/api.php"
VERBS = re.compile(r"\b(asu(i|ivat|nut|neet|ttiin|maan|essaan|ntonsa|nnossa|nnossaan|nto|nnon|nnolla|nnoissa|nnoksi)|"
                   r"muutti|muuttivat|muuttanut|muuttaneet|muutettuaan|muuttaessaan|asettui|asettuivat|syntyi|syntynyt|"
                   r"syntymäko\w*|kuoli|kuollut|menehtyi|koti|kotinsa|kotiinsa|kotonaan|kodissa\w*|kotitalo\w*|"
                   r"lapsuudenko\w*|kasvoi|ateljee\w*|työhuone\w*|vastaanot\w*|toimisto\w*|vuokrasi|"
                   r"huvila\w*|vietti\w*|piileskel\w*|piilotteli|asuinpaik\w*|kotipaik\w*)\b", re.I)
# A sentence about designing or building a house is about the architect or the builder, not about living there
DESIGNED = re.compile(r"\b(suunnitte\w*|rakennutt\w*)", re.I)
# In a building's own article: living or having one's studio there; being born or dying there is said of other
# things too ("Se syntyi … kokoelmasta"). The sentence must name the building, by its own name or as the house, and not
# a neighbour's.
LIVED = re.compile(r"\b(asu(i|ivat|nut|neet|neita|ttiin|kkaa\w*|kkai\w*|kas)|asuntonaan|virka-asunto\w*|kotinaan|ateljee\w*)\b", re.I)
HOUSE = r"\b(talo\w*|rakennu\w*|huvila\w*|kartano\w*|linna\w*|hotelli\w*|siellä|täällä|tässä)\b"
NEXT_DOOR = re.compile(r"\b(naapuri\w*|viere\w*|lähellä|vastapäät\w*)", re.I)
# A person named in the genitive is someone's, not the resident ("Bobrikovin leikannut kirurgi", "Edelfeltin sisaret"),
# unless it is their home ("Leinon koti")
HOME = r"(koti\w*|kodi\w*|asunto\w*|asunno\w*|ateljee\w*|perhe\w*|työhuone\w*)"
# … or introduced as someone's kin a few words before: "joiden isä oli arkkitehti [[X]] ja veli [[Y]]"
KIN = re.compile(r"\b(isä|isänsä|äiti|äitinsä|veli|veljensä|sisar|sisarensa|siskonsa|vaimo\w*|puoliso\w*|miehensä|poika|poikansa|tytär|"
                 r"tyttärensä|lapse\w*|appi|anoppi|setä|eno|täti|isoisä\w*|isoäiti\w*)\s+(?:\S+\s+){0,3}$", re.I)
SELF = re.compile(r"\b(hän|he|perhe|perheineen|pariskunta)\b", re.I)
BURIED = re.compile(r"\b(haudat\w*|hauta\w*|hautaus\w*|siunat\w*)", re.I)
# Other towns, in any case ending: a Kauppakatu or a Linnankatu there is not Helsinki's.
ELSEWHERE = re.compile(r"\b(Turu|Turk|Tamper|Viipur|Oulu|Ouluu|Vaas|Pori|Porin|Jyväskyl|Kuopi|Lahde|Lahti|Porvo|Hämeenlinn|"
                       r"Tukholm|Pietar|Berliin|Pariisi|Lontoo|Espoo|Espoon|Vantaa|Vantaan|Kauniai|Tallin|Kotka|Kotkan|"
                       r"Lappeenrann|Kokkola|Joensuu|Mikkel|Savonlinn|Rauma|Seinäjo|Kajaan|Rovaniem|Hang|Loviis|Tammisaar|"
                       r"Kristiinankaupun|Uusikaupun|Raahe|Iisalm|Kemi|Tornio|Sortavala|Käkisalm|Hamin|Heinol|Riihimä|Hyvinkää|Hanko)")
# Wikidata's links from a person to a building: residence and place of work. Birth and death places are left out: they
# are nearly all hospitals.
WHY = {"P551": "Wikidata records this building as their residence.",
       "P937": "Wikidata records this building as their place of work."}
FIELDS = "?p ?label ?article ?descFi ?descEn ?born ?died ?links"
DETAILS = """?article schema:about ?p ; schema:isPartOf <https://fi.wikipedia.org/> . ?p wikibase:sitelinks ?links .
  OPTIONAL { ?p rdfs:label ?label FILTER(LANG(?label) = "fi") }
  OPTIONAL { ?p schema:description ?descFi FILTER(LANG(?descFi) = "fi") }
  OPTIONAL { ?p schema:description ?descEn FILTER(LANG(?descEn) = "en") }
  OPTIONAL { ?p wdt:P569 ?born } OPTIONAL { ?p wdt:P570 ?died }"""


def sparql(q: str) -> list[dict]:
    for attempt in range(5):
        r = requests.post(WDQS, data={"query": q}, headers={**UA, "Accept": "text/csv"}, timeout=600)
        if r.ok:
            return list(csv.DictReader(io.StringIO(r.text)))
        time.sleep(5 * 2 ** attempt)
    r.raise_for_status()


def named(article: str) -> str:
    """A person as their Finnish article names them, not Wikidata's formal label: 'Annie Edelfelt', not 'Alexandra Edelfelt'."""
    return requests.utils.unquote(article.rsplit("/wiki/", 1)[1]).replace("_", " ").split(" (")[0]


def lived(desc: str) -> str:
    """Wikidata's description less the years it often ends on, which the card gives already: '… arkkitehti (1898–1976)'."""
    return re.sub(r"\s*\(\s*\d{3,4}\s*[–-]\s*\d{0,4}\s*\)\s*$", "", desc or "")


def unique(rows: list[dict]) -> dict:
    """{article title: person}, the first row of each (a person with two birth dates comes twice)."""
    out = {}
    for v in rows:
        out.setdefault(requests.utils.unquote(v["article"].rsplit("/wiki/", 1)[1]).replace("_", " "), v)
    return out


def people() -> dict:
    """People Wikidata ties to Helsinki, with a Finnish article: their articles first, then the details a few hundred at
    a time (all at once the query times out)."""
    rows = sparql("""SELECT DISTINCT ?article WHERE { VALUES ?prop { wdt:P19 wdt:P20 wdt:P551 wdt:P937 }
      ?p ?prop wd:Q1757 ; wdt:P31 wd:Q5 . ?article schema:about ?p ; schema:isPartOf <https://fi.wikipedia.org/> . }""")
    return humans([requests.utils.unquote(r["article"].rsplit("/wiki/", 1)[1]).replace("_", " ") for r in rows])


def humans(titles: list[str]) -> dict:
    """The titles whose Wikidata item is a person."""
    rows = []
    for i in range(0, len(titles), 300):
        vals = " ".join(f'<https://fi.wikipedia.org/wiki/{requests.utils.quote(t.replace(" ", "_"), safe="")}>' for t in titles[i:i + 300])
        rows += sparql(f"SELECT {FIELDS} WHERE {{ VALUES ?article {{ {vals} }} ?p wdt:P31 wd:Q5 . {DETAILS} }}")
    return unique(rows)


def wikitexts(titles: list[str], cache: Path = RAW / "fiwiki_people.json") -> dict:
    """{title: wikitext}, cached; one request at a time, 50 articles each, as Wikimedia's rate limits ask."""
    texts = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [t for t in titles if t not in texts]
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        for attempt in range(6):
            r = requests.get(API, headers=UA, timeout=120, params=dict(action="query", prop="revisions", rvprop="content",
                             rvslots="main", format="json", formatversion=2, redirects=1, maxlag=5, titles="|".join(chunk)))
            if r.ok and r.headers.get("content-type", "").startswith("application/json") and "query" in r.json():
                break
            time.sleep(int(r.headers.get("Retry-After") or 0) or 15 * 2 ** attempt)
        else:
            r.raise_for_status()
        time.sleep(1)
        d = r.json()["query"]
        back = {n["to"]: n["from"] for n in d.get("normalized", []) + d.get("redirects", [])}
        for p in d["pages"]:
            t = p["title"]
            while t in back:
                t = back[t]
            texts[t] = p["revisions"][0]["slots"]["main"]["content"] if p.get("revisions") else ""
        if i % 1000 == 0:
            cache.write_text(json.dumps(texts, ensure_ascii=False))
    cache.write_text(json.dumps(texts, ensure_ascii=False))
    return texts


def clean(wt: str) -> str:
    """Wikitext to plain sentences; headings and list lines become sentence breaks, so a quote never spans them."""
    wt = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>|<!--.*?-->", "", wt, flags=re.S)
    for _ in range(3):
        wt = re.sub(r"\{\{[^{}]*\}\}", "", wt)
    wt = re.sub(r"\[\[(?:Tiedosto|Kuva|File|Image|Luokka|Category):[^\[\]]*(?:\[\[[^\]]*\]\][^\[\]]*)*\]\]", "", wt, flags=re.I)
    wt = re.sub(r"^(?:Tiedosto|Kuva|File|Image):[^|\n]*\|", "", wt, flags=re.M | re.I)  # a gallery's lines: the caption stays
    wt = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", wt)
    wt = re.sub(r"\[https?://\S+\s*([^\]]*)\]", r"\1", wt)
    wt = re.sub(r"^=+[^=\n]*=+\s*$", ". ", wt, flags=re.M)
    wt = re.sub(r"^[*#:;|!{].*$", ". ", wt, flags=re.M)
    wt = re.sub(r"<[^>]+>|'{2,}", "", wt)
    return re.sub(r"\s+", " ", wt)


# Abbreviations a sentence goes on after: "asuivat mm. Leino", "(s. 1865)"
ABBREV = r"".join(rf"(?<!\b{a}\.)" for a in ("mm", "ym", "ns", "esim", "yms", "jne", "tms", "vrt", "ks", "ts", "eli", "tri", "prof"))


def sentences(text: str) -> list[str]:
    # before a capital, a number or a link, not after an initial ("J. L. Runeberg", "s. 1865") or an abbreviation;
    # "1. tammikuuta" goes on in lower case
    return re.split(rf"(?<![\s(⟦][A-ZÅÄÖa-zåäö]\.){ABBREV}(?<=[.!?])\s+(?=[A-ZÅÄÖ0-9⟦])", " " + text)


def surname_stem(label: str) -> str:
    """'Jean Sibelius' → 'sibeli': the surname less its last letters, which Finnish inflects (Sibeliuksen)."""
    s = label.split(" (")[0].split()[-1].lower() if label else ""
    return s[:max(3, len(s) - 2)]


def found_in(text: str, stem: str, address: re.Pattern, here: re.Pattern = re.compile(r"Helsin")) -> list[tuple[str, str]]:
    """[(address, quote)]: the sentences of an article that place its person at a Helsinki address. `here` finds
    Helsinki or its districts in the sentence or the three before."""
    out, ss = [], sentences(text)
    for i, s in enumerate(ss):
        if (len(s) < 400 and VERBS.search(s) and not BURIED.search(s) and not DESIGNED.search(s)
                and here.search(" ".join(ss[max(0, i - 3):i + 1]))
                and not ELSEWHERE.search(s) and (stem and re.search(rf"\b{re.escape(stem)}", s.lower()) or SELF.search(s))):
            for m in address.finditer(s):
                out.append((f"{m['street']} {m['num']}", s.strip()))
    return out


def districts() -> re.Pattern:
    """Helsinki and its districts in any case form: a name less its last letter, or two for a long one, at a word's start
    (Kulosaari → Kulosaar…: Kulosaareen; Kruununhaka → Kruununha…: Kruununhaassa)."""
    n = gpd.read_file(RAW / "Nimisto_piste_rekisteritiedot.geojson")
    names = {x for x in n.nimi_suomi[n.laji_selite.isin(["Kaupunginosa", "Osa-alue", "Peruspiiri"])].dropna() if len(x) >= 5}
    stems = sorted({x[:-1] if len(x) <= 7 else x[:-2] for x in names} | {"Helsin"}, key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(map(re.escape, stems)) + ")")


def in_buildings(articles: dict) -> list[tuple[str, str, str]]:
    """[(building key, linked title, quote)]: the people linked in a building's own article ({key: (title, wikitext)})
    in a sentence about living there that names the house; not one linked as someone's kin ("[[X]]n tytär")."""
    out = []
    for key, (title, wt) in articles.items():
        own = re.compile(rf"{HOUSE}|\b{re.escape(title.split(' (')[0].lower()[:max(5, len(title) - 2)])}", re.I)
        wt = re.sub(r"\[\[(?!(?:Tiedosto|Kuva|File|Image|Luokka|Category):)([^|\]#]+)(?:\|([^\]]*))?\]\]",
                    lambda m: f"⟦{m[1].strip()[:1].upper()}{m[1].strip()[1:]}⟧{m[2] or m[1]}", wt, flags=re.I)
        for s in sentences(clean(wt)):
            if (len(s) < 400 and LIVED.search(s) and not BURIED.search(s) and not DESIGNED.search(s)
                    and not NEXT_DOOR.search(s) and own.search(re.sub(r"⟦[^⟧]*⟧", "", s))):
                quote = re.sub(r"⟦[^⟧]*⟧", "", s).strip()
                for m in re.finditer(r"⟦([^⟧]+)⟧", s):
                    t = m[1]
                    if KIN.search(re.sub(r"⟦[^⟧]*⟧", "", s[:m.start()])):
                        continue
                    last = re.escape(t.split(" (")[0].split()[-1])
                    owner = re.search(rf"⟦{re.escape(t)}⟧[^⟦]{{0,40}}?\b{last}\w*?:?n\b(\s+\w+)?", s)
                    if not owner or re.match(rf"\s+{HOME}", owner[1] or ""):
                        out.append((key, t, quote))
    return out


def main():
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "year", "floors", "gone", "katunimi_suomi", "osoitenumero", "geometry"])
    index = address_index(b[b.gone == 0])
    pts = gpd.read_file(RAW / "Osoiteluettelo_piste_rekisteritiedot.geojson")
    streets = sorted({s for s in pts.katunimi.dropna() if len(s) > 4}, key=len, reverse=True)
    # "Bulevardi 5", "Bulevardi 5:ssä", "Bulevardi 5–7", "Unioninkatu 33b"; a capital after the number is a staircase
    address = re.compile(r"\b(?P<street>" + "|".join(map(re.escape, streets)) + r")\s+(?P<num>\d{1,3}[a-zåäö]?)\b")

    ppl = people()
    print(len(ppl), "people")
    texts = wikitexts(sorted(ppl))
    print(len(texts), "articles")
    here = districts()

    found = []
    for title, p in ppl.items():
        seen = set()
        for addr, quote in found_in(clean(texts.get(title, "")), surname_stem(p["label"] or title), address, here):
            key = index.get(next(iter(keys_of(*addr.rsplit(" ", 1))), ""))
            if key and key not in seen:
                seen.add(key)
                found.append(dict(key=key, address=addr, person=named(p["article"]), wikidata=p["p"], url=p["article"],
                                  desc=lived(p["descEn"]), desc_fi=lived(p["descFi"]), born=p["born"][:4], died=p["died"][:4],
                                  links=int(p["links"]), quote=quote[:400]))
    # The people the buildings' own articles say lived in them
    keys = set(b.key[b.gone == 0])
    where = (b.katunimi_suomi.fillna("") + " " + b.osoitenumero.fillna("")).str.strip()
    where = dict(zip(b.key, where))
    titles = {requests.utils.unquote(r["fi"].rsplit("/wiki/", 1)[1]).replace("_", " "): r["prt"]
              for r in csv.DictReader(open(RAW / "wd_buildings.csv")) if r["fi"] and r["prt"] in keys}
    texts = wikitexts(sorted(titles), RAW / "fiwiki_buildings.json")
    hits = in_buildings({titles[t]: (t, wt) for t, wt in texts.items() if t in titles})
    linked = humans(sorted({t for _, t, _ in hits}))
    for key, t, quote in hits:
        if (p := linked.get(t)):
            found.append(dict(key=key, address=where.get(key, ""), person=named(p["article"]), wikidata=p["p"], url=p["article"],
                              desc=lived(p["descEn"]), desc_fi=lived(p["descFi"]), born=p["born"][:4], died=p["died"][:4],
                              links=int(p["links"]), quote=quote[:400]))
    print(len(titles), "building articles;", len(hits), "people linked in them,", sum(t in linked for _, t, _ in hits), "of them people")
    # Wikidata's own links from a person to a building, by its VTJ-PRT
    for r in sparql(f"""SELECT ?prop ?prt {FIELDS} WHERE {{ VALUES ?prop {{ wdt:P551 wdt:P937 }}
                       ?p ?prop ?b ; wdt:P31 wd:Q5 . ?b wdt:P3824 ?prt . {DETAILS} }}"""):
        if r["prt"] in keys:
            found.append(dict(key=r["prt"], address=where.get(r["prt"], ""), person=named(r["article"]), wikidata=r["p"], url=r["article"],
                              desc=lived(r["descEn"]), desc_fi=lived(r["descFi"]), born=r["born"][:4], died=r["died"][:4],
                              links=int(r["links"]), quote=WHY[r["prop"].rsplit("/", 1)[1]]))
    uniq = {}
    for f in found:  # one row per person and building; Wikipedia's sentences come first, so they win
        uniq.setdefault((f["key"], f["wikidata"]), f)
    found = sorted(uniq.values(), key=lambda f: -f["links"])
    Path("data/residents.json").write_text(json.dumps(found, ensure_ascii=False, indent=1))
    print(len(found), "rows;", len({f["wikidata"] for f in found}), "people;", len({f["key"] for f in found}), "buildings")


if __name__ == "__main__":
    main()
