"""JSON endpoints used by the prediction / sensitivity panel on /comparisons."""

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models import AnnualRecord, Facility, Unit
from machine_learning import config
from machine_learning.data_preparation import get_unit_baseline
from machine_learning.prediction_service import (
    available_models,
    load_model,
    predict_all,
)
from machine_learning.sensitivity import oat_sweep, run_scenarios

ml_bp = Blueprint("ml", __name__, url_prefix="/api/ml")


def _error(message, status=400):
    return jsonify({"error": message}), status


@ml_bp.errorhandler(ValueError)
def _value_error(exc):
    return _error(str(exc), 400)


@ml_bp.errorhandler(FileNotFoundError)
def _missing_model(exc):
    return _error(str(exc), 503)


@ml_bp.errorhandler(SQLAlchemyError)
def _db_error(exc):
    return _error("Could not load data from the database.", 500)


def _body():
    return request.get_json(silent=True) or {}


def _model_name(data):
    name = data.get("model", "ridge")
    if name not in config.MODEL_NAMES:
        raise ValueError("Choose a valid model.")
    return name


def _optional_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError("Minimum and maximum must be numbers.")


@ml_bp.route("/metrics")
def metrics():
    names = available_models()
    if not names:
        return _error("No trained models found. Run train_models.py first.", 503)

    models = []
    for name in names:
        saved = load_model(name)
        models.append({
            "name": name,
            "label": saved["label"],
            "metrics": saved["metrics"],
            "params": saved["params"],
            "train_target_years": saved["train_target_years"],
            "validation_year": saved["validation_year"],
            "test_year": saved["test_year"],
            "train_rows": saved["train_rows"],
            "pipeline_version": saved["pipeline_version"],
            "trained_at": saved["trained_at"],
            "features": saved["features"],
            "target": saved["target"],
        })

    reference = load_model(names[0])
    return jsonify({
        "models": models,
        "persistence": reference["persistence"],
        "train_ranges": reference["train_ranges"],
        "categories": reference["categories"],
        "variables": [
            {"key": key, **config.VARIABLES[key]} for key in config.NUMERIC_FEATURES
        ],
        "target_unit": config.TARGET_UNIT,
    })


@ml_bp.route("/states")
def states():
    rows = (
        db.session.query(Facility.state)
        .filter(Facility.state.isnot(None))
        .distinct()
        .order_by(Facility.state)
        .all()
    )
    return jsonify({"states": [row[0] for row in rows]})


@ml_bp.route("/units")
def units():
    state = request.args.get("state", "").strip()
    if not state:
        return _error("Choose a state first.")
    rows = (
        db.session.query(Unit.id, Facility.facility_name, Unit.epa_unit_id)
        .join(Facility, Unit.facility_id == Facility.id)
        .join(AnnualRecord, AnnualRecord.unit_id == Unit.id)
        .filter(Facility.state == state)
        .distinct()
        .order_by(Facility.facility_name, Unit.epa_unit_id)
        .limit(2000)
        .all()
    )
    return jsonify({
        "units": [
            {"id": r[0], "label": f"{r[1]} — Unit {r[2]}"} for r in rows
        ]
    })


@ml_bp.route("/baseline")
def baseline():
    unit_id = request.args.get("unit_id", type=int)
    if unit_id is None:
        return _error("Choose a unit.")
    result = get_unit_baseline(unit_id)
    if result is None:
        return _error("No annual records were found for that unit.", 404)
    return jsonify(result)


@ml_bp.route("/predict", methods=["POST"])
def predict():
    data = _body()
    return jsonify({"predictions": predict_all(data.get("baseline") or {})})


@ml_bp.route("/sensitivity", methods=["POST"])
def sensitivity_curve():
    data = _body()
    return jsonify(oat_sweep(
        _model_name(data),
        data.get("baseline") or {},
        data.get("variable", ""),
        low=_optional_float(data.get("min")),
        high=_optional_float(data.get("max")),
        steps=int(data.get("steps") or 25),
    ))


@ml_bp.route("/scenarios", methods=["POST"])
def scenarios():
    data = _body()
    return jsonify(run_scenarios(
        _model_name(data),
        data.get("baseline") or {},
        fuel=(data.get("fuel") or "").strip() or None,
    ))
