import os
import pandas as pd


REQUIRED_COLUMNS = {
    "epa_facility_id",
    "facility_name",
    "state",
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

COLUMN_MAP = {
    "State": "state",
    "Facility Name": "facility_name",
    "Facility ID": "epa_facility_id",
    "Unit ID": "epa_unit_id",
    "Year": "reporting_year",
    "Sum of the Operating Time": "operating_time",
    "Gross Load (MWh)": "gross_load",
    "Steam Load (1000 lb)": "steam_load",
    "SO2 Mass (short tons)": "so2_mass",
    "CO2": "co2_mass",
    "NOx Mass (short tons)": "nox_mass",
    "Heat Input (mmBtu)": "heat_input",
    "Primary Fuel Type": "primary_fuel",
    "Secondary Fuel Type": "secondary_fuel",
    "Unit Type": "unit_type",
    "SO2 Controls": "so2_control",
    "NOx Controls": "nox_control",
    "PM Controls": "pm_control",
    "Program Code": "program_code"
}


ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def get_file_extension(filename):
    return os.path.splitext(filename)[1].lower()


def read_uploaded_file(file_path):
    extension = get_file_extension(file_path)

    if extension == ".csv":
        return pd.read_csv(file_path)

    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(file_path)

    raise ValueError(
        "Unsupported file type. Please upload a CSV or Excel file."
    )


def normalize_columns(dataframe):
    dataframe = dataframe.copy()

    dataframe.columns = [
        str(column).strip()
        for column in dataframe.columns
    ]

    dataframe = dataframe.rename(columns=COLUMN_MAP)

    return dataframe


def validate_columns(dataframe):
    available_columns = set(dataframe.columns)

    missing_columns = REQUIRED_COLUMNS - available_columns

    extra_columns = available_columns - REQUIRED_COLUMNS

    return {
        "valid": len(missing_columns) == 0,
        "missing_columns": sorted(missing_columns),
        "extra_columns": sorted(extra_columns),
        "available_columns": sorted(available_columns),
    }


def validate_values(dataframe):
    errors = []

    required_value_columns = [
        "epa_facility_id",
        "epa_unit_id",
        "reporting_year",
    ]

    for column in required_value_columns:
        if column not in dataframe.columns:
            continue

        missing_count = int(dataframe[column].isna().sum())

        if missing_count > 0:
            errors.append({
                "column": column,
                "problem": "Missing values",
                "count": missing_count,
            })

    if "reporting_year" in dataframe.columns:
        years = pd.to_numeric(
            dataframe["reporting_year"],
            errors="coerce"
        )

        invalid_years = (
            years.isna()
            | ~years.between(1990, 2100)
        )

        invalid_count = int(invalid_years.sum())

        if invalid_count > 0:
            errors.append({
                "column": "reporting_year",
                "problem": "Invalid reporting year",
                "count": invalid_count,
            })

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

        invalid = (
            converted.isna()
            & dataframe[column].notna()
        )

        invalid_count = int(invalid.sum())

        if invalid_count > 0:
            errors.append({
                "column": column,
                "problem": "Invalid numeric value",
                "count": invalid_count,
            })

    return errors


def find_duplicates(dataframe):
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