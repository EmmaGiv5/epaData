
import numpy as np
import pandas as pd
import pytest

from machine_learning import config, prediction_service, sensitivity 

from machine_learning.data_preparation import build_forecast_frame
from machine_learning.training import train_all


def synthetic_records(n_units=60, years=range(2018, 2025), seed=0):
    rng = np.random.default_rng(seed)
    fuels = ["Coal", "Natural Gas"]
    factor = {"Coal": 2.2, "Natural Gas": 1.2}
    rows = []
    for unit in range(n_units):
        fuel = fuels[unit % 2]
        state = ["KY", "TN", "AL"][unit % 3]
        base_load = rng.uniform(1e4, 1e6)
        for year in years:
            load = base_load * rng.uniform(0.8, 1.2)
            heat = load * rng.uniform(9, 11)
            rows.append({
                "unit_id": unit, "year": year,
                "operating_time": rng.uniform(1000, 8000),
                "gross_load": load, "heat_input": heat,
                "co2_mass": heat * factor[fuel] / 20,
                "primary_fuel": fuel, "unit_type": "Boiler", "state": state,
            })
    return pd.DataFrame(rows)


@pytest.fixture()
def trained(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODEL_DIR", tmp_path)
    prediction_service.clear_cache()
    df = build_forecast_frame(synthetic_records())
    train_all(df=df, model_dir=tmp_path)
    return df


def baseline_inputs():
    return {
        "gross_load": 5e5, "heat_input": 5e6, "operating_time": 6000,
        "co2_mass_prev": 3e5, "primary_fuel": "Coal",
        "unit_type": "Boiler", "state": "KY",
    }


def test_only_consecutive_years_are_paired():
    df = synthetic_records(n_units=2, years=[2018, 2019, 2021])
    frame = build_forecast_frame(df)
    assert set(frame["year"]) == {2018}  # 2019 -> 2021 has a gap


def test_chronological_split_and_files(trained, tmp_path):
    for name in config.MODEL_NAMES:
        assert (tmp_path / f"{name}.joblib").exists()
    saved = prediction_service.load_model("ridge")
    assert saved["train_target_years"][1] < saved["validation_year"] < saved["test_year"]


def test_baseline_is_constant(trained):
    rows = [baseline_inputs(), {**baseline_inputs(), "gross_load": 9e5}]
    preds = prediction_service.predict_rows("baseline_median", rows)
    assert preds[0] == preds[1]


def test_sweep_flags_out_of_range(trained):
    result = sensitivity.oat_sweep(
        "ridge", baseline_inputs(), "gross_load", low=1, high=5e7, steps=10
    )
    assert any(p["out_of_range"] for p in result["points"])
    assert result["points"][0]["pct_change"] is None or math.isfinite(result["points"][0]["pct_change"])


def test_scenarios_compare_with_baseline(trained):
    result = sensitivity.run_scenarios("ridge", baseline_inputs(), fuel="Natural Gas")
    names = [s["name"] for s in result["scenarios"]]
    assert names[0] == "Baseline" and "Fuel changed to Natural Gas" in names
    assert result["scenarios"][0]["abs_change"] == pytest.approx(0)


def test_invalid_input_rejected(trained):
    with pytest.raises(ValueError):
        prediction_service.normalize_inputs({**baseline_inputs(), "gross_load": -5})
