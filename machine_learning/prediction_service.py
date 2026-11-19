"""Load saved models once and make predictions from them."""

import math
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd

from machine_learning import config
from machine_learning.data_preparation import coerce_frame


@lru_cache(maxsize=None)
def load_model(name):
    if name not in config.MODEL_NAMES:
        raise ValueError(f"Unknown model: {name}")
    path = config.MODEL_DIR / f"{name}.joblib"
    if not path.exists():
        raise FileNotFoundError(
            f"Model '{name}' has not been trained yet. Run train_models.py."
        )
    return joblib.load(path)


def clear_cache():
    """Call after retraining while the app is running."""
    load_model.cache_clear()


def available_models():
    return [n for n in config.MODEL_NAMES if (config.MODEL_DIR / f"{n}.joblib").exists()]


def normalize_inputs(raw):
    """Validate user-supplied inputs. Missing numbers stay NaN (the pipeline
    imputes them); they are never silently turned into zero."""
    clean = {}
    for key in config.NUMERIC_FEATURES:
        value = raw.get(key)
        if value is None or value == "":
            clean[key] = float("nan")
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{config.VARIABLES[key]['label']} must be a number.")
        if not math.isfinite(number) or number < 0:
            raise ValueError(
                f"{config.VARIABLES[key]['label']} must be a non-negative number."
            )
        clean[key] = number
    for key in config.CATEGORICAL_FEATURES:
        value = raw.get(key)
        clean[key] = str(value).strip() if value not in (None, "") else None
    return clean


def predict_rows(name, rows):
    saved = load_model(name)
    frame = coerce_frame(pd.DataFrame(rows)[saved["features"]])
    return np.asarray(saved["model"].predict(frame), dtype=float)


def predict_all(inputs):
    """Predicted next-year CO2 (short tons) from every trained model."""
    clean = normalize_inputs(inputs)
    return {
        name: float(predict_rows(name, [clean])[0]) for name in available_models()
    }
