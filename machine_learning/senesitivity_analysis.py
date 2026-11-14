# analyze sensitivity of the model to changes in input variables

from machine_learning.prediction_service import predict_co2


def calculate_sensitivity(
    inputs,
    variable,
    model_name="model_one",
    percentage=10
):

    if variable not in (
        "gross_load",
        "heat_input",
        "operating_time",
    ):
        raise ValueError("Invalid sensitivity variable.")

    if not 0 <= percentage <= 100:
        raise ValueError("Invalid percentage change.")

    original_value = float(inputs[variable])

    if original_value < 0:
        raise ValueError("Input cannot be negative.")

    baseline = predict_co2(inputs, model_name)

    change = original_value * percentage / 100

    increased = inputs.copy()
    decreased = inputs.copy()

    increased[variable] = original_value + change
    decreased[variable] = max(0, original_value - change)

    higher_prediction = predict_co2(
        increased, model_name
    )

    lower_prediction = predict_co2(
        decreased, model_name
    )

    return {
        "variable": variable,
        "baseline_input": original_value,
        "baseline_prediction": baseline,
        "increased": {
            "input": increased[variable],
            "prediction": higher_prediction,
            "absolute_change": higher_prediction - baseline,
        },
        "decreased": {
            "input": decreased[variable],
            "prediction": lower_prediction,
            "absolute_change": lower_prediction - baseline,
        },
    }