# Handles general website pages.

# Such as: project intro, current data coverage, 
# number of facilities, number of units, and navigation

# Creates your first webpage

import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from app import db
from app.models import (
    Dataset,
    Facility,
    Unit,
    AnnualRecord,
    UploadedFile,
    DataProvenance,
)

from app.services.validator import (
    read_uploaded_file,
    validate_dataframe,
    get_file_extension,
    normalize_columns,
)


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    return render_template("index.html")


@main_bp.route("/upload", methods=["GET", "POST"])
def upload():

    validation_results = None
    preview = None
    filename = None
    saved_filename = None

    if request.method == "POST":

        # Approval request
        if request.form.get("action") == "approve":

            saved_filename = request.form.get("saved_filename")

            if not saved_filename:
                flash("No validated file was found.", "error")
                return redirect(url_for("main.upload"))

            file_path = os.path.join(
                current_app.config["UPLOAD_FOLDER"],
                saved_filename,
            )

            if not os.path.exists(file_path):
                flash("The uploaded file could not be found.", "error")
                return redirect(url_for("main.upload"))

            try:
                dataframe = read_uploaded_file(file_path)
                dataframe = normalize_columns(dataframe)

                validation_results = validate_dataframe(dataframe)

                if not validation_results["valid"]:
                    flash(
                        "The file cannot be imported because it did not pass validation.",
                        "error",
                    )

                    return render_template(
                        "upload.html",
                        validation_results=validation_results,
                        preview=dataframe.head(10).to_html(
                            classes="data-preview",
                            index=False
                        ),
                        filename=request.form.get("original_filename"),
                        saved_filename=saved_filename,
                    )

                imported_count = import_dataframe(
                    dataframe,
                    request.form.get("original_filename")
                    or saved_filename,
                )

                flash(
                    f"Import successful. {imported_count} annual records were imported.",
                    "success",
                )

                return redirect(url_for("main.upload"))

            except Exception as exc:
                db.session.rollback()

                flash(
                    f"Import failed: {exc}",
                    "error",
                )

                return render_template(
                    "upload.html",
                    validation_results=validation_results,
                    preview=preview,
                    filename=filename,
                    saved_filename=saved_filename,
                )

        # Normal upload/validation
        uploaded_file = request.files.get("file")

        if not uploaded_file or not uploaded_file.filename:
            flash("Please select a file.", "error")
            return redirect(url_for("main.upload"))

        filename = secure_filename(uploaded_file.filename)

        extension = get_file_extension(filename)

        if extension not in {".csv", ".xlsx", ".xls"}:
            flash(
                "Unsupported file type. Please upload CSV or Excel.",
                "error",
            )
            return redirect(url_for("main.upload"))

        upload_folder = current_app.config["UPLOAD_FOLDER"]

        os.makedirs(upload_folder, exist_ok=True)

        saved_filename = (
            f"{uuid.uuid4().hex}{extension}"
        )

        file_path = os.path.join(
            upload_folder,
            saved_filename,
        )

        uploaded_file.save(file_path)

        try:
            dataframe = read_uploaded_file(file_path)

            dataframe = normalize_columns(dataframe)

            print("Original Columns")
            print(list(
                read_uploaded_file(file_path).columns
            ))

            print("Normalized Columns")
            print(list(dataframe.columns))

            validation_results = validate_dataframe(
                dataframe
            )

            preview = dataframe.head(10).to_html(
                classes="data-preview",
                index=False,
            )

        except Exception as exc:

            flash(
                f"Validation failed: {exc}",
                "error",
            )

            return render_template(
                "upload.html",
                validation_results=None,
                preview=None,
                filename=filename,
                saved_filename=None,
            )

    return render_template(
        "upload.html",
        validation_results=validation_results,
        preview=preview,
        filename=filename,
        saved_filename=saved_filename,
    )


def import_dataframe(dataframe, original_filename):

    dataset = Dataset(
        dataset_name=os.path.splitext(
            original_filename
        )[0],
        data_source="EPA uploaded file",
        reporting_year=int(
            dataframe["reporting_year"].min()
        ),
        retrieval_upload_date=datetime.utcnow(),
        original_filename=original_filename,
        raw_record_count=len(dataframe),
        accepted_record_count=0,
        notes="Imported through epaData upload workflow.",
    )

    db.session.add(dataset)
    db.session.flush()

    uploaded = UploadedFile(
        dataset_id=dataset.id,
        original_filename=original_filename,
        stored_filename=original_filename,
        file_type=get_file_extension(
            original_filename
        ).replace(".", ""),
        file_size=0,
        upload_date=datetime.utcnow(),
        status="imported",
    )

    db.session.add(uploaded)

    facility_cache = {}
    unit_cache = {}

    imported_count = 0

    for _, row in dataframe.iterrows():

        facility_key = str(
            row["epa_facility_id"]
        )

        if facility_key not in facility_cache:

            facility = Facility(
                dataset_id=dataset.id,
                epa_facility_id=facility_key,
                facility_name=str(
                    row["facility_name"]
                ),
                state=str(row["state"]),
                source_category=None
            )

            db.session.add(facility)
            db.session.flush()

            facility_cache[facility_key] = facility

        facility = facility_cache[facility_key]

        unit_key = (
            facility.id,
            str(row["epa_unit_id"])
        )

        if unit_key not in unit_cache:

            unit = Unit(
                facility_id=facility.id,
                epa_unit_id=str(
                    row["epa_unit_id"]
                ),
                unit_type=str(
                    row["unit_type"]
                ),
                primary_fuel=str(
                    row["primary_fuel"]
                ),
                secondary_fuel=(
                    None
                    if str(row["secondary_fuel"]) == "nan"
                    else str(row["secondary_fuel"])
                ),
            )

            db.session.add(unit)
            db.session.flush()

            unit_cache[unit_key] = unit

        unit = unit_cache[unit_key]

        record = AnnualRecord(
            unit_id=unit.id,
            reporting_year=int(
                row["reporting_year"]
            ),
            operating_time=float(
                row["operating_time"]
            ),
            gross_load=float(
                row["gross_load"]
            ),
            steam_load=(
                None
                if str(row["steam_load"]) == "nan"
                else float(row["steam_load"])
            ),
            heat_input=float(
                row["heat_input"]
            ),
            co2_mass=float(
                row["co2_mass"]
            ),
            so2_mass=float(
                row["so2_mass"]
            ),
            nox_mass=float(
                row["nox_mass"]
            ),
            so2_control=(
                None
                if str(row["so2_control"]) == "nan"
                else str(row["so2_control"])
            ),
            nox_control=(
                None
                if str(row["nox_control"]) == "nan"
                else str(row["nox_control"])
            ),
            pm_control=(
                None
                if str(row["pm_control"]) == "nan"
                else str(row["pm_control"])
            ),
            program_code=(
                None
                if str(row["program_code"]) == "nan"
                else str(row["program_code"])
            ),
        )

        db.session.add(record)

        imported_count += 1

    dataset.accepted_record_count = imported_count

    db.session.commit()

    return imported_count