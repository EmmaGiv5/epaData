import os

import pandas as pd


# Columns required by the Phase 1 annual-record schema
REQUIRED_COLUMNS = {
    "epa_facility_id",
    "facility_name",
    "state",
    "county",
    "epa_unit_id",
    "unit_type",
    "primary_fuel",
    "secondary_fuel",
    "reporting_year",
    "operating_time",
    "gross_load",
    "steam_load",
    "heat_input",
    "co2_mass",
    "so2_mass",
    "nox_mass",
    "so2_control",
    "nox_control",
    "pm_control",
    "program_code",
}


ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
    ".xls",
}


def get_file_extension(filename):
    """Return the lowercase file extension."""
    return os.path.splitext(filename)[1].lower()


def read_uploaded_file(file_path):
    """
    Read a CSV or Excel file into a pandas DataFrame.
    """

    extension = get_file_extension(file_path)

    if extension == ".csv":
        return pd.read_csv(file_path)

    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)

    raise ValueError(
        "Unsupported file type. "
        "Please upload CSV or Excel files."
    )


def validate_columns(dataframe):
    """
    Check whether the uploaded file contains
    all required columns.
    """

    available_columns = set(dataframe.columns)

    missing_columns = (
        REQUIRED_COLUMNS - available_columns
    )

    extra_columns = (
        available_columns - REQUIRED_COLUMNS
    )

    return {
        "valid": len(missing_columns) == 0,
        "missing_columns": sorted(missing_columns),
        "extra_columns": sorted(extra_columns),
        "available_columns": sorted(available_columns),
    }


def validate_values(dataframe):
    """
    Check for missing and invalid values.
    """

    errors = []

    # Required identification fields
    required_value_columns = [
        "epa_facility_id",
        "epa_unit_id",
        "reporting_year",
    ]

    for column in required_value_columns:

        if column not in dataframe.columns:
            continue

        missing_count = dataframe[column].isna().sum()

        if missing_count > 0:
            errors.append({
                "column": column,
                "problem": "Missing values",
                "count": int(missing_count),
            })

    # Reporting year
    if "reporting_year" in dataframe.columns:

        invalid_years = dataframe[
            ~dataframe["reporting_year"]
            .between(1990, 2100, inclusive="both")
        ]

        if len(invalid_years) > 0:

            errors.append({
                "column": "reporting_year",
                "problem": "Invalid reporting year",
                "count": len(invalid_years),
            })

    # Numeric columns
    numeric_columns = [
        "operating_time",
        "gross_load",
        "steam_load",
        "heat_input",
        "co2_mass",
        "so2_mass",
        "nox_mass",
    ]

    for column in numeric_columns:

        if column not in dataframe.columns:
            continue

        converted = pd.to_numeric(
            dataframe[column],
            errors="coerce"
        )

        invalid_count = (
            converted.isna()
            & dataframe[column].notna()
        ).sum()

        if invalid_count > 0:

            errors.append({
                "column": column,
                "problem": "Invalid numeric value",
                "count": int(invalid_count),
            })

    return errors


def find_duplicates(dataframe):
    """
    Find duplicate facility/unit/year records.
    """

    required = {
        "epa_facility_id",
        "epa_unit_id",
        "reporting_year",
    }

    if not required.issubset(dataframe.columns):
        return pd.DataFrame()

    duplicate_mask = dataframe.duplicated(
        subset=[
            "epa_facility_id",
            "epa_unit_id",
            "reporting_year",
        ],
        keep=False,
    )

    return dataframe[duplicate_mask]


def validate_dataframe(dataframe):
    """
    Run all validation checks.
    """

    column_result = validate_columns(dataframe)

    value_errors = validate_values(dataframe)

    duplicates = find_duplicates(dataframe)

    return {
        "columns": column_result,
        "value_errors": value_errors,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "row_count": len(dataframe),
        "valid": (
            column_result["valid"]
            and len(value_errors) == 0
            and len(duplicates) == 0
        ),
    }
