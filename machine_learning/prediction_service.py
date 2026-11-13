import joblib
import pandas as pd

from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1] / "saved_models"


def predict_co2(inputs):

    results = {}

    models = {
        "Prediction Model 1": MODEL_DIR / "model_one.joblib",
        "Sensitivity Analysis Model 2": MODEL_DIR / "model_two.joblib",
    }

    for name, path in models.items():

        if not path.exists():
            raise FileNotFoundError(
                f"Model not found: {path}"
            )

        saved = joblib.load(path)

        model = saved["model"]
        features = saved["features"]

        dataframe = pd.DataFrame(
            [{key: inputs[key] for key in features}]
        )

        prediction = model.predict(dataframe)[0]

        results[name] = round(float(prediction), 2)

    return results