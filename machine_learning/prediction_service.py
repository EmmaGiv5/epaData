import joblib
import pandas as pd

from pathlib import Path

MODEL_DIR = (
    Path(__file__).resolve().parents[1]
    / "saved_models"
)


def load_model(model_name):

    model_path = MODEL_DIR / f"{model_name}.joblib"

    if not model_path.exists():
        raise FileNotFoundError(
            f"{model_name} has not been trained yet."
        )

    saved = joblib.load(model_path)

    return saved


def generate_prediction(model_name, inputs):

    saved = load_model(model_name)

    model = saved["model"]
    features = saved["features"]

    dataframe = pd.DataFrame(
        [{feature: inputs.get(feature) for feature in features}]
    )

    prediction = model.predict(dataframe)[0]

    return {
        "prediction": float(prediction),
        "model": model_name,
        "mae": float(saved["mae"]),
        "r2": float(saved["r2"]),
    }