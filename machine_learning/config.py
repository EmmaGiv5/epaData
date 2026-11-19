"""Shared settings for the prediction and sensitivity modules."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = PROJECT_ROOT / "saved_models"
PIPELINE_VERSION = "phase2-v1"

# Prediction task: use a unit's values in year t to predict its CO2 in year t+1.
# co2_mass_prev is the CO2 reported in the latest observed year (year t).
# Heat input is NOT leakage here because the target is a different year's CO2.
TARGET = "co2_mass_next"

NUMERIC_FEATURES = [
    "gross_load",
    "heat_input",
    "operating_time",
    "co2_mass_prev",
]
CATEGORICAL_FEATURES = [
    "primary_fuel",
    "unit_type",
    "state",
]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Label and unit for every numeric input, used by the charts and exports.
VARIABLES = {
    "gross_load": {"label": "Gross load", "unit": "MWh"},
    "heat_input": {"label": "Heat input", "unit": "mmBtu"},
    "operating_time": {"label": "Operating time", "unit": "hours"},
    "co2_mass_prev": {"label": "CO2 in latest observed year", "unit": "short tons"},
}
TARGET_UNIT = "short tons"

# Whitelist of model ids (also prevents arbitrary file names reaching joblib.load)
MODEL_NAMES = {
    "baseline_median": "Baseline (median)",
    "ridge": "Ridge regression",
    "random_forest": "Random forest",
}
