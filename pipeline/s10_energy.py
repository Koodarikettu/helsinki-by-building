"""Energy labels and solar potential, by building → data/energy.parquet.

Energy labels: Varke's register of energy certificates, its public CSV (every certificate in force; those of houses
with one or two homes are not public), matched by VTJ-PRT. A building with several takes the one signed last. The 2013
and 2018 scales put the class limits in different places, so the version is kept for the card.
Solar: HSY's photovoltaic potential (2015, CC BY 4.0), the yearly output if every suitable part of the roof carried
panels. Each of its outlines goes to the building of ours its inside point falls in, and several add up. The outlines
are newer than the estimates, which read zero on nearly every building completed after 2010 (2009: 28 % zero, like the
city as a whole; 2012: 69 %; 2015: 96 %): those are left without one.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

CLASSES = "GFEDCBA"  # 1 … 7; 0 = no certificate


COLS = ["Id", "Versio", "Allekirjoitusaika", "Perustiedot / Rakennustunnus", "Tulokset / E-luku", "Tulokset / E-luokka"]


def labels(b: pd.DataFrame, e: pd.DataFrame) -> pd.DataFrame:
    e = e[COLS].set_axis(["id", "version", "signed", "vtj_prt", "eluku", "eclass"], axis=1)
    e = e[e.vtj_prt.isin(b.vtj_prt.dropna()) & e.eclass.isin(list(CLASSES))]
    e = e.sort_values(["signed", "id"]).drop_duplicates("vtj_prt", keep="last")
    return pd.DataFrame({"key": e.vtj_prt, "eclass": e.eclass.map(CLASSES.index) + 1,
                         "eluku": pd.to_numeric(e.eluku, errors="coerce").fillna(0).astype(int),
                         "ever": e.version.astype(int) % 100})


def solar(b: gpd.GeoDataFrame, s: gpd.GeoDataFrame) -> pd.DataFrame:
    s = s.to_crs(b.crs)
    s["geometry"] = s.geometry.representative_point()
    after = pd.to_numeric(b.c_valmpvm.astype(str).str[:4], errors="coerce") > 2010
    j = gpd.sjoin(s, b[(b.gone == 0) & ~after][["key", "geometry"]], predicate="within")
    j = j[~j.index.duplicated()]  # overlapping outlines of ours: the first
    return j.groupby("key", as_index=False).agg(solar_kwh=("elec_kwh_v", "sum"), panel_m2=("panel_ala", "sum"))


def main():
    b = gpd.read_parquet("data/buildings.parquet", columns=["key", "vtj_prt", "c_valmpvm", "gone", "geometry"])
    e = labels(b, pd.read_csv("data/raw/energiatodistukset.csv", sep=";", dtype=str, usecols=COLS))
    e = e.merge(solar(b, gpd.read_file("data/raw/rakennukset_aurinkosahkopotentiaali.geojson")), on="key", how="outer")
    e.to_parquet("data/energy.parquet")
    print(int((e.eclass > 0).sum()), "buildings with an energy label;", int(e.solar_kwh.notna().sum()),
          "with a solar estimate,", int((e.solar_kwh > 0).sum()), "above zero")
    print(e.eclass.value_counts().sort_index().rename(lambda i: CLASSES[int(i) - 1]).to_string())


if __name__ == "__main__":
    main()
