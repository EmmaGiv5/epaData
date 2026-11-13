import numpy as np

from .prediction_service import load_model


def calculate_sensitivity(
    inputs,
    variable,
    minimum,
    maximum,
    steps=20
):

    saved = load_model("model_two")

    model = saved["model"]

    features = saved["features"]

    if variable not in (
        "gross_load",
        "heat_input",
        "operating_time",
    ):
        raise ValueError("Invalid sensitivity variable.")

    if minimum >= maximum:
        raise ValueError("Minimum must be below maximum.")

    if steps < 2 or steps > 100:
        raise ValueError("Steps must be between 2 and 100.")

    baseline_prediction = model.predict(
        [{feature: inputs[feature] for feature in features}]
    )[0]

    values = np.linspace(minimum, maximum, steps)

    results = []

    for value in values:

        modified_inputs = inputs.copy()

        modified_inputs[variable] = float(value)

        prediction = model.predict([
            {
                feature: modified_inputs[feature]
                for feature in features
            }
        ])[0]

        absolute_change = (
            float(prediction) - float(baseline_prediction)
        )

        percentage_change = (
            absolute_change / baseline_prediction * 100
            if baseline_prediction != 0
            else None
        )

        results.append({
            "input_value": float(value),
            "prediction": float(prediction),
            "absolute_change": float(absolute_change),
            "percentage_change": (
                float(percentage_change)
                if percentage_change is not None
                else None
            ),
        })

    return {
        "variable": variable,
        "baseline_prediction": float(baseline_prediction),
        "results": results,
    }
def compare_scenarios(inputs, scenarios):

    saved = load_model("model_two")
    model = saved["model"]
    features = saved["features"]

    baseline_inputs = {
        feature: inputs[feature]
        for feature in features
    }

    baseline_prediction = float(
        model.predict([baseline_inputs])[0]
    )

    results = [{
        "scenario": "Baseline",
        "prediction": baseline_prediction,
        "absolute_change": 0,
        "percentage_change": 0,
    }]

    for scenario_name, changes in scenarios.items():

        modified = baseline_inputs.copy()

        for variable, value in changes.items():

            if variable not in (
                "gross_load",
                "heat_input",
                "operating_time",
                "primary_fuel",
                "unit_type",
            ):
                raise ValueError(
                    f"Unsupported scenario variable: {variable}"
                )

            modified[variable] = value

        prediction = float(
            model.predict([modified])[0]
        )

        difference = prediction - baseline_prediction

        percentage = (
            difference / baseline_prediction * 100
            if baseline_prediction != 0
            else None
        )

        results.append({
            "scenario": scenario_name,
            "prediction": prediction,
            "absolute_change": difference,
            "percentage_change": percentage,
        })

    return results