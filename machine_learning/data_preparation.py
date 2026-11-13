import pandas as pd

from app import db
from app.models import AnnualRecord, Unit, Facility


def get_training_data():

    records = (
        db.session.query(
            AnnualRecord.reporting_year,
            AnnualRecord.operating_time,
            AnnualRecord.gross_load,
            AnnualRecord.heat_input,
            AnnualRecord.co2_mass,
            Unit.primary_fuel,
            Unit.unit_type,
            Facility.state,
        )
        .join(
            Unit,
            AnnualRecord.unit_id == Unit.id
        )
        .join(
            Facility,
            Unit.facility_id == Facility.id
        )
        .all()
    )

    dataframe = pd.DataFrame(
        records,
        columns=[
            "year",
            "operating_time",
            "gross_load",
            "heat_input",
            "co2_mass",
            "primary_fuel",
            "unit_type",
            "state",
        ]
    )

    dataframe = dataframe.dropna(
        subset=["co2_mass", "gross_load", "heat_input"]
    )

    dataframe = dataframe[
        dataframe["gross_load"] > 0
    ]

    dataframe = dataframe[
        dataframe["heat_input"] >= 0
    ]

    dataframe = dataframe[
        dataframe["co2_mass"] >= 0
    ]

    dataframe = dataframe.drop_duplicates()

    return dataframe