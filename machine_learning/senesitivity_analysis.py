from machine_learning.prediction_service import predict_co2


def calculate_sensitivity(inputs):

    variables = [
        "gross_load",
        "heat_input",
        "operating_time",
    ]

    results = {}

    for variable in variables:

        original_value = float(inputs[variable])

        if original_value <= 0:
            change = max(abs(original_value) * 0.10, 1)
        else:
            change = original_value * 0.10

        increased = inputs.copy()
        decreased = inputs.copy()

        increased[variable] = original_value + change
        decreased[variable] = max(0, original_value - change)

        original_prediction = predict_co2(inputs)
        higher_prediction = predict_co2(increased)
        lower_prediction = predict_co2(decreased)

        results[variable] = {}

        for model in original_prediction:

            results[variable][model] = {
                "original": original_prediction[model],
                "increased": higher_prediction[model],
                "decreased": lower_prediction[model],
            }

    return results