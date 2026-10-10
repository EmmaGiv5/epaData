# Handles general website pages.

# Such as: project intro, current data coverage, 
# number of facilities, number of units, and navigation

# Creates your first webpage

import os
import uuid
from datetime import datetime
#from sqlalchemy import or_
from sqlalchemy import or_, cast, String

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

from app.services.metadata_service import create_dataset_metadata

from app import db
from app.models import (
    Dataset,
    Facility,
    Unit,
    AnnualRecord,
    UploadedFile,
    DataProvenance,
    #dataset,
    User,
)

from app.services.metadata_service import create_dataset_metadata
from app.services.validator import (
    read_uploaded_file,
    validate_dataframe,
    get_file_extension,
    normalize_columns,
)

from app.search_utils import (
    normalize_query,
    find_search_fields,
)
from app.services.campd_service import (
    CAMPDServiceError,
    EMISSION_DATASETS,
    STATE_OPTIONS,
    build_dataset_filters,
    fetch_dataset_with_provenance,
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

    # ---------------------------------------------------------
    # Determine the reporting years in the uploaded dataset
    # ---------------------------------------------------------

    years = sorted(
        dataframe["reporting_year"]
        .dropna()
        .astype(int)
        .unique()
        .tolist()
    )

    if len(years) == 1:
        dataset_reporting_year = years[0]
        year_description = str(years[0])
    else:
        dataset_reporting_year = None
        year_description = (
            f"{years[0]}-{years[-1]}"
            if years
            else "Unknown"
        )

    # ---------------------------------------------------------
    # Create the Dataset
    # ---------------------------------------------------------

    dataset = Dataset(
        dataset_name=os.path.splitext(
            original_filename
        )[0],
        data_source="EPA uploaded file",
        reporting_year=dataset_reporting_year,
        retrieval_upload_date=datetime.utcnow(),
        original_filename=original_filename,
        raw_record_count=len(dataframe),
        accepted_record_count=0,
        notes=(
            "Imported through epaData upload workflow. "
            f"Reporting years: {year_description}."
        ),
    )

    db.session.add(dataset)
    db.session.flush()

    # ---------------------------------------------------------
    # Create UploadedFile record
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # Caches prevent duplicate facilities and units
    # ---------------------------------------------------------

    facility_cache = {}
    unit_cache = {}

    imported_count = 0

    # ---------------------------------------------------------
    # Import each row
    # ---------------------------------------------------------

    for _, row in dataframe.iterrows():

        # -----------------------------------------------------
        # Facility
        # -----------------------------------------------------

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
                state=str(
                    row["state"]
                ),
                source_category=None
            )

            db.session.add(facility)
            db.session.flush()

            facility_cache[facility_key] = facility

        facility = facility_cache[facility_key]

        # -----------------------------------------------------
        # Unit
        # -----------------------------------------------------

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
                unit_type=(
                    None
                    if str(row["unit_type"]) == "nan"
                    else str(row["unit_type"])
                ),
                primary_fuel=(
                    None
                    if str(row["primary_fuel"]) == "nan"
                    else str(row["primary_fuel"])
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

        # -----------------------------------------------------
        # Annual Record
        # -----------------------------------------------------

        record = AnnualRecord(
            unit_id=unit.id,

            reporting_year=int(
                row["reporting_year"]
            ),

            operating_time=(
                None
                if str(row["operating_time"]) == "nan"
                else float(row["operating_time"])
            ),

            gross_load=(
                None
                if str(row["gross_load"]) == "nan"
                else float(row["gross_load"])
            ),

            steam_load=(
                None
                if str(row["steam_load"]) == "nan"
                else float(row["steam_load"])
            ),

            heat_input=(
                None
                if str(row["heat_input"]) == "nan"
                else float(row["heat_input"])
            ),

            co2_mass=(
                None
                if str(row["co2_mass"]) == "nan"
                else float(row["co2_mass"])
            ),

            so2_mass=(
                None
                if str(row["so2_mass"]) == "nan"
                else float(row["so2_mass"])
            ),

            nox_mass=(
                None
                if str(row["nox_mass"]) == "nan"
                else float(row["nox_mass"])
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

    # ---------------------------------------------------------
    # Create Dataset Metadata
    # ---------------------------------------------------------

    create_dataset_metadata(
        dataset=dataset,
        title=(
            f"EPA Electric Generating Unit Annual Data "
            f"({year_description})"
        ),
        description=(
            "Annual EPA electric generating unit data "
            "imported through the epaData upload workflow."
        ),
        source="U.S. Environmental Protection Agency",
        source_url=None,
        geographic_scope=", ".join(
            sorted(
                dataframe["state"]
                .dropna()
                .astype(str)
                .unique()
            )
        ),
        filters_applied=None,
        file_format=get_file_extension(
            original_filename
        ).replace(".", "").upper(),
        notes=(
            "Metadata generated automatically during "
            "dataset import. "
            f"Reporting years: {year_description}."
        ),
        record_count=len(dataframe),
    )

    # ---------------------------------------------------------
    # Save everything to the database
    # ---------------------------------------------------------

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

    # --------------------------------------------------
    # 1. Get and normalize the user's search query
    # --------------------------------------------------

    query = request.args.get("query", "").strip()
    normalized_query = normalize_query(query)

    # Start with an empty list of results
    results = []
    campd_records = []
    campd_columns = []
    campd_total = None
    campd_error = None
    campd_searched = request.args.get("campd_search") == "1"
    campd_state = request.args.get("campd_state", "").strip().upper()
    campd_dataset = request.args.get(
        "campd_dataset",
        "annual_facility",
    ).strip()
    campd_year = request.args.get("campd_year", "").strip()
    campd_oris_code = request.args.get("campd_oris_code", "").strip()
    campd_begin_date = request.args.get("campd_begin_date", "").strip()
    campd_end_date = request.args.get("campd_end_date", "").strip()
    campd_page = request.args.get("campd_page", 1, type=int)
    campd_per_page = request.args.get("campd_per_page", 50, type=int)
    if campd_per_page not in (25, 50, 100, 500):
        campd_per_page = 50

    if campd_searched:
        try:
            filters = build_dataset_filters(
                dataset=campd_dataset,
                state_code=campd_state,
                year=campd_year,
                begin_date=campd_begin_date,
                end_date=campd_end_date,
                oris_code=campd_oris_code,
            )
            api_result = fetch_dataset_with_provenance(
                dataset=campd_dataset,
                filters=filters,
                page=max(campd_page, 1),
                per_page=campd_per_page,
            )
            campd_records = [
                record
                for record in api_result["records"]
                if isinstance(record, dict)
            ]
            campd_total = api_result["total"]
            for record in campd_records:
                for key in record:
                    if key not in campd_columns and len(campd_columns) < 12:
                        campd_columns.append(key)
        except CAMPDServiceError as exc:
            campd_error = str(exc)

    # --------------------------------------------------
    # 2. Search only if the user entered something
    # --------------------------------------------------

    if normalized_query:

        search_term = f"%{normalized_query}%"

        # Identify EPA measurements mentioned in the query.
        # Example: "Compare CO2 and NOx emissions"
        # returns ["nox_mass", "co2_mass"].
        detected_fields = find_search_fields(
            normalized_query
        )

        # --------------------------------------------------
        # 3. Build the existing text search conditions
        # --------------------------------------------------

        text_conditions = [
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
            AnnualRecord.program_code.ilike(search_term),
        ]

        # --------------------------------------------------
        # 4. Add semantic measurement matching
        # --------------------------------------------------

        # If the user searches for "carbon emissions",
        # include records that contain CO2 measurements.
        #
        # If the user searches for "CO2 and NOx",
        # include records containing either measurement.

        for field in detected_fields:

            measurement_column = getattr(
                AnnualRecord,
                field
            )

            text_conditions.append(
                measurement_column.isnot(None)
            )

        # --------------------------------------------------
        # 5. Query the database
        # --------------------------------------------------

        results = (
            AnnualRecord.query

            # AnnualRecord -> Unit
            .join(
                Unit,
                AnnualRecord.unit_id == Unit.id
            )

            # Unit -> Facility
            .join(
                Facility,
                Unit.facility_id == Facility.id
            )

            # Match existing text searches OR recognized
            # EPA measurement terminology.
            .filter(
                or_(*text_conditions)
            )

            # Newest reporting years first
            .order_by(
                AnnualRecord.reporting_year.desc(),
                Facility.facility_name,
                Unit.epa_unit_id
            )

            .all()
        )

    # --------------------------------------------------
    # 6. Display results in the existing template
    # --------------------------------------------------

    return render_template(
        "search.html",
        results=results,
        query=query,
        campd_records=campd_records,
        campd_columns=campd_columns,
        campd_total=campd_total,
        campd_error=campd_error,
        campd_searched=campd_searched,
        campd_state=campd_state,
        campd_dataset=campd_dataset,
        campd_datasets=EMISSION_DATASETS,
        campd_states=STATE_OPTIONS,
        campd_year=campd_year,
        campd_oris_code=campd_oris_code,
        campd_begin_date=campd_begin_date,
        campd_end_date=campd_end_date,
        campd_page=max(campd_page, 1),
        campd_per_page=campd_per_page,
    )