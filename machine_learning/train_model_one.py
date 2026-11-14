# Train Prediction model for selected targets 

import os
import joblib

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics import mean_absolute_error, r2_score

from machine_learning.data_preparation import get_training_data 


def train_model_one():

    df = get_training_data()

    features = [
        "gross_load",
        "heat_input",
        "operating_time",
        "year",
        "primary_fuel",
        "unit_type",
        "state",
    ]

    target = "co2_mass"

    df = df.sort_values("year")

    years = sorted(df["year"].unique())

    if len(years) < 3:
        raise ValueError(
            "At least three reporting years are needed "
            "for chronological model evaluation."
        )

    test_year = years[-1]

    train = df[df["year"] < test_year]
    test = df[df["year"] == test_year]

    X_train = train[features]
    y_train = train[target]

    X_test = test[features]
    y_test = test[target]

    numeric_features = [
        "gross_load",
        "heat_input",
        "operating_time",
        "year",
    ]

    categorical_features = [
        "primary_fuel",
        "unit_type",
        "state",
    ]

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                SimpleImputer(strategy="median"),
                numeric_features
            ),
            (
                "categorical",
                Pipeline([
                    (
                        "imputer",
                        SimpleImputer(strategy="most_frequent")
                    ),
                    (
                        "encoder",
                        OneHotEncoder(handle_unknown="ignore")
                    )
                ]),
                categorical_features
            )
        ]
    )

    model = Pipeline([
        ("preprocessing", preprocessing),
        (
            "regressor",
            RandomForestRegressor(
                n_estimators=200,
                random_state=42,
                min_samples_leaf=2,
                n_jobs=-1
            )
        )
    ])

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    os.makedirs("saved_models", exist_ok=True)

    joblib.dump(
        {
            "model": model,
            "features": features,
            "test_year": test_year,
            "mae": mae,
            "r2": r2,
        },
        "saved_models/model_one.joblib"
    )

    return {
        "model": "Prediction Model 1",
        "mae": mae,
        "r2": r2,
        "test_year": test_year,
    }