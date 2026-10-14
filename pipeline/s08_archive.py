"""Archive photos from the Helsinki City Museum (HKM) in Finna, matched to buildings by address.

1. Every HKM image in Finna (fetched by s00_fetch) names its place, ending in an address:
   "…, Helsinki, Kluuvi Helsinki, Aleksanterinkatu 52"; sometimes several ("Läntinen Teatterikuja 1. Vilhonkatu 11.").
2. An address belongs to the building under the city's address point (or the nearest one within 15 m), else to the
   building whose register address it is; when several buildings share an address, the largest takes it.
3. Per building up to six photos, one a decade, oldest first. The museum's subject words and titles tell what a photo
   shows. Kept, in this order: buildings (a subject ending in "rakennukset", or architecture, facades, villas, blocks
   of flats) and the museum's documentation shots (the title is the address). Left out: interiors, street scenes
   (as often a painted utility box or a square as the building) and the people, events and shops that make up
   most of the rest. A photo naming one address beats one naming several,
   and none is older than the building (an older photo shows what stood there before).
4. Only openly licensed photos (PDM, CC0, CC BY 4.0). Each keeps its photographer and licence; the card credits the
   photographer and Helsingin kaupunginmuseo, and links the Finna record.
5. Shards web/data/archive/<nn>.json, keyed by a CRC-32 of the building id, that the page loads when a card needs them.
"""
import json
import re
import zlib
from pathlib import Path

import geopandas as gpd
import pandas as pd

OUT = Path("web/data/archive")
SHARDS = 64
PER_BUILDING = 6
OPEN = {"PDM", "CC0", "CC BY 4.0"}
# "Aleksanterinkatu 52", "Unioninkatu 33b", "Ruoholahdenkatu 24 D" (D is a staircase), "Aleksanterinkatu 14-18"
ADDRESS = re.compile(r"^(?P<street>[^\d,]+?)\s+(?P<num>\d+)(?P<letter>[a-zåäö]?)(?:\s*-\s*(?P<to>\d+))?\b")
# The museum's most common subject words on photos with an address (puurakennukset, kerrostalot, interiöörit …)
BUILDING = {"arkkitehtuuri", "julkisivut", "huvilat", "kerrostalot", "kerrostaloalueet", "kaupunkikuva"}
INSIDE = {"interiöörit", "sisätilat", "sisustus"}
INSIDE_TITLE = re.compile(r"sisänäkymä|sisäkuva|sisustus|interiööri")


def keys_of(street: str, num: str) -> list[str]:
    """Lookup keys of a street address: 'aleksanterinkatu 14', … for 14-18 (same side of the street), and 33b."""
    m = ADDRESS.match(f"{street} {num}".strip())
    if not m:
        return []
    s, n = m["street"].strip().lower(), int(m["num"])
    if m["letter"]:
        return [f"{s} {n}{m['letter'].lower()}"]
    to = int(m["to"]) if m["to"] and int(m["to"]) >= n else n
    return [f"{s} {k}" for k in range(n, to + 1, 2 if (to - n) % 2 == 0 else 1)]


def address_index(b: gpd.GeoDataFrame) -> dict[str, str]:
    b = b.assign(size=b.area * b.floors)
    pts = gpd.read_file("data/raw/Osoiteluettelo_piste_rekisteritiedot.geojson")[["katunimi", "osoitenumero", "geometry"]]
    pts = pts.to_crs(b.crs)
    hit = gpd.sjoin_nearest(pts, b[["key", "size", "geometry"]], max_distance=15, how="inner")
    rows = [(k, r.key, 0, r.size) for r in hit.itertuples() for k in keys_of(r.katunimi, str(r.osoitenumero or ""))]
    rows += [(k, r.key, 1, r.size) for r in b.itertuples() if isinstance(r.katunimi_suomi, str)
             for k in keys_of(r.katunimi_suomi, str(r.osoitenumero or ""))]
    # The address point first, then the largest building: an address on a shed and a house goes to the house.
    best = pd.DataFrame(rows, columns=["addr", "key", "src", "size"]).sort_values(["src", "size"], ascending=[True, False])
    return dict(best.drop_duplicates("addr")[["addr", "key"]].values)


def person(name):
    """'Rista, Simo' reads as 'Simo Rista'."""
    if not name:
        return None
    if "," in name:
        last, first = name.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return name.strip()


def addresses(record) -> list[str]:
    out = []
    for place in record.get("subjectPlaces") or []:
        parts = place.split(", ")
        if "Helsinki" not in parts:
            continue
        for a in re.split(r"\.\s*", parts[-1]):
            m = ADDRESS.match(a.strip())
            if m:
                out.append(f"{m['street'].strip().lower()} {m['num']}{(m['letter'] or '').lower()}")
    return out


def main():
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "year", "floors", "katunimi_suomi", "osoitenumero", "geometry"])
    index = address_index(b)
    built = dict(zip(b.key, b.year))
    print(len(index), "addresses on", len(set(index.values())), "buildings")

    seen = dropped = 0
    cands = {}
    for line in open("data/raw/finna_hkm.jsonl"):
        r = json.loads(line)
        seen += 1
        if r.get("imageRights", {}).get("copyright") not in OPEN or not r.get("images"):
            dropped += 1
            continue
        year = int(r["year"][:4]) if str(r.get("year", ""))[:4].isdigit() else None
        addrs = addresses(r)
        if year is None or not addrs:
            continue
        subjects = {s[0].lower() for s in r.get("subjects") or [] if s}
        maker = next((person(a["name"]) for a in r.get("nonPresenterAuthors") or [] if a.get("role") == "valokuvaaja"), None)
        item = dict(r=r["id"], y=year, m=maker, l=r["imageRights"]["copyright"])
        title = r.get("title", "").lower().strip(" .")
        if subjects & INSIDE or INSIDE_TITLE.search(title):
            continue
        building = bool(subjects & BUILDING) or any(w.endswith("rakennukset") for w in subjects)
        documented = any(title == a or title.startswith((a + ",", a + " ")) for a in addrs)
        if not (building or documented):
            continue
        rank = (not building, not documented, len(addrs) > 1)
        for k in {index[a] if a in index else index.get(a.rstrip("abcdefghijklmnopqrstuvwxyzåäö")) for a in addrs} - {None}:
            if year >= built[k]:
                cands.setdefault(k, []).append((rank, item))
    print(f"{seen} records, {dropped} without an open licence or an image; {sum(map(len, cands.values()))} matches")

    picks = {}
    for k, cs in cands.items():
        cs.sort(key=lambda c: (c[0], c[1]["y"]))
        decades, chosen = set(), []
        for _, item in cs:
            if item["y"] // 10 not in decades:
                decades.add(item["y"] // 10)
                chosen.append(item)
            if len(chosen) == PER_BUILDING:
                break
        picks[k] = sorted(chosen, key=lambda i: i["y"])
    print(len(picks), "buildings with archive photos,", sum(map(len, picks.values())), "photos")

    OUT.mkdir(parents=True, exist_ok=True)
    shards = [{} for _ in range(SHARDS)]
    for k, v in picks.items():
        shards[zlib.crc32(k.encode()) % SHARDS][k] = [{f: x for f, x in i.items() if x is not None} for i in v]
    for i, s in enumerate(shards):
        (OUT / f"{i:02d}.json").write_text(json.dumps(s, ensure_ascii=False, separators=(",", ":")))
    print(sum(f.stat().st_size for f in OUT.iterdir()) // 1024, "KB in", SHARDS, "shards")


if __name__ == "__main__":
    main()
