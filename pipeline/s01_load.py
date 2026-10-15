"""Helsinki's buildings with register data, and those its 3D city model records as demolished → data/buildings.parquet,
one row per building.

Key: the permanent building identifier VTJ-PRT where the outline is linked to the register, else the city's feature id
(the model's for a demolished building). Every building type is kept, including 'Räystäs (stereo)': those are outlines
traced along the eaves in stereo aerial imagery (Östersundom, Santahamina), not duplicates of other buildings.
`gone` is the year of demolition, 0 for a building standing today. See README, Data decisions.
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely
from pyproj import Transformer

from .codes import KAYTTARK, TYYPPI
from .s00_fetch import read_b3dm

COLS = ["id", "vtj_prt", "i_pyraknro", "tyyppi", "c_valmpvm", "i_kerrlkm", "c_kayttark", "c_rakeaine", "c_julkisivu",
        "c_kiinteistotunnus", "katunimi_suomi", "katunimi_ruotsi", "osoitenumero", "c_poltaine", "c_lammtapa"]
ECEF_TO_GK25 = Transformer.from_crs(4978, 3879, always_xy=True)
Y_UP = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]])  # glTF's y-up into the tile's z-up: (x, y, z) → (x, -z, y)
USE_CODE = {fi.lower(): code for code, (fi, _) in KAYTTARK.items()}


def demolished() -> gpd.GeoDataFrame:
    """The model's demolished buildings, LoD1 prisms in b3dm: the outline is the union of the roof's triangles."""
    rows = []
    for path in sorted(Path("data/raw/demolished").glob("*.b3dm")):
        features, table, gltf, accessor = read_b3dm(path.read_bytes())
        node = gltf["nodes"][0]
        m = np.array(node["matrix"]).reshape(4, 4).T  # column-major; turns the model's local east-up-south to the globe
        for prim in gltf["meshes"][node["mesh"]]["primitives"]:
            pos, ids = accessor(prim["attributes"]["POSITION"]), accessor(prim["attributes"]["_BATCHID"]).astype(int)
            tri = accessor(prim["indices"]).astype(int).reshape(-1, 3)
            ecef = (pos @ m[:3, :3].T + m[:3, 3]) @ Y_UP.T + features["RTC_CENTER"]
            en = np.c_[ECEF_TO_GK25.transform(*ecef.T)[:2]]
            a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
            n = np.cross(b - a, c - a)
            flat = np.abs(n[:, 1]) > 0.99 * np.linalg.norm(n, axis=1)
            for i in np.unique(ids):
                own = ids[tri[:, 0]] == i
                roof = own & flat & (a[:, 1] > pos[ids == i, 1].min() + 0.5)
                if not roof.any():
                    continue
                outline = shapely.union_all(shapely.polygons(en[tri[roof]])).buffer(0.01).buffer(-0.01)
                rows.append(dict(table["attributes"][i], id=table["id"][i], geometry=outline))
    d = pd.DataFrame(rows)
    street = d.Address.map(lambda a: a.get("Street"))
    return gpd.GeoDataFrame({
        "id": d.id, "vtj_prt": d.get("VTJ_PRT"), "i_pyraknro": None,
        "tyyppi": d.get("usage").where(d.get("usage").isin(TYYPPI.keys())),
        "c_valmpvm": d.get("yearOfConstruction"), "i_kerrlkm": d.get("storeysAboveGround"),
        "c_kayttark": d.get("function").str.lower().map(USE_CODE), "c_rakeaine": None, "c_julkisivu": None,
        "c_kiinteistotunnus": None, "katunimi_suomi": street,
        "katunimi_ruotsi": None, "osoitenumero": d.Address.map(lambda a: a.get("HouseNumber")).where(street.notna()),
        "gone": d.yearOfDemolition.astype(int), "lod1_height": d.measuredHeight.astype(float),
    }, geometry=d.geometry.values, crs=3879)


def main():
    # Dates as written (local midnight, "1968-12-31T00:00:00+02:00"): parsed to UTC they would slip into the year before.
    b = pyogrio.read_dataframe("data/raw/Rakennukset_alue_rekisteritiedot.geojson", columns=COLS, datetime_as_string=True)
    b["id"] = b.id.astype(str)
    b["gone"], b["lod1_height"] = 0, np.nan
    g = demolished()
    # The register outlasts the model on a few: what it still lists stands.
    g = g[~g.vtj_prt.isin(b.vtj_prt.dropna())]
    g.loc[g.vtj_prt.notna() & g.vtj_prt.duplicated(), "vtj_prt"] = None  # a building in two parts: the second by its id
    b = pd.concat([b, g.to_crs(b.crs)], ignore_index=True)
    b["key"] = b.vtj_prt.fillna(b.id)
    assert b.key.is_unique
    b.to_parquet("data/buildings.parquet")
    print(len(b), "buildings;", int(b.vtj_prt.notna().sum()), "with a VTJ-PRT;", len(g), "demolished")
    print(b.tyyppi.value_counts().to_string())


if __name__ == "__main__":
    main()
