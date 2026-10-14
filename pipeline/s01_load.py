"""Helsinki's buildings with register data → data/buildings.parquet, one row per building.

Key: the permanent building identifier VTJ-PRT where the outline is linked to the register, else the city's feature id.
Every building type is kept, including 'Räystäs (stereo)': those are outlines traced along the eaves in stereo aerial
imagery (Östersundom, Santahamina), not duplicates of other buildings. See README, Data decisions.
"""
import pyogrio

COLS = ["id", "vtj_prt", "i_pyraknro", "tyyppi", "c_valmpvm", "i_kerrlkm", "c_kayttark", "c_rakeaine", "c_julkisivu",
        "c_kiinteistotunnus", "katunimi_suomi", "katunimi_ruotsi", "osoitenumero"]


def main():
    # Dates as written (local midnight, "1968-12-31T00:00:00+02:00"): parsed to UTC they would slip into the year before.
    b = pyogrio.read_dataframe("data/raw/Rakennukset_alue_rekisteritiedot.geojson", columns=COLS, datetime_as_string=True)
    b["key"] = b.vtj_prt.fillna(b.id.astype(str))
    assert b.key.is_unique
    b.to_parquet("data/buildings.parquet")
    print(len(b), "buildings;", int(b.vtj_prt.notna().sum()), "with a VTJ-PRT")
    print(b.tyyppi.value_counts().to_string())


if __name__ == "__main__":
    main()
