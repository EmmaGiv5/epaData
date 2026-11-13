"""Comparison summaries for the application's emissions datasets."""

import math
from collections import defaultdict

import numpy as np
from sqlalchemy import Integer, MetaData, String, Table, cast, func, select

from app import db


DATASETS = {
    "annual_state": {
        "label": "Annual state emissions",
        "table": "calc_data_annual",
    },
    "annual_facility": {
        "label": "Annual facility emissions",
        "table": "annual_emissions_facility",
    },
    "hourly_state": {
        "label": "Hourly state emissions",
        "table": "calc_data_hourly",
    },
    "hourly_facility": {
        "label": "Hourly facility emissions",
        "table": "hourly_emissions_facility",
    },
    "unit_annual": {
        "label": "Annual unit records",
        "table": "annual_records",
    },
}

METRICS = {
    "gross_load": {
        "label": "Gross load",
        "columns": ("gross_load", "Gross Load (MWh)", "Gross Load (MW)"),
    },
    "steam_load": {
        "label": "Steam load",
        "columns": ("steam_load", "Steam Load (1000 lb)", "Steam Load (1000 lb/hr)"),
    },
    "co2_mass": {
        "label": "CO₂ mass",
        "columns": ("co2_mass", "CO2 Mass (short tons)"),
    },
    "so2_mass": {
        "label": "SO₂ mass",
        "columns": ("so2_mass", "SO2 Mass (short tons)", "SO2 Mass (lbs)"),
    },
    "nox_mass": {
        "label": "NOx mass",
        "columns": ("nox_mass", "NOx Mass (short tons)", "NOx Mass (lbs)"),
    },
    "heat_input": {
        "label": "Heat input",
        "columns": ("heat_input", "Heat Input (mmBtu)"),
    },
    "co2_intensity": {
        "label": "CO₂ intensity",
        "numerator": ("co2_mass", "CO2 Mass (short tons)"),
        "denominator": ("gross_load", "Gross Load (MWh)", "Gross Load (MW)"),
    },
    "so2_intensity": {
        "label": "SO₂ intensity",
        "numerator": ("so2_mass", "SO2 Mass (short tons)", "SO2 Mass (lbs)"),
        "denominator": ("gross_load", "Gross Load (MWh)", "Gross Load (MW)"),
    },
    "nox_intensity": {
        "label": "NOx intensity",
        "numerator": ("nox_mass", "NOx Mass (short tons)", "NOx Mass (lbs)"),
        "denominator": ("gross_load", "Gross Load (MWh)", "Gross Load (MW)"),
    },
    "heat_rate": {
        "label": "Heat rate",
        "numerator": ("heat_input", "Heat Input (mmBtu)"),
        "denominator": ("gross_load", "Gross Load (MWh)", "Gross Load (MW)"),
    },
}

GROUPS = {
    "state": ("State", "state"),
    "year": ("Year", "year"),
    "facility_name": ("Facility Name", "facility_name"),
    "facility_id": ("Facility ID", "facility_id"),
    "unit_id": ("Unit ID", "unit_id"),
    "fuel": ("Primary Fuel Type", "fuel"),
    "unit_type": ("Unit Type", "unit_type"),
    "so2_control_status": ("SO₂ control status", "so2_control_status"),
    "nox_control_status": ("NOx control status", "nox_control_status"),
    "pm_control_status": ("PM control status", "pm_control_status"),
}

EXTERNAL_GROUP_COLUMNS = {
    "state": ("State",),
    "year": ("Year",),
    "facility_name": ("Facility Name",),
    "facility_id": ("Facility ID",),
}

CONTROL_FIELDS = {
    "so2_control_status": "so2_control",
    "nox_control_status": "nox_control",
    "pm_control_status": "pm_control",
}

NO_CONTROL_VALUES = {
    "no",
    "none",
    "no control",
    "uncontrolled",
    "not controlled",
}
UNSPECIFIED_CONTROL_VALUES = {
    "",
    "n/a",
    "na",
    "unknown",
    "not reported",
    "not specified",
}


def _column(columns, candidates):
    return next(
        (columns[name] for name in candidates if name in columns),
        None,
    )


def _unit_data_source(metadata):
    records = Table("annual_records", metadata, autoload_with=db.engine)
    units = Table("units", metadata, autoload_with=db.engine)
    facilities = Table("facilities", metadata, autoload_with=db.engine)
    from_clause = records.join(
        units,
        records.c.unit_id == units.c.id,
    ).join(
        facilities,
        units.c.facility_id == facilities.c.id,
    )
    fields = {
        "state": facilities.c.state,
        "year": records.c.reporting_year,
        "facility_name": facilities.c.facility_name,
        "facility_id": facilities.c.epa_facility_id,
        "unit_id": units.c.epa_unit_id,
        "fuel": units.c.primary_fuel,
        "unit_type": units.c.unit_type,
        "so2_control_status": records.c.so2_control,
        "nox_control_status": records.c.nox_control,
        "pm_control_status": records.c.pm_control,
    }
    return from_clause, records.c, fields, records.c.reporting_year


def _external_data_source(dataset_key, metadata):
    table_name = DATASETS[dataset_key]["table"]
    table = Table(table_name, metadata, autoload_with=db.engine)
    fields = {}

    for group_key, candidates in EXTERNAL_GROUP_COLUMNS.items():
        column = _column(table.c, candidates)
        if column is not None:
            fields[group_key] = column

    date_column = table.c["Date"] if "Date" in table.c else None
    year_expression = (
        _column(table.c, ("Year",))
        if "Year" in table.c
        else (
            cast(
                func.substr(cast(date_column, String), 1, 4),
                Integer,
            )
            if date_column is not None
            else None
        )
    )
    if year_expression is not None:
        fields["year"] = year_expression

    return table, table.c, fields, year_expression


def _control_status(value):
    if value is None:
        return "Not specified"
    normalized = str(value).strip().lower()
    if normalized in UNSPECIFIED_CONTROL_VALUES:
        return "Not specified"
    if normalized in NO_CONTROL_VALUES:
        return "Without control"
    return "With control"


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metric_units(metric_key, selected_columns):
    metric = METRICS[metric_key]
    canonical_units = {
        "gross_load": "MWh",
        "steam_load": "1000 lb",
        "heat_input": "mmBtu",
        "co2_mass": "short tons",
        "so2_mass": "short tons",
        "nox_mass": "short tons",
    }

    if "columns" in metric:
        column = selected_columns[0]
        start = column.name.rfind("(")
        end = column.name.rfind(")")
        if start >= 0 and end > start:
            return column.name[start + 1:end]
        return canonical_units.get(column.name, "")

    numerator, denominator = selected_columns

    def unit(column):
        start = column.name.rfind("(")
        end = column.name.rfind(")")
        if start >= 0 and end > start:
            return column.name[start + 1:end]
        return canonical_units.get(column.name, "")

    return f"{unit(numerator)} / {unit(denominator)}"


def _build_row_value(metric_key, row):
    metric = METRICS[metric_key]
    if "columns" in metric:
        return _finite_number(row["metric_value"])

    numerator = _finite_number(row["metric_numerator"])
    denominator = _finite_number(row["metric_denominator"])
    if numerator is None or denominator in (None, 0):
        return None
    return _finite_number(numerator / denominator)


def _statistics(values):
    usable = np.asarray(values, dtype=float)
    count = len(usable)
    if not count:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "standard_deviation": None,
            "minimum": None,
            "maximum": None,
        }
    return {
        "count": count,
        "mean": float(np.mean(usable)),
        "median": float(np.median(usable)),
        "standard_deviation": (
            float(np.std(usable, ddof=1)) if count > 1 else None
        ),
        "minimum": float(np.min(usable)),
        "maximum": float(np.max(usable)),
    }


def build_comparison(
    dataset_key,
    metric_key,
    group_key,
    aggregation,
    baseline,
    year_from,
    year_to,
):
    """Return all group summaries and comparisons for a dataset and metric."""
    metadata = MetaData()
    if dataset_key == "unit_annual":
        from_clause, data_columns, group_fields, year_expression = (
            _unit_data_source(metadata)
        )
    else:
        from_clause, data_columns, group_fields, year_expression = (
            _external_data_source(dataset_key, metadata)
        )

    metric = METRICS[metric_key]
    selected_columns = []
    if "columns" in metric:
        value_column = _column(data_columns, metric["columns"])
        if value_column is None:
            raise ValueError(
                f"The selected dataset does not contain {metric['label']}."
            )
        selected_columns.append(value_column)
    else:
        numerator_column = _column(data_columns, metric["numerator"])
        denominator_column = _column(data_columns, metric["denominator"])
        if numerator_column is None or denominator_column is None:
            raise ValueError(
                f"The selected dataset does not contain all fields needed "
                f"for {metric['label']}."
            )
        selected_columns.extend((numerator_column, denominator_column))

    if group_key and group_key not in group_fields:
        raise ValueError(
            "The selected dataset does not contain the chosen comparison group."
        )
    if year_expression is None and (year_from is not None or year_to is not None):
        raise ValueError(
            "The selected dataset does not contain a reporting year."
        )

    if group_key == "year":
        group_expression = year_expression
    else:
        group_expression = group_fields.get(group_key) if group_key else None

    selections = []
    if group_expression is not None:
        selections.append(group_expression.label("group_value"))
    if len(selected_columns) == 1:
        selections.append(selected_columns[0].label("metric_value"))
    else:
        selections.extend((
            selected_columns[0].label("metric_numerator"),
            selected_columns[1].label("metric_denominator"),
        ))

    query = select(*selections).select_from(from_clause)
    if year_from is not None:
        query = query.where(year_expression >= year_from)
    if year_to is not None:
        query = query.where(year_expression <= year_to)

    rows = db.session.execute(query).mappings().all()
    groups = defaultdict(list)

    for row in rows:
        value = _build_row_value(metric_key, row)
        if group_expression is None:
            label = "All records"
        else:
            group_value = row["group_value"]
            if group_key in CONTROL_FIELDS:
                label = _control_status(group_value)
            elif group_value is None:
                label = "(Missing group)"
            else:
                label = str(group_value)
        groups[label].append(value)

    summaries = []
    for label, raw_values in groups.items():
        values = [value for value in raw_values if value is not None]
        summary = _statistics(values)
        summary.update({
            "group": label,
            "missing_count": len(raw_values) - len(values),
            "total": float(sum(values)) if values else None,
        })
        comparison_value = (
            summary["total"] if aggregation == "sum" else summary["mean"]
        )
        summary["comparison_value"] = comparison_value
        summaries.append(summary)

    summaries.sort(
        key=lambda summary: (
            summary["comparison_value"] is None,
            -(summary["comparison_value"] or 0),
            summary["group"].casefold(),
        )
    )
    rank = 0
    previous_value = None
    for index, summary in enumerate(summaries, start=1):
        value = summary["comparison_value"]
        if value is not None:
            if index == 1 or value != previous_value:
                rank = index
            summary["rank"] = rank
            previous_value = value
        else:
            summary["rank"] = None

    baseline_label = baseline if any(
        summary["group"] == baseline for summary in summaries
    ) else (summaries[0]["group"] if summaries else "")
    baseline_summary = next(
        (
            summary for summary in summaries
            if summary["group"] == baseline_label
        ),
        None,
    )
    baseline_value = (
        baseline_summary["comparison_value"]
        if baseline_summary is not None
        else None
    )

    for summary in summaries:
        value = summary["comparison_value"]
        if value is None or baseline_value is None:
            summary["difference"] = None
            summary["percentage_difference"] = None
        else:
            summary["difference"] = value - baseline_value
            summary["percentage_difference"] = (
                (value - baseline_value) / abs(baseline_value) * 100
                if baseline_value != 0
                else None
            )

    available_groups = [
        {"key": key, "label": GROUPS[key][0]}
        for key in GROUPS
        if key in group_fields
    ]
    return {
        "summaries": summaries,
        "available_groups": available_groups,
        "baseline": baseline_label,
        "units": _metric_units(metric_key, selected_columns),
        "dataset_label": DATASETS[dataset_key]["label"],
        "metric_label": metric["label"],
    }


def comparison_options(dataset_key):
    """Return valid group choices present in a dataset."""
    metadata = MetaData()
    if dataset_key == "unit_annual":
        _, _, group_fields, _ = _unit_data_source(metadata)
    else:
        _, _, group_fields, _ = _external_data_source(dataset_key, metadata)
    return [
        {"key": key, "label": GROUPS[key][0]}
        for key in GROUPS
        if key in group_fields
    ]


def comparison_metrics(dataset_key):
    """Return metrics whose source columns exist in the selected dataset."""
    metadata = MetaData()
    if dataset_key == "unit_annual":
        _, data_columns, _, _ = _unit_data_source(metadata)
    else:
        _, data_columns, _, _ = _external_data_source(dataset_key, metadata)

    available = []
    for key, definition in METRICS.items():
        if "columns" in definition:
            supported = _column(data_columns, definition["columns"]) is not None
        else:
            supported = (
                _column(data_columns, definition["numerator"]) is not None
                and _column(data_columns, definition["denominator"]) is not None
            )
        if supported:
            available.append({"key": key, "label": definition["label"]})
    return available
