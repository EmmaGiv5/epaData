"""Train a baseline and two candidate models on a chronological split.

Split (by the year being predicted):
    train      = all target years before the validation year
    validation = second-most-recent target year
    test       = most recent target year
"""

import json
import math
from datetime import datetime, timezone

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from machine_learning import config
from machine_learning.data_preparation import coerce_frame, get_forecast_data


def candidate_models():
    return {
        "baseline_median": DummyRegressor(strategy="median"),
        "ridge": Ridge(alpha=1.0),
        "random_forest": RandomForestRegressor(
            n_estimators=200, min_samples_leaf=2, random_state=42, n_jobs=-1
        ),
    }


def build_pipeline(regressor):
    """Shared preprocessing. log1p makes the skewed MWh/ton values well behaved,
    and the target is modeled in log space then converted back to short tons."""
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("log", FunctionTransformer(np.log1p, validate=False)),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    preprocessing = ColumnTransformer([
        ("numeric", numeric, config.NUMERIC_FEATURES),
        ("categorical", categorical, config.CATEGORICAL_FEATURES),
    ])
    return TransformedTargetRegressor(
        regressor=Pipeline([("preprocessing", preprocessing), ("regressor", regressor)]),
        func=np.log1p,
        inverse_func=np.expm1,
    )


def evaluate(y_true, y_pred):
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    nonzero = y_true != 0
    mape = (
        float(np.mean(np.abs((y_true[nonzero] - y_pred[nonzero]) / y_true[nonzero])) * 100)
        if nonzero.any() else None
    )
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(math.sqrt(mean_squared_error(y_true, y_pred))),
        "r2": float(r2_score(y_true, y_pred)),
        "mape": mape,
        "n": int(len(y_true)),
    }


def _simple_params(regressor):
    return {
        key: value for key, value in regressor.get_params().items()
        if isinstance(value, (int, float, str, bool, type(None)))
    }


def train_all(df=None, model_dir=None):
    df = get_forecast_data() if df is None else df
    model_dir = config.MODEL_DIR if model_dir is None else model_dir
    model_dir.mkdir(parents=True, exist_ok=True)

    target_years = sorted(int(y) for y in df["target_year"].unique())
    if len(target_years) < 3:
        raise ValueError(
            "At least three predicted years (four reporting years with "
            "consecutive records) are needed for train/validation/test splits."
        )
    test_year, val_year = target_years[-1], target_years[-2]

    train = df[df["target_year"] < val_year]
    val = df[df["target_year"] == val_year]
    test = df[df["target_year"] == test_year]

    X_train = coerce_frame(train[config.FEATURES])
    y_train = train[config.TARGET]

    train_ranges = {
        column: [float(X_train[column].min()), float(X_train[column].max())]
        for column in config.NUMERIC_FEATURES
    }
    categories = {
        column: sorted(str(v) for v in X_train[column].dropna().unique())
        for column in config.CATEGORICAL_FEATURES
    }

    # Reference that needs no model: "next year = this year"
    persistence = {
        "validation": evaluate(val[config.TARGET], val["co2_mass_prev"]),
        "test": evaluate(test[config.TARGET], test["co2_mass_prev"]),
    }

    summaries = []
    for name, regressor in candidate_models().items():
        model = build_pipeline(regressor)
        model.fit(X_train, y_train)

        metrics = {
            "validation": evaluate(
                val[config.TARGET], model.predict(coerce_frame(val[config.FEATURES]))
            ),
            "test": evaluate(
                test[config.TARGET], model.predict(coerce_frame(test[config.FEATURES]))
            ),
        }

        artifact = {
            "name": name,
            "label": config.MODEL_NAMES[name],
            "model": model,
            "features": config.FEATURES,
            "target": config.TARGET,
            "metrics": metrics,
            "persistence": persistence,
            "train_target_years": [int(train["target_year"].min()), int(train["target_year"].max())],
            "validation_year": val_year,
            "test_year": test_year,
            "train_rows": int(len(train)),
            "train_ranges": train_ranges,
            "categories": categories,
            "params": _simple_params(regressor),
            "pipeline_version": config.PIPELINE_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        joblib.dump(artifact, model_dir / f"{name}.joblib")

        summaries.append({k: v for k, v in artifact.items() if k != "model"})

    with open(model_dir / "metadata.json", "w", encoding="utf-8") as handle:
        json.dump(summaries, handle, indent=2, default=str)

    return summaries
