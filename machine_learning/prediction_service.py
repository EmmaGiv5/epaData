# Predict different measurements 

import joblib
import pandas as pd

from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1] / "saved_models"


MODEL_FILES = {
    "model_one": MODEL_DIR / "model_one.joblib",
    "model_two": MODEL_DIR / "model_two.joblib",
}


def predict_co2(inputs, model_name="model_one"):

    if model_name not in MODEL_FILES:
        raise ValueError("Invalid prediction model.")

    model_path = MODEL_FILES[model_name]

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    saved = joblib.load(model_path)

    model = saved["model"]
    features = saved["features"]

    dataframe = pd.DataFrame([
        {key: inputs[key] for key in features}
    ])

    prediction = model.predict(dataframe)[0]

    return round(float(prediction), 2)