"""One-variable-at-a-time sensitivity curves and named scenarios.

These describe how a fitted model responds to input changes. They do not show
a real-world causal effect.
"""

import math

import numpy as np

from machine_learning import config
from machine_learning.prediction_service import (
    load_model,
    normalize_inputs,
    predict_rows,
)

DEFAULT_SCENARIOS = [
    {"name": "Baseline", "multipliers": {}},
    {"name": "Gross load +10%", "multipliers": {"gross_load": 1.10}},
    {"name": "Heat input -5%", "multipliers": {"heat_input": 0.95}},
    {"name": "Operating time +10%", "multipliers": {"operating_time": 1.10}},
    {
        "name": "High efficiency (load +10%, heat input -5%)",
        "multipliers": {"gross_load": 1.10, "heat_input": 0.95},
    },
]


def _num(value):
    """JSON cannot hold NaN/inf, so return None instead."""
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def _pct(new, base):
    return None if not base else (new - base) / base * 100


def range_warnings(saved, inputs):
    warnings = []
    for key in config.NUMERIC_FEATURES:
        value = inputs.get(key)
        if value is None or not math.isfinite(value):
            continue
        low, high = saved["train_ranges"][key]
        if not low <= value <= high:
            label = config.VARIABLES[key]["label"]
            warnings.append(
                f"{label} ({value:,.4g}) is outside the training range "
                f"({low:,.4g} to {high:,.4g})."
            )
    for key in config.CATEGORICAL_FEATURES:
        value = inputs.get(key)
        if value and value not in saved["categories"][key]:
            warnings.append(f"{key.replace('_', ' ').title()} '{value}' was not in the training data.")
    return warnings


def model_metadata(saved):
    return {
        "model": saved["label"],
        "features": saved["features"],
        "target": saved["target"],
        "params": saved["params"],
        "train_target_years": saved["train_target_years"],
        "validation_year": saved["validation_year"],
        "test_year": saved["test_year"],
        "pipeline_version": saved["pipeline_version"],
    }


def oat_sweep(model_name, baseline, variable, low=None, high=None, steps=25):
    if variable not in config.NUMERIC_FEATURES:
        raise ValueError("Choose a numeric input variable to vary.")

    saved = load_model(model_name)
    base = normalize_inputs(baseline)
    base_value = base[variable]
    train_low, train_high = saved["train_ranges"][variable]

    if low is None or high is None:
        if not math.isfinite(base_value) or base_value == 0:
            low, high = train_low, train_high
        else:
            low, high = base_value * 0.5, base_value * 1.5
    low, high = float(low), float(high)
    if low < 0 or high <= low:
        raise ValueError("The maximum must be larger than the minimum, and both must be 0 or more.")

    steps = int(min(max(steps, 2), 101))
    values = np.linspace(low, high, steps)

    rows = [{**base, variable: float(v)} for v in values]
    baseline_prediction = float(predict_rows(model_name, [base])[0])
    predictions = predict_rows(model_name, rows)

    points = []
    for value, prediction in zip(values, predictions):
        points.append({
            "input": float(value),
            "prediction": float(prediction),
            "abs_change": float(prediction - baseline_prediction),
            "pct_change": _num(_pct(prediction, baseline_prediction)),
            "out_of_range": not (train_low <= value <= train_high),
        })

    return {
        "variable": variable,
        "label": config.VARIABLES[variable]["label"],
        "unit": config.VARIABLES[variable]["unit"],
        "baseline": {"input": _num(base_value), "prediction": baseline_prediction},
        "train_range": [train_low, train_high],
        "points": points,
        "metadata": model_metadata(saved),
    }


def run_scenarios(model_name, baseline, scenarios=None, fuel=None):
    saved = load_model(model_name)
    base = normalize_inputs(baseline)

    specs = list(scenarios) if scenarios else list(DEFAULT_SCENARIOS)
    if fuel and fuel != base.get("primary_fuel"):
        specs.append({"name": f"Fuel changed to {fuel}", "set": {"primary_fuel": fuel}})

    rows, changed_inputs = [], []
    for spec in specs:
        row, changes = dict(base), {}
        for key, factor in (spec.get("multipliers") or {}).items():
            if key not in config.NUMERIC_FEATURES:
                raise ValueError(f"Cannot scale '{key}'.")
            if math.isfinite(row[key]):
                row[key] = max(0.0, row[key] * float(factor))
                changes[key] = row[key]
        for key, value in (spec.get("set") or {}).items():
            if key not in config.CATEGORICAL_FEATURES:
                raise ValueError(f"Cannot set '{key}'.")
            row[key] = value
            changes[key] = value
        rows.append(row)
        changed_inputs.append(changes)

    predictions = predict_rows(model_name, rows)
    baseline_prediction = float(predict_rows(model_name, [base])[0])

    results = []
    for spec, row, changes, prediction in zip(specs, rows, changed_inputs, predictions):
        results.append({
            "name": spec["name"],
            "changed_inputs": {k: (_num(v) if not isinstance(v, str) else v) for k, v in changes.items()},
            "prediction": float(prediction),
            "abs_change": float(prediction - baseline_prediction),
            "pct_change": _num(_pct(prediction, baseline_prediction)),
            "warnings": range_warnings(saved, row),
        })

    return {
        "baseline_prediction": baseline_prediction,
        "scenarios": results,
        "metadata": model_metadata(saved),
    }
