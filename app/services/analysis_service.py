"""Filtered CAMPD analysis, descriptive summaries, and chart data."""

import calendar
import math
from collections import defaultdict

import numpy as np
from sqlalchemy import or_

from app import db
from app.models import AnnualRecord, Facility, Unit


VARIABLES = {
    "gross_load": ("Gross load", "MWh"),
    "steam_load": ("Steam load", "1000 lb"),
    "operating_time": ("Operating time", "hours"),
    "heat_input": ("Heat input", "mmBtu"),
    "co2_mass": ("CO2 mass", "short tons"),
    "so2_mass": ("SO2 mass", "short tons"),
    "nox_mass": ("NOx mass", "short tons"),
    "co2_intensity": ("CO2 intensity", "short tons / MWh"),
    "so2_intensity": ("SO2 intensity", "short tons / MWh"),
    "nox_intensity": ("NOx intensity", "short tons / MWh"),
    "heat_rate": ("Heat rate", "mmBtu / MWh"),
    "operating_utilization": ("Operating-hours share", "% of year"),
}

RAW_VARIABLES = (
    "gross_load",
    "steam_load",
    "operating_time",
    "heat_input",
    "co2_mass",
    "so2_mass",
    "nox_mass",
)

GROUPS = {
    "state": "State",
    "year": "Reporting year",
    "facility": "Facility",
    "unit": "Generating unit",
    "fuel": "Primary fuel",
    "unit_type": "Unit type",
}

CHART_TYPES = {
    "bar": "Bar chart",
    "line": "Line chart",
    "histogram": "Histogram",
    "scatter": "Scatter plot",
    "box": "Box plot",
    "heatmap": "Correlation heat map",
    "ranking": "High / low rankings",
    "map": "Facility map",
}

FILTER_FIELDS = (
    "state",
    "facility_id",
    "unit_id",
    "fuel",
    "unit_type",
)


def _finite_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _metric_value(record, key):
    if key in RAW_VARIABLES:
        return _finite_number(getattr(record, key))
    gross_load = _finite_number(record.gross_load)
    if key == "operating_utilization":
        operating_time = _finite_number(record.operating_time)
        if operating_time is None:
            return None
        annual_hours = 8784 if calendar.isleap(record.reporting_year) else 8760
        return operating_time / annual_hours * 100
    if gross_load in (None, 0):
        return None
    numerator_key = {
        "co2_intensity": "co2_mass",
        "so2_intensity": "so2_mass",
        "nox_intensity": "nox_mass",
        "heat_rate": "heat_input",
    }.get(key)
    if numerator_key is None:
        return None
    numerator = _finite_number(getattr(record, numerator_key))
    return numerator / gross_load if numerator is not None else None


def _parse_year(params, key):
    raw_value = str(params.get(key, "") or "").strip()
    if not raw_value:
        return None
    if not raw_value.isdigit():
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a whole year.")
    return int(raw_value)


def _parse_threshold(params, key):
    raw_value = str(params.get(key, "") or "").strip()
    if not raw_value:
        return None
    value = _finite_number(raw_value)
    if value is None:
        raise ValueError(f"{key.replace('_', ' ').capitalize()} must be a finite number.")
    return value


def _analysis_query():
    return db.session.query(
        AnnualRecord,
        Unit,
        Facility,
    ).join(
        Unit,
        AnnualRecord.unit_id == Unit.id,
    ).join(
        Facility,
        Unit.facility_id == Facility.id,
    )


def _available_options():
    query = _analysis_query()
    return {
        "states": [
            row[0] for row in query.with_entities(Facility.state)
            .filter(Facility.state.isnot(None))
            .distinct().order_by(Facility.state).all()
        ],
        "facilities": [
            {
                "id": row[0],
                "name": row[1],
                "state": row[2],
            }
            for row in query.with_entities(
                Facility.epa_facility_id,
                Facility.facility_name,
                Facility.state,
            ).distinct().order_by(Facility.facility_name).all()
        ],
        "units": [
            {
                "id": row[0],
                "unit_id": row[1],
                "facility_id": row[2],
                "facility_name": row[3],
            }
            for row in query.with_entities(
                Unit.id,
                Unit.epa_unit_id,
                Facility.epa_facility_id,
                Facility.facility_name,
            ).distinct().order_by(Unit.epa_unit_id).all()
        ],
        "fuels": [
            row[0] for row in query.with_entities(Unit.primary_fuel)
            .filter(Unit.primary_fuel.isnot(None))
            .distinct().order_by(Unit.primary_fuel).all()
        ],
        "unit_types": [
            row[0] for row in query.with_entities(Unit.unit_type)
            .filter(Unit.unit_type.isnot(None))
            .distinct().order_by(Unit.unit_type).all()
        ],
        "years": [
            row[0] for row in query.with_entities(AnnualRecord.reporting_year)
            .distinct().order_by(AnnualRecord.reporting_year).all()
        ],
    }


def analysis_form_options():
    return {
        "options": _available_options(),
        "variables": [
            {"key": key, "label": label, "units": units}
            for key, (label, units) in VARIABLES.items()
        ],
        "groups": [
            {"key": key, "label": label}
            for key, label in GROUPS.items()
        ],
        "chart_types": [
            {"key": key, "label": label}
            for key, label in CHART_TYPES.items()
        ],
        "available_fields": [
            "State",
            "Facility name and ID",
            "Generating unit",
            "Reporting year",
            "Unit type",
            "Primary and secondary fuel",
            "Operating time",
            "Gross load",
            "Heat input",
            "CO2, SO2, and NOx mass",
            "SO2, NOx, and PM control status",
            "Emissions program",
            "Facility latitude and longitude when available",
        ] + [
            label for key, (label, _) in VARIABLES.items()
            if key not in RAW_VARIABLES
        ],
    }


def _apply_dimensions(query, selections):
    for key, column in (
        ("state", Facility.state),
        ("facility_id", Facility.epa_facility_id),
        ("unit_id", Unit.id),
        ("fuel", Unit.primary_fuel),
        ("unit_type", Unit.unit_type),
    ):
        if selections[key]:
            query = query.filter(column == selections[key])

    if selections["control"]:
        pattern = f"%{selections['control']}%"
        query = query.filter(
            or_(
                AnnualRecord.so2_control.ilike(pattern),
                AnnualRecord.nox_control.ilike(pattern),
                AnnualRecord.pm_control.ilike(pattern),
            )
        )
    if selections["program_code"]:
        query = query.filter(
            AnnualRecord.program_code.ilike(
                f"%{selections['program_code']}%"
            )
        )
    return query


def _group_label(row, group_by):
    if group_by == "state":
        return row["state"] or "(Missing group)"
    if group_by == "year":
        return str(row["year"])
    if group_by == "facility":
        return row["facility_name"] or "(Missing group)"
    if group_by == "unit":
        return row["unit_label"] or "(Missing group)"
    if group_by == "fuel":
        return row["fuel"] or "(Missing group)"
    if group_by == "unit_type":
        return row["unit_type"] or "(Missing group)"
    return "All records"


def _summarize(group, rows, variable, percentiles):
    raw_values = [row[variable] for row in rows]
    values = np.asarray(
        [value for value in raw_values if value is not None],
        dtype=float,
    )
    count = len(values)
    if count:
        q1, median, q3 = np.percentile(values, [25, 50, 75])
        return {
            "group": group,
            "count": count,
            "missing_count": len(raw_values) - count,
            "minimum": float(np.min(values)),
            "maximum": float(np.max(values)),
            "mean": float(np.mean(values)),
            "median": float(median),
            "standard_deviation": (
                float(np.std(values, ddof=1)) if count > 1 else None
            ),
            "q1": float(q1),
            "q3": float(q3),
            "iqr": float(q3 - q1),
            "total": float(np.sum(values)),
            "percentiles": {
                f"{percentile:g}": float(np.percentile(values, percentile))
                for percentile in percentiles
            },
        }
    return {
        "group": group,
        "count": 0,
        "missing_count": len(raw_values),
        "minimum": None,
        "maximum": None,
        "mean": None,
        "median": None,
        "standard_deviation": None,
        "q1": None,
        "q3": None,
        "iqr": None,
        "total": None,
        "percentiles": {
            f"{percentile:g}": None for percentile in percentiles
        },
    }


def _correlation_matrix(rows):
    keys = ("gross_load", "heat_input", "co2_mass", "so2_mass", "nox_mass")
    matrix = []
    for left in keys:
        cells = []
        for right in keys:
            pairs = [
                (row[left], row[right])
                for row in rows
                if row[left] is not None and row[right] is not None
            ]
            if left == right and len(pairs) < 2:
                correlation = None
            elif len(pairs) < 2:
                correlation = None
            else:
                values = np.asarray(pairs, dtype=float)
                correlation = _finite_number(
                    np.corrcoef(values[:, 0], values[:, 1])[0, 1]
                )
            color = ""
            if correlation is not None:
                alpha = round(abs(correlation), 2)
                rgb = "45, 113, 189" if correlation >= 0 else "37, 17, 1"
                color = f"rgba({rgb}, {alpha})"
            cells.append({
                "value": correlation,
                "color": color,
            })
        matrix.append({"label": VARIABLES[left][0], "cells": cells})
    return {
        "labels": [VARIABLES[key][0] for key in keys],
        "rows": matrix,
    }


def build_analysis(params, options=None):
    """Apply reproducible filters and return summaries and visualization data."""
    selections = {
        key: str(params.get(key, "") or "").strip()
        for key in FILTER_FIELDS
    }
    selections.update({
        "control": str(params.get("control", "") or "").strip(),
        "program_code": str(params.get("program_code", "") or "").strip(),
    })
    if options is None:
        options = _available_options()
    if selections["state"] and selections["state"] not in options["states"]:
        raise ValueError("Choose a state available in the annual records.")
    if selections["facility_id"] and selections["facility_id"] not in {
        item["id"] for item in options["facilities"]
    }:
        raise ValueError("Choose a facility available in the annual records.")
    if selections["unit_id"] and selections["unit_id"] not in {
        str(item["id"]) for item in options["units"]
    }:
        raise ValueError("Choose a unit available in the annual records.")
    if selections["fuel"] and selections["fuel"] not in options["fuels"]:
        raise ValueError("Choose a fuel available in the annual records.")
    if (
        selections["unit_type"]
        and selections["unit_type"] not in options["unit_types"]
    ):
        raise ValueError("Choose a unit type available in the annual records.")
    year_from = _parse_year(params, "year_from")
    year_to = _parse_year(params, "year_to")
    min_operating_time = _parse_threshold(params, "min_operating_time")
    min_gross_load = _parse_threshold(params, "min_gross_load")
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError("The starting year cannot exceed the ending year.")
    percentiles = []
    selected_percentiles = str(params.get("percentiles", "") or "").strip()
    if selected_percentiles:
        for value in selected_percentiles.split(","):
            percentile = _finite_number(value.strip())
            if percentile is None or not 0 <= percentile <= 100:
                raise ValueError("Percentiles must be finite values from 0 to 100.")
            if percentile not in percentiles:
                percentiles.append(percentile)

    variable = str(params.get("variable", "co2_mass") or "co2_mass").strip()
    if variable not in VARIABLES:
        raise ValueError("Choose a supported analysis variable.")
    chart_type = str(params.get("chart", "bar") or "bar").strip()
    if chart_type not in CHART_TYPES:
        raise ValueError("Choose a supported visualization.")
    group_by = str(params.get("group_by", "year") or "").strip()
    if group_by not in GROUPS and group_by:
        raise ValueError("Choose a supported grouping field.")
    aggregation = str(params.get("aggregation", "mean") or "mean").strip()
    if aggregation not in ("mean", "sum"):
        raise ValueError("Choose mean or total aggregation.")
    if aggregation == "sum" and variable not in RAW_VARIABLES:
        raise ValueError("Totals are only available for raw measurements.")

    query_selections = dict(selections)
    if query_selections["unit_id"]:
        query_selections["unit_id"] = int(query_selections["unit_id"])
    base_query = _apply_dimensions(_analysis_query(), query_selections)
    if year_to is not None:
        base_query = base_query.filter(AnnualRecord.reporting_year <= year_to)

    baseline_query = base_query
    if year_from is not None:
        baseline_query = baseline_query.filter(
            AnnualRecord.reporting_year >= year_from - 1
        )
    baseline_rows = baseline_query.order_by(
        AnnualRecord.reporting_year.asc()
    ).all()
    previous_records = {
        (unit.id, record.reporting_year): record
        for record, unit, _ in baseline_rows
    }

    selected_query = base_query
    if year_from is not None:
        selected_query = selected_query.filter(
            AnnualRecord.reporting_year >= year_from
        )
    if min_operating_time is not None:
        selected_query = selected_query.filter(
            AnnualRecord.operating_time >= min_operating_time
        )
    if min_gross_load is not None:
        selected_query = selected_query.filter(
            AnnualRecord.gross_load >= min_gross_load
        )
    selected_records = selected_query.order_by(
        Facility.state,
        Facility.facility_name,
        Unit.epa_unit_id,
        AnnualRecord.reporting_year,
    ).all()

    rows = []
    for record, unit, facility in selected_records:
        row = {
            "state": facility.state,
            "facility_name": facility.facility_name,
            "facility_id": facility.epa_facility_id,
            "unit_label": f"{facility.facility_name} — {unit.epa_unit_id}",
            "unit_id": unit.epa_unit_id,
            "unit_type": unit.unit_type,
            "fuel": unit.primary_fuel,
            "secondary_fuel": unit.secondary_fuel,
            "so2_control": record.so2_control,
            "nox_control": record.nox_control,
            "pm_control": record.pm_control,
            "program_code": record.program_code,
            "year": record.reporting_year,
            "latitude": _finite_number(facility.latitude),
            "longitude": _finite_number(facility.longitude),
            "operating_time": _finite_number(record.operating_time),
            "gross_load": _finite_number(record.gross_load),
            "steam_load": _finite_number(record.steam_load),
            "heat_input": _finite_number(record.heat_input),
            "co2_mass": _finite_number(record.co2_mass),
            "so2_mass": _finite_number(record.so2_mass),
            "nox_mass": _finite_number(record.nox_mass),
        }
        for key in VARIABLES:
            row[key] = _metric_value(record, key)
        previous = previous_records.get((unit.id, record.reporting_year - 1))
        previous_value = _metric_value(previous, variable) if previous else None
        current_value = row[variable]
        absolute_change = (
            current_value - previous_value
            if current_value is not None and previous_value is not None
            else None
        )
        row.update({
            "previous_year_value": previous_value,
            "year_over_year_absolute": absolute_change,
            "year_over_year_percent": (
                absolute_change / abs(previous_value) * 100
                if absolute_change is not None and previous_value != 0
                else None
            ),
        })
        rows.append(row)

    buckets = defaultdict(list)
    for row in rows:
        buckets[_group_label(row, group_by)].append(row)
    if not group_by and not buckets:
        buckets["All records"] = []

    stats = [
        _summarize(label, group_rows, variable, percentiles)
        for label, group_rows in sorted(
            buckets.items(),
            key=lambda item: item[0].casefold(),
        )
    ]
    statistic_ranges = [
        value
        for row in stats
        for value in (row["minimum"], row["maximum"])
        if value is not None
    ]
    overall_minimum = min(statistic_ranges) if statistic_ranges else 0
    overall_maximum = max(statistic_ranges) if statistic_ranges else 0
    overall_range = overall_maximum - overall_minimum
    if overall_range == 0:
        overall_range = 1
    for row in stats:
        if row["minimum"] is None:
            row["plot"] = None
            continue
        row["plot"] = {
            key: (row[key] - overall_minimum) / overall_range * 100
            for key in ("minimum", "q1", "median", "q3", "maximum")
        }
    missing_summary = [
        {
            "key": key,
            "label": VARIABLES[key][0],
            "units": VARIABLES[key][1],
            "missing": sum(row[key] is None for row in rows),
            "count": len(rows),
        }
        for key in VARIABLES
    ]
    for key, label in (
        ("state", "State"),
        ("facility_name", "Facility name"),
        ("unit_type", "Unit type"),
        ("fuel", "Primary fuel"),
        ("secondary_fuel", "Secondary fuel"),
        ("so2_control", "SO2 control"),
        ("nox_control", "NOx control"),
        ("pm_control", "PM control"),
        ("program_code", "Emissions program"),
        ("latitude", "Facility latitude"),
        ("longitude", "Facility longitude"),
    ):
        missing_summary.append({
            "key": key,
            "label": label,
            "units": "",
            "missing": sum(
                row[key] is None
                or (isinstance(row[key], str) and not row[key].strip())
                for row in rows
            ),
            "count": len(rows),
        })

    grouped_values = []
    for label, group_rows in buckets.items():
        usable = [row[variable] for row in group_rows if row[variable] is not None]
        if usable:
            grouped_values.append({
                "group": label,
                "value": (
                    float(sum(usable))
                    if aggregation == "sum"
                    else float(sum(usable) / len(usable))
                ),
                "count": len(usable),
            })
    grouped_values.sort(key=lambda item: item["group"].casefold())
    rankings = sorted(
        grouped_values,
        key=lambda item: item["value"],
        reverse=True,
    )

    numeric_values = [row[variable] for row in rows if row[variable] is not None]
    histogram = []
    if numeric_values:
        lower = min(numeric_values)
        upper = max(numeric_values)
        bin_count = max(1, min(20, int(math.ceil(math.sqrt(len(numeric_values))))))
        width = (upper - lower) / bin_count if upper > lower else 1.0
        counts = [0] * bin_count
        for value in numeric_values:
            index = min(int((value - lower) / width), bin_count - 1)
            counts[index] += 1
        histogram = [
            {
                "label": (
                    f"{lower + index * width:.4g}–"
                    f"{lower + (index + 1) * width:.4g}"
                ),
                "count": count,
            }
            for index, count in enumerate(counts)
        ]

    map_markers = [
        {
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "value": row[variable],
            "label": (
                f"{row['facility_name']} ({row['facility_id']}), "
                f"{row['year']}: {row[variable]} {VARIABLES[variable][1]}"
            ),
        }
        for row in rows
        if row["latitude"] is not None
        and row["longitude"] is not None
        and -90 <= row["latitude"] <= 90
        and -180 <= row["longitude"] <= 180
        and row[variable] is not None
    ]
    summary = {
        "records": len(rows),
        "facilities": len({row["facility_id"] for row in rows}),
        "units": len({(row["facility_id"], row["unit_id"]) for row in rows}),
        "years": len({row["year"] for row in rows}),
    }
    return {
        "rows": rows,
        "preview_rows": rows[:200],
        "summary": summary,
        "missing_summary": missing_summary,
        "stats": stats,
        "rankings": rankings,
        "chart_data": grouped_values,
        "histogram": histogram,
        "scatter": [
            {
                "x": row["gross_load"],
                "y": row[variable],
                "label": f"{row['facility_name']} ({row['unit_id']}), {row['year']}",
            }
            for row in rows
            if row["gross_load"] is not None and row[variable] is not None
        ],
        "correlation": _correlation_matrix(rows),
        "map_markers": map_markers,
        "options": options,
        "variables": [
            {"key": key, "label": label, "units": units}
            for key, (label, units) in VARIABLES.items()
        ],
        "available_fields": [
            "State",
            "Facility name and ID",
            "Generating unit",
            "Reporting year",
            "Unit type",
            "Primary and secondary fuel",
            "Operating time",
            "Gross load",
            "Heat input",
            "CO2, SO2, and NOx mass",
            "SO2, NOx, and PM control status",
            "Emissions program",
            "Facility latitude and longitude when available",
        ] + [
            label for key, (label, _) in VARIABLES.items()
            if key not in RAW_VARIABLES
        ],
        "groups": [{"key": key, "label": label} for key, label in GROUPS.items()],
        "chart_types": [
            {"key": key, "label": label}
            for key, label in CHART_TYPES.items()
        ],
        "selected": {
            **selections,
            "year_from": str(year_from or ""),
            "year_to": str(year_to or ""),
            "min_operating_time": str(
                params.get("min_operating_time", "") or ""
            ).strip(),
            "min_gross_load": str(params.get("min_gross_load", "") or "").strip(),
            "variable": variable,
            "chart": chart_type,
            "group_by": group_by,
            "aggregation": aggregation,
            "percentiles": selected_percentiles,
        },
        "percentile_values": [f"{value:g}" for value in percentiles],
        "units": VARIABLES[variable][1],
        "variable_label": VARIABLES[variable][0],
        "chart_type": chart_type,
        "group_label": GROUPS.get(group_by, "All records"),
        "aggregation_label": aggregation.capitalize(),
    }
