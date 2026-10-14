"""Pack buildings into 600 m binary tiles + a city config JSON.

Local frame: metres from Senaatintori, x east, z south (three.js, y up).
Tile layout (little-endian, every section 4-byte aligned):
  header  u32 magic, nB, nP, nR, nV; f32 originX, originZ
  B       u32 gid[nB]; i16 year[nB]; i16 gone[nB] (year of demolition, 0 if standing); u8 flag[nB]; u8 period[nB]; u8 floors[nB]; u8 energy[nB] (label, 1–7 = G…A, 0 = none);
          u8 solar[nB] (yearly solar potential: 0 none, 1 zero, 2… up the steps in SOLAR_MWH);
          u32 lay0[nB]; u32 lay1[nB] (context layer bits, see s05_layers); u32 partStart[nB+1]
  P       f32 height[nP]; u32 ringStart[nP+1]
  R       u32 vertStart[nR+1]; u8 hole[nR]
  V       i16 xz[2*nV], decimetres from the tile origin
"""
import json
import struct
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

from .codes import JULKISIVU, KAYTTARK, RAKEAINE, TYYPPI
from .periods import PERIODS

ORIGIN = Transformer.from_crs(4326, 3879, always_xy=True).transform(24.9527, 60.1694)  # Senaatintori, ETRS-GK25
TILE = 600.0
SIMPLIFY = 0.25
OUT = Path("web/data")
MAGIC = 0x35424241  # 'ABB5'
SOLAR_MWH = [5, 10, 25, 50, 100, 250, 500]  # steps of the solar colouring, MWh a year
# Written by steps not run yet (street names, facts, quests); until then the map shows none.
STUBS = {"labels.json": "[]", "facts.json": "{}"}


def pad4(b: bytes) -> bytes:
    return b + b"\0" * (-len(b) % 4)


def to_local(coords: np.ndarray) -> np.ndarray:
    return np.c_[coords[:, 0] - ORIGIN[0], -(coords[:, 1] - ORIGIN[1])]


def rings_of(geom):
    polys = getattr(geom, "geoms", [geom])
    for poly in polys:
        if poly.is_empty:
            continue
        yield shapely.get_coordinates(poly.exterior)[:-1], 0
        for hole in poly.interiors:
            yield shapely.get_coordinates(hole)[:-1], 1


def pack_tile(origin, rows):
    gid, year, gone, flag, period, floors, energy, solar, lay0, lay1, part_start = [], [], [], [], [], [], [], [], [], [], [0]
    heights, ring_start, vert_start, holes, verts = [], [0], [0], [], []
    for b in rows:
        gid.append(b["gid"]); year.append(b["year"]); gone.append(b["gone"]); flag.append(b["flag"])
        period.append(b["period"]); floors.append(b["floors"])
        lay0.append(b["lay0"]); lay1.append(b["lay1"]); energy.append(b["energy"]); solar.append(b["solar"])
        for h, geom in b["parts"]:
            heights.append(h)
            for ring, hole in rings_of(geom):
                if len(ring) < 3:
                    continue
                loc = (to_local(ring) - origin) * 10
                verts.append(np.round(loc).astype(np.int16))
                holes.append(hole)
                vert_start.append(vert_start[-1] + len(ring))
            ring_start.append(len(holes))
        part_start.append(len(heights))
    nB, nP, nR = len(gid), len(heights), len(holes)
    V = np.concatenate(verts) if verts else np.zeros((0, 2), np.int16)
    out = struct.pack("<5I2f", MAGIC, nB, nP, nR, len(V), *origin)
    out += pad4(np.array(gid, "<u4").tobytes())
    out += pad4(np.array(year, "<i2").tobytes())
    out += pad4(np.array(gone, "<i2").tobytes())
    out += pad4(np.array(flag, "u1").tobytes())
    out += pad4(np.array(period, "u1").tobytes())
    out += pad4(np.array(floors, "u1").tobytes())
    out += pad4(np.array(energy, "u1").tobytes())
    out += pad4(np.array(solar, "u1").tobytes())
    out += np.array(lay0, "<u4").tobytes() + np.array(lay1, "<u4").tobytes()
    out += pad4(np.array(part_start, "<u4").tobytes())
    out += pad4(np.array(heights, "<f4").tobytes())
    out += pad4(np.array(ring_start, "<u4").tobytes())
    out += pad4(np.array(vert_start, "<u4").tobytes())
    out += pad4(np.array(holes, "u1").tobytes())
    out += pad4(V.astype("<i2").tobytes())
    return out


def main():
    b = gpd.read_parquet("data/buildings.parquet").merge(pd.read_parquet("data/layers.parquet"), on="key", how="left")
    b[["lay0", "lay1"]] = b[["lay0", "lay1"]].fillna(0)  # demolished buildings are in no layer
    b = b.merge(pd.read_parquet("data/energy.parquet"), on="key", how="left")
    b["energy"] = b.eclass.fillna(0).astype(int)
    mwh = b.solar_kwh / 1000
    b["solar"] = np.where(mwh.isna(), 0, np.where(mwh > 0, 2 + np.searchsorted(SOLAR_MWH, mwh.fillna(0)), 1))
    # One part per polygon: the viewer roofs a part as a single outline with holes.
    geoms = shapely.simplify(shapely.make_valid(b.geometry.values), SIMPLIFY, preserve_topology=True)
    parts = [[(h, g) for g in getattr(geom, "geoms", [geom]) if g.geom_type == "Polygon" and not g.is_empty]
             for h, geom in zip(b.height, geoms)]

    c = to_local(np.c_[b.geometry.centroid.x, b.geometry.centroid.y])
    b["tx"] = np.floor(c[:, 0] / TILE).astype(int)
    b["tz"] = np.floor(c[:, 1] / TILE).astype(int)

    (OUT / "tiles").mkdir(parents=True, exist_ok=True)
    index = []
    for (tx, tz), grp in b.groupby(["tx", "tz"]):
        origin = np.array([tx * TILE, tz * TILE])
        rows = [dict(gid=r.Index, year=int(r.year), gone=int(r.gone), flag=int(r.date_flag),
                     period=int(r.period), floors=int(r.floors),
                     lay0=int(r.lay0), lay1=int(r.lay1), energy=int(r.energy), solar=int(r.solar), parts=parts[r.Index])
                for r in grp.itertuples()]
        data = pack_tile(origin, rows)
        name = f"{tx}_{tz}.bin"
        (OUT / "tiles" / name).write_bytes(data)
        cx, cz = origin + TILE / 2
        index.append(dict(file=name, tx=int(tx), tz=int(tz), n=len(rows), bytes=len(data),
                          dist=round(float(np.hypot(cx, cz)))))
    index.sort(key=lambda t: t["dist"])

    # Bundle tiles into a few packs, nearest Senaatintori first, so the city loads centre-out in few requests.
    packs, n_packs = [], 8
    per = -(-len(index) // n_packs)
    for k in range(n_packs):
        chunk = index[k * per:(k + 1) * per]
        if not chunk:
            break
        name, offset, blob = f"pack{k}.bin", 0, bytearray()
        for t in chunk:
            data = (OUT / "tiles" / t["file"]).read_bytes()
            t.update(pack=name, offset=offset, length=len(data))
            blob += data; offset += len(data)
        (OUT / name).write_bytes(blob)
        packs.append(name)

    # Per-building lookup for hover: height (dm), sources (bit 1 floors assumed, bit 2 height from floors), date flag,
    # years, floors, codes into the lists in the config.
    attrs = np.zeros(len(b), dtype=[("h", "<u2"), ("fsrc", "u1"), ("flag", "u1"), ("year", "<i2"), ("orig", "<i2"),
                                    ("lay0", "<u4"), ("lay1", "<u4"), ("wk", "<i4"), ("use", "u1"), ("floors", "u1"), ("mat", "u1"),
                                    ("fac", "u1"), ("x", "<f4"), ("z", "<f4"), ("gone", "<i2"),
                                    ("eclass", "u1"), ("ever", "u1"), ("eluku", "<u2"), ("solar", "<i4"), ("panel", "<u2")])
    attrs["h"] = np.round(b.height * 10).clip(0, 65535)
    attrs["fsrc"] = b.floors_src + 2 * b.height_src; attrs["flag"] = b.date_flag; attrs["floors"] = b.floors
    attrs["year"] = b.year; attrs["orig"] = b.orig; attrs["gone"] = b.gone
    attrs["lay0"] = b.lay0; attrs["lay1"] = b.lay1
    # Energy: the label, its scale (13 or 18) and E-value; solar: kWh a year (-1 without an estimate), m² of panels.
    attrs["eclass"] = b.energy; attrs["ever"] = b.ever.fillna(0); attrs["eluku"] = b.eluku.fillna(0).clip(0, 65535)
    attrs["solar"] = b.solar_kwh.round().fillna(-1); attrs["panel"] = b.panel_m2.round().fillna(0).clip(0, 65535)
    attrs["wk"] = b.key.map(pd.read_parquet("data/wiki_index.parquet").set_index("key").wk).fillna(-1).astype(int)
    # Use: the register's class (Rakennusluokitus 1994) where the building has one, else the map's building type.
    use_key = b.c_kayttark.where(b.c_kayttark.isin(KAYTTARK), b.tyyppi)
    uses = sorted(use_key.dropna().unique())
    attrs["use"] = use_key.map({k: i + 1 for i, k in enumerate(uses)}).fillna(0)
    code = lambda col, table: pd.to_numeric(col, errors="coerce").where(lambda c: c.isin(table.keys())).fillna(0)
    attrs["mat"] = code(b.c_rakeaine, RAKEAINE); attrs["fac"] = code(b.c_julkisivu, JULKISIVU)
    cen = to_local(np.c_[b.geometry.centroid.x, b.geometry.centroid.y])
    attrs["x"], attrs["z"] = cen[:, 0], cen[:, 1]
    (OUT / "attrs.bin").write_bytes(attrs.tobytes())
    # Strings, by building: the id (VTJ-PRT, or the city's feature id) and the street address.
    addr = (b.katunimi_suomi.fillna("") + " " + b.osoitenumero.fillna("")).str.strip()
    (OUT / "info.json").write_text(json.dumps(dict(id=b.key.tolist(), addr=addr.tolist()), ensure_ascii=False, separators=(",", ":")))
    for name, empty in STUBS.items():
        if not (OUT / name).exists():
            (OUT / name).write_text(empty)

    years = b.year.to_numpy()
    hist, gone = {}, {}
    for p, y in zip(b.period, years):
        hist.setdefault(int(y), [0] * len(PERIODS))[p] += 1
    for p, y in zip(b.period[b.gone > 0], b.gone[b.gone > 0]):  # buildings leave the count in these years
        gone.setdefault(int(y), [0] * len(PERIODS))[p] += 1
    label = lambda fi, en: dict(fi=fi, en=en)
    config = dict(
        city="helsinki", label="Helsinki", tileSize=TILE, origin=ORIGIN,
        home=dict(x=-850, z=100, azimuth=345, elevation=42, span=6600),  # from the sea: the peninsula and the inner city
        periods=[dict(key=k, label=l, from_=a, to=bb, color=col) for k, l, a, bb, col in PERIODS],
        yearMin=int(years.min()), yearMax=int(years.max()),
        histogram={str(k): v for k, v in sorted(hist.items())},
        demolished={str(k): v for k, v in sorted(gone.items())},
        # Counted among the buildings standing today
        energy=dict(labels=list("GFEDCBA"), counts=np.bincount(b.energy[b.gone == 0], minlength=8).tolist()),
        solar=dict(steps=SOLAR_MWH, counts=np.bincount(b.solar[b.gone == 0], minlength=len(SOLAR_MWH) + 3).tolist()),
        attrStride=attrs.dtype.itemsize,
        archive=(OUT / "archive").exists(),  # archive photos, a later step
        uses=[label(*(KAYTTARK.get(k) or TYYPPI.get(k, (k, k)))) for k in uses],
        materials={str(k): label(*v) for k, v in RAKEAINE.items()},
        facades={str(k): label(*v) for k, v in JULKISIVU.items()},
        tiles=index,
        packs=packs,
        stats=dict(buildings=len(b), exact=int((b.date_flag == 0).sum()),
                   faint=int((b.date_flag == 1).sum()), estimated=int((b.date_flag == 2).sum()),
                   property=int((b.date_flag == 4).sum()),
                   floorsRegister=int((b.floors_src == 0).sum()), floorsAssumed=int((b.floors_src == 1).sum()),
                   heightModel=int((b.height_src == 0).sum()), demolished=int((b.gone > 0).sum())),
    )
    (OUT / "helsinki.json").write_text(json.dumps(config, ensure_ascii=False, separators=(",", ":")).replace('"from_"', '"from"'))
    total = sum(t["bytes"] for t in index)
    print(f"{len(index)} tiles, {total/1e6:.1f} MB, attrs {attrs.nbytes/1e6:.1f} MB")


if __name__ == "__main__":
    main()
