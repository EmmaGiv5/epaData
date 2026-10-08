# Handles general website pages.

# Such as: project intro, current data coverage, 
# number of facilities, number of units, and navigation

# Creates your first webpage

import os
import uuid
from datetime import datetime
from sqlalchemy import or_
# from sqlalchemy import or_, cast, String

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
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
    dataset,
    User,
)

from app.services.metadata_service import create_dataset_metadata
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


@main_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):

            session["user_id"] = user.id
            session["user_email"] = user.email

            flash("Login successful!", "success")

            return redirect(url_for("main.home"))

        flash(
            "Invalid email or password.",
            "error"
        )

    return render_template("login.html")


@main_bp.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("main.login")
    )


@main_bp.route("/create-user", methods=["GET", "POST"])
def create_user():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        # Check that the passwords match
        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return render_template(
                "create_user.html"
            )

        # Check whether the email already exists
        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            flash(
                "An account with that email already exists.",
                "error"
            )

            return render_template(
                "create_user.html"
            )

        # Create the new user
        user = User(email=email)

        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        flash(
            "Account created successfully! You can now log in.",
            "success"
        )

        return redirect(
            url_for("main.login")
        )

    return render_template("create_user.html")



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

    create_dataset_metadata(
        dataset=dataset,
        title=dataset.dataset_name,
        description="EPA environmental dataset imported through the epaData upload workflow.",
        source=dataset.data_source,
        source_url=None,
        geographic_scope="United States",
        filters_applied=None,
        file_format=get_file_extension(original_filename).replace(".", "").upper(),
        notes="Metadata generated automatically during dataset import.",
    )

    db.session.commit()

    return imported_count

@main_bp.route("/data")
def data_explorer():
    records = (
        db.session.query(
            AnnualRecord,
            Unit,
            Facility
        )
        .join(
            Unit,
            AnnualRecord.unit_id == Unit.id
        )
        .join(
            Facility,
            Unit.facility_id == Facility.id
        )
        .order_by(
            AnnualRecord.reporting_year.desc(),
            Facility.facility_name,
            Unit.epa_unit_id
        )
        .all()
    )

    states = (
        db.session.query(Facility.state)
        .distinct()
        .order_by(Facility.state)
        .all()
    )

    facilities = (
        db.session.query(
            Facility.id,
            Facility.facility_name
        )
        .distinct()
        .order_by(Facility.facility_name)
        .all()
    )

    years = (
        db.session.query(
            AnnualRecord.reporting_year
        )
        .distinct()
        .order_by(
            AnnualRecord.reporting_year.desc()
        )
        .all()
    )

    return render_template(
        "data_explorer.html",
        records=records,
        states=[row[0] for row in states if row[0]],
        facilities=facilities,
        years=[row[0] for row in years if row[0]],
    )
    
    
@main_bp.route("/search", methods=["GET"])
def search():
    # Get the text entered into the search box
    query = request.args.get("query", "").strip()

    # Start with an empty list
    results = []

    # Only search if the user entered something
    if query:
        search_term = f"%{query}%"

        results = (
            AnnualRecord.query
            .join(Unit, AnnualRecord.unit_id == Unit.id)
            .join(Facility, Unit.facility_id == Facility.id)
            .filter(
                or_(
                    # Facility information
                    Facility.facility_name.ilike(search_term),
                    Facility.epa_facility_id.ilike(search_term),
                    Facility.state.ilike(search_term),
                    Facility.source_category.ilike(search_term),

                    # Unit information
                    Unit.epa_unit_id.ilike(search_term),
                    Unit.unit_type.ilike(search_term),
                    Unit.primary_fuel.ilike(search_term),
                    Unit.secondary_fuel.ilike(search_term),

                    # Annual record information
                    cast(
                        AnnualRecord.reporting_year,
                        String
                    ).ilike(search_term),

                    AnnualRecord.so2_control.ilike(search_term),
                    AnnualRecord.nox_control.ilike(search_term),
                    AnnualRecord.pm_control.ilike(search_term),
                    AnnualRecord.program_code.ilike(search_term)
                )
            )
            .all()
        )

    return render_template(
        "search.html",
        results=results,
        query=query
    )