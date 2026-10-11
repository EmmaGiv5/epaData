import math
import re

from flask import Blueprint, render_template, request

from app.models import (
    AnnualRecord,
    DataProvenance,
    Dataset,
    Facility,
    Unit,
)
from app.services.campd_service import (
    CAMPDServiceError,
    EMISSION_DATASETS,
    STATE_OPTIONS,
    build_dataset_filters,
    fetch_dataset_with_provenance,
)
from app.services.export_service import csv_download

download_bp = Blueprint("download", __name__)

LOCAL_FILTERS = (
    ("operating_time", AnnualRecord.operating_time),
    ("gross_load", AnnualRecord.gross_load),
    ("heat_input", AnnualRecord.heat_input),
    ("co2_mass", AnnualRecord.co2_mass),
    ("so2_mass", AnnualRecord.so2_mass),
    ("nox_mass", AnnualRecord.nox_mass),
)


def _number(form, name, label):
    raw_value = form.get(name, "").strip()
    if not raw_value:
        return None
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number.")
    return value


def _local_annual_rows(form, state_options, dataset_ids):
    state = form.get("state", "").strip().upper()
    if state and state not in state_options:
        raise ValueError("Choose a state from the list.")

    year_text = form.get("year", "").strip()
    if year_text:
        try:
            year = int(year_text)
        except ValueError as exc:
            raise ValueError("Reporting year must be a whole number.") from exc
        if not 1900 <= year <= 2100:
            raise ValueError("Reporting year must be between 1900 and 2100.")
    else:
        year = None

    facility_id = form.get("facility_id", "").strip()
    if facility_id and not re.fullmatch(r"[A-Za-z0-9_-]+", facility_id):
        raise ValueError("Facility ID contains unsupported characters.")

    unit_id = form.get("unit_id", "").strip()
    fuel = form.get("fuel", "").strip()
    unit_type = form.get("unit_type", "").strip()
    control = form.get("control", "").strip()

    selected_dataset = form.get("dataset", "local_all")
    query = (
        AnnualRecord.query
        .join(Unit, AnnualRecord.unit_id == Unit.id)
        .join(Facility, Unit.facility_id == Facility.id)
    )

    if selected_dataset.startswith("local_dataset:"):
        try:
            dataset_id = int(selected_dataset.split(":", 1)[1])
        except ValueError as exc:
            raise ValueError("Choose a valid uploaded dataset.") from exc
        if dataset_id not in dataset_ids:
            raise ValueError("Choose a valid uploaded dataset.")
        query = query.filter(Facility.dataset_id == dataset_id)

    if state:
        query = query.filter(Facility.state == state)
    if year is not None:
        query = query.filter(AnnualRecord.reporting_year == year)
    if facility_id:
        query = query.filter(Facility.epa_facility_id == facility_id)
    if unit_id:
        query = query.filter(Unit.epa_unit_id.ilike(f"%{unit_id}%"))
    if fuel:
        query = query.filter(Unit.primary_fuel.ilike(f"%{fuel}%"))
    if unit_type:
        query = query.filter(Unit.unit_type.ilike(f"%{unit_type}%"))
    if control:
        query = query.filter(
            AnnualRecord.so2_control.ilike(f"%{control}%")
            | AnnualRecord.nox_control.ilike(f"%{control}%")
            | AnnualRecord.pm_control.ilike(f"%{control}%")
        )

    for field_name, column in LOCAL_FILTERS:
        minimum = _number(form, f"min_{field_name}", "Minimum")
        maximum = _number(form, f"max_{field_name}", "Maximum")
        if minimum is not None and maximum is not None and minimum > maximum:
            raise ValueError(
                f"Minimum {field_name.replace('_', ' ')} cannot exceed maximum."
            )
        if minimum is not None:
            query = query.filter(column >= minimum)
        if maximum is not None:
            query = query.filter(column <= maximum)

    query = query.order_by(
        AnnualRecord.reporting_year,
        Facility.facility_name,
        Unit.epa_unit_id,
    )
    records = query.with_entities(AnnualRecord, Unit, Facility).all()

    columns = [
        "reporting_year",
        "state",
        "facility_id",
        "facility_name",
        "unit_id",
        "unit_type",
        "primary_fuel",
        "secondary_fuel",
        "operating_time",
        "gross_load",
        "steam_load",
        "heat_input",
        "co2_mass",
        "so2_mass",
        "nox_mass",
        "so2_control",
        "nox_control",
        "pm_control",
        "program_code",
    ]
    rows = []
    for annual, unit, facility in records:
        rows.append({
            "reporting_year": annual.reporting_year,
            "state": facility.state,
            "facility_id": facility.epa_facility_id,
            "facility_name": facility.facility_name,
            "unit_id": unit.epa_unit_id,
            "unit_type": unit.unit_type,
            "primary_fuel": unit.primary_fuel,
            "secondary_fuel": unit.secondary_fuel,
            "operating_time": annual.operating_time,
            "gross_load": annual.gross_load,
            "steam_load": annual.steam_load,
            "heat_input": annual.heat_input,
            "co2_mass": annual.co2_mass,
            "so2_mass": annual.so2_mass,
            "nox_mass": annual.nox_mass,
            "so2_control": annual.so2_control,
            "nox_control": annual.nox_control,
            "pm_control": annual.pm_control,
            "program_code": annual.program_code,
        })
    return columns, rows


def _provenance_rows():
    records = (
        DataProvenance.query
        .join(Dataset, DataProvenance.dataset_id == Dataset.id)
        .order_by(DataProvenance.retrieval_date, DataProvenance.id)
        .with_entities(DataProvenance, Dataset)
        .all()
    )
    columns = [
        "source",
        "source_url",
        "retrieval_date",
        "dataset_name",
        "data_source",
        "reporting_year",
        "query_parameters",
        "record_count",
        "notes",
    ]
    rows = [
        {
            "source": provenance.source,
            "source_url": provenance.source_url,
            "retrieval_date": provenance.retrieval_date.isoformat(),
            "dataset_name": dataset.dataset_name,
            "data_source": dataset.data_source,
            "reporting_year": provenance.reporting_year,
            "query_parameters": provenance.query_parameters,
            "record_count": provenance.record_count,
            "notes": provenance.notes,
        }
        for provenance, dataset in records
    ]
    return columns, rows


@download_bp.route("/download", methods=["GET"])
def download_page():
    datasets = Dataset.query.order_by(Dataset.dataset_name).all()
    state_options = sorted({
        row[0]
        for row in Facility.query.with_entities(Facility.state)
        .filter(Facility.state.isnot(None))
        .distinct()
        .all()
    })
    return render_template(
        "download.html",
        local_datasets=datasets,
        local_states=state_options,
        campd_states=STATE_OPTIONS,
        campd_datasets=EMISSION_DATASETS,
        error=None,
    )


@download_bp.route("/download/export", methods=["POST"])
def export_download():
    selected_dataset = request.form.get("dataset", "").strip()
    selected_format = request.form.get("format", "").strip().lower()

    if selected_format != "csv":
        return _render_error("CSV is the only currently supported format.")

    try:
        if selected_dataset == "local_all" or selected_dataset.startswith(
            "local_dataset:"
        ):
            local_datasets = {
                dataset_id for dataset_id, in Dataset.query.with_entities(
                    Dataset.id
                ).all()
            }
            local_states = {
                state for state, in Facility.query.with_entities(
                    Facility.state
                ).filter(Facility.state.isnot(None)).distinct().all()
            }
            columns, rows = _local_annual_rows(
                request.form,
                state_options=local_states,
                dataset_ids=local_datasets,
            )
            filename = "epaData_local_annual_records.csv"
        elif selected_dataset == "provenance":
            columns, rows = _provenance_rows()
            filename = "epaData_retrieval_provenance.csv"
        elif selected_dataset in EMISSION_DATASETS:
            state = request.form.get("campd_state", "").strip().upper()
            year = request.form.get("campd_year", "").strip()
            begin_date = request.form.get("begin_date", "").strip()
            end_date = request.form.get("end_date", "").strip()
            facility_id = request.form.get("campd_facility_id", "").strip()
            try:
                campd_page = int(request.form.get("campd_page", "1"))
                campd_per_page = int(request.form.get("campd_per_page", "50"))
            except ValueError as exc:
                raise ValueError(
                    "Choose a valid page and rows-per-page value."
                ) from exc
            if campd_page < 1 or campd_per_page not in (25, 50, 100, 500):
                raise ValueError("Choose a valid page and rows-per-page value.")
            filters = build_dataset_filters(
                dataset=selected_dataset,
                state_code=state,
                year=year,
                begin_date=begin_date,
                end_date=end_date,
                oris_code=facility_id,
            )
            result = fetch_dataset_with_provenance(
                dataset=selected_dataset,
                filters=filters,
                page=campd_page,
                per_page=campd_per_page,
            )
            rows = [
                record for record in result["records"]
                if isinstance(record, dict)
            ]
            columns = list(dict.fromkeys(
                key for row in rows for key in row
            ))
            if not columns:
                columns = ["message"]
                rows = [{"message": "No records returned for these filters."}]
            filename = (
                f"epaData_campd_{selected_dataset}_{state}"
                f"_page_{campd_page}.csv"
            )
        else:
            raise ValueError("Choose a dataset from the list.")
    except (CAMPDServiceError, ValueError) as exc:
        return _render_error(str(exc))

    return csv_download(columns, rows, filename)


def _render_error(message):
    datasets = Dataset.query.order_by(Dataset.dataset_name).all()
    state_options = sorted({
        row[0]
        for row in Facility.query.with_entities(Facility.state)
        .filter(Facility.state.isnot(None))
        .distinct()
        .all()
    })
    return render_template(
        "download.html",
        local_datasets=datasets,
        local_states=state_options,
        campd_states=STATE_OPTIONS,
        campd_datasets=EMISSION_DATASETS,
        error=message,
        form_data=request.form,
    ), 400
