"""Build the modeling dataset from the Phase 1 database.

Each row is one unit-year (year t). The target is the same unit's CO2 in year
t + 1, and only consecutive years are paired.
"""

import numpy as np
import pandas as pd

from machine_learning.config import CATEGORICAL_FEATURES, NUMERIC_FEATURES


def coerce_frame(frame):
    """Make numeric columns numeric and missing categories a real NaN."""
    frame = frame.copy()
    for column in NUMERIC_FEATURES:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in CATEGORICAL_FEATURES:
        series = frame[column].astype(object)
        frame[column] = series.where(series.notna(), np.nan)
    return frame


def get_forecast_data():
    # Imported here so the pure-ML modules can be tested without an app context.
    from app import db
    from app.models import AnnualRecord, Facility, Unit

    rows = (
        db.session.query(
            AnnualRecord.unit_id,
            AnnualRecord.reporting_year,
            AnnualRecord.operating_time,
            AnnualRecord.gross_load,
            AnnualRecord.heat_input,
            AnnualRecord.co2_mass,
            Unit.primary_fuel,
            Unit.unit_type,
            Facility.state,
        )
        .join(Unit, AnnualRecord.unit_id == Unit.id)
        .join(Facility, Unit.facility_id == Facility.id)
        .all()
    )

    df = pd.DataFrame(
        rows,
        columns=[
            "unit_id", "year", "operating_time", "gross_load", "heat_input",
            "co2_mass", "primary_fuel", "unit_type", "state",
        ],
    )
    return build_forecast_frame(df)


def build_forecast_frame(df):
    """Pair each unit-year with the same unit's CO2 one year later."""
    df = df.copy()
    for column in ("operating_time", "gross_load", "heat_input", "co2_mass"):
        df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.drop_duplicates(subset=["unit_id", "year"])
    df = df.sort_values(["unit_id", "year"])

    grouped = df.groupby("unit_id")
    next_year = grouped["year"].shift(-1)
    next_co2 = grouped["co2_mass"].shift(-1)

    # Only keep the next value when it is exactly one year later (no gaps).
    df["co2_mass_next"] = next_co2.where(next_year == df["year"] + 1)
    df["target_year"] = df["year"] + 1
    df = df.rename(columns={"co2_mass": "co2_mass_prev"})

    df = df.dropna(
        subset=["co2_mass_prev", "co2_mass_next", "gross_load", "heat_input"]
    )
    df = df[
        (df["gross_load"] > 0)
        & (df["heat_input"] >= 0)
        & (df["co2_mass_prev"] >= 0)
        & (df["co2_mass_next"] >= 0)
    ]
    return df.reset_index(drop=True)


def get_unit_baseline(unit_id):
    """Latest-year inputs for one unit, used to pre-fill the comparison page."""
    from app import db
    from app.models import AnnualRecord, Facility, Unit

    row = (
        db.session.query(
            AnnualRecord.reporting_year,
            AnnualRecord.operating_time,
            AnnualRecord.gross_load,
            AnnualRecord.heat_input,
            AnnualRecord.co2_mass,
            Unit.primary_fuel,
            Unit.unit_type,
            Unit.epa_unit_id,
            Facility.state,
            Facility.facility_name,
        )
        .join(Unit, AnnualRecord.unit_id == Unit.id)
        .join(Facility, Unit.facility_id == Facility.id)
        .filter(AnnualRecord.unit_id == unit_id)
        .order_by(AnnualRecord.reporting_year.desc())
        .first()
    )
    if row is None:
        return None

    def number(value):
        return None if value is None else float(value)

    return {
        "label": f"{row.facility_name} — Unit {row.epa_unit_id}",
        "observed_year": int(row.reporting_year),
        "predicted_year": int(row.reporting_year) + 1,
        "inputs": {
            "gross_load": number(row.gross_load),
            "heat_input": number(row.heat_input),
            "operating_time": number(row.operating_time),
            "co2_mass_prev": number(row.co2_mass),
            "primary_fuel": row.primary_fuel,
            "unit_type": row.unit_type,
            "state": row.state,
        },
    }
