# Handles general website pages.

# Such as: project intro, current data coverage, 
# number of facilities, number of units, and navigation

# Creates your first webpage

#import psycopg2
from dotenv import load_dotenv
import os
import re
# Load environment variables from .env
load_dotenv()

# Fetch variables
#DATABASE_URL = os.getenv("DATABASE_URL")

# Connect to the database
#connection = psycopg2.connect(DATABASE_URL)


import uuid
from datetime import datetime
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

#from app.services.campd_service import (
#    CAMPDServiceError,
#    EMISSION_DATASETS,
#    STATE_OPTIONS,
#    build_dataset_filters,
#    fetch_dataset_with_provenance,
#)

from app.services.campd_service import (
    DATASETS as campd_datasets,
    EMISSION_DATASETS,
    STATE_OPTIONS,
    build_dataset_filters,
    fetch_dataset,
    fetch_dataset_with_provenance,
    CAMPDServiceError,
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


@main_bp.route("/forgot-password")
def forgot_password():
    return render_template("forgot_password.html")


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

            original_filename = secure_filename(
                request.form.get("original_filename")
                or saved_filename
            )

            already_imported = Dataset.query.filter_by(
                original_filename=original_filename,
                data_source="EPA uploaded file",
            ).first()

            if already_imported is not None:
                flash(
                    "This dataset has already been imported.",
                    "error",
                )
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

                imported_count, updated_count = import_dataframe(
                    dataframe,
                    original_filename,
                )

                flash(
                    f"Import successful. {imported_count} annual records were processed; "
                    f"{updated_count} existing records were updated.",
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
    updated_count = 0

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

            facility = Facility.query.filter_by(
                epa_facility_id=facility_key
            ).one_or_none()

            if facility is None:
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

            unit = Unit.query.filter_by(
                facility_id=facility.id,
                epa_unit_id=str(row["epa_unit_id"]),
            ).one_or_none()

            if unit is None:
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

        record_values = {
            "unit_id": unit.id,
            "reporting_year": int(row["reporting_year"]),
            "operating_time": (
                None
                if str(row["operating_time"]) == "nan"
                else float(row["operating_time"])
            ),
            "gross_load": (
                None
                if str(row["gross_load"]) == "nan"
                else float(row["gross_load"])
            ),
            "steam_load": (
                None
                if str(row["steam_load"]) == "nan"
                else float(row["steam_load"])
            ),
            "heat_input": (
                None
                if str(row["heat_input"]) == "nan"
                else float(row["heat_input"])
            ),
            "co2_mass": (
                None
                if str(row["co2_mass"]) == "nan"
                else float(row["co2_mass"])
            ),
            "so2_mass": (
                None
                if str(row["so2_mass"]) == "nan"
                else float(row["so2_mass"])
            ),
            "nox_mass": (
                None
                if str(row["nox_mass"]) == "nan"
                else float(row["nox_mass"])
            ),
            "so2_control": (
                None
                if str(row["so2_control"]) == "nan"
                else str(row["so2_control"])
            ),
            "nox_control": (
                None
                if str(row["nox_control"]) == "nan"
                else str(row["nox_control"])
            ),
            "pm_control": (
                None
                if str(row["pm_control"]) == "nan"
                else str(row["pm_control"])
            ),
            "program_code": (
                None
                if str(row["program_code"]) == "nan"
                else str(row["program_code"])
            ),
        }

        record = AnnualRecord.query.filter_by(
            unit_id=unit.id,
            reporting_year=record_values["reporting_year"],
        ).one_or_none()

        if record is None:
            db.session.add(AnnualRecord(**record_values))
        else:
            for field, value in record_values.items():
                setattr(record, field, value)
            updated_count += 1

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

    return imported_count, updated_count

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
    
    

STATE_NAMES = {
    "AL": "Alabama",
    "GA": "Georgia",
    "KY": "Kentucky",
    "MS": "Mississippi",
    "TN": "Tennessee",
}


def interpret_basic_query(query):
    """Turn common descriptive phrases into database filters."""
    remaining = query.lower()
    filters = {}

    # Match full state names first so "in Kentucky" is not
    # mistaken for the state abbreviation IN (Indiana).
    for code, name in STATE_NAMES.items():
        pattern = rf"\b{re.escape(name.lower())}\b"
        if re.search(pattern, remaining):
            filters["state"] = (code, name)
            remaining = re.sub(pattern, " ", remaining)
            break

    # Match state abbreviations when the query makes it clear
    # that the abbreviation is intended as a state.
    if "state" not in filters:
        original = query

        for code, name in STATE_NAMES.items():
            # Accept an uppercase abbreviation such as KY,
            # an abbreviation after "in", or a query that is
            # exactly the abbreviation.
            patterns = [
                rf"\b{re.escape(code)}\b",
                rf"\b(?:in|state)\s+{re.escape(code.lower())}\b",
            ]

            matched_pattern = None

            if original == code:
                matched_pattern = rf"\b{re.escape(code.lower())}\b"
            elif re.search(patterns[1], remaining):
                matched_pattern = patterns[1]
            elif re.search(patterns[0], original):
                matched_pattern = rf"\b{re.escape(code.lower())}\b"

            if matched_pattern:
                filters["state"] = (code, name)
                remaining = re.sub(
                    matched_pattern, " ", remaining, count=1
                )
                break

    # Recognize a reporting year.
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", remaining)
    if year_match:
        year_text = year_match.group(0)
        filters["year"] = int(year_text)
        remaining = re.sub(rf"\b{year_text}\b", " ", remaining, count=1)

    # Recognize common fuel descriptions. Longer phrases come first.
    fuel_terms = (
        "natural gas", "petroleum coke", "biomass",
        "coal", "oil", "gas", "nuclear", "wood",
    )
    for fuel in fuel_terms:
        pattern = rf"\b{re.escape(fuel)}\b"
        if re.search(pattern, remaining):
            filters["fuel"] = fuel
            remaining = re.sub(pattern, " ", remaining, count=1)
            break

    # Initial rule: "high CO2" means CO2 mass greater than 500,000.
    high_co2 = re.search(
        r"\b(?:high|highly elevated|large)\b.{0,20}"
        r"\b(?:co2|carbon dioxide)\b"
        r"|\b(?:co2|carbon dioxide)\b.{0,20}"
        r"\b(?:high|highly elevated|large)\b",
        remaining,
    )

    if high_co2:
        filters["co2_gt"] = 500000
        remaining = re.sub(
            r"\b(?:high|highly elevated|large)\b", " ", remaining
        )
        remaining = re.sub(
            r"\b(?:co2|carbon dioxide|emissions?|tons?)\b",
            " ", remaining,
        )

    # Remove conversational filler and keep useful search terms.
    filler = {
        "find", "show", "me", "all", "the", "with", "in", "for",
        "units", "unit", "facility", "facilities", "records",
        "where", "having", "that", "are", "is", "of", "and",
        "from", "emissions", "emission",
    }

    words = re.findall(r"[a-z0-9_-]+", remaining)
    residual = " ".join(word for word in words if word not in filler)

    return filters, residual

# reusable helpers for EPA records

def _normalized_api_key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _api_value(record, *names):
    """Find an API field even if its casing or underscores differ."""
    wanted = {_normalized_api_key(name) for name in names}

    for key, value in record.items():
        if _normalized_api_key(key) in wanted:
            return value

    return None


def _api_number(value):
    """Convert a numeric API value to float, if possible."""
    if value is None or value == "":
        return None

    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _fetch_annual_facility_records(state_code, year, oris_code=""):
    """Fetch up to 500 annual facility records for a state/year."""
    filters = build_dataset_filters(
        dataset="annual_facility",
        state_code=state_code,
        year=str(year),
        oris_code=oris_code,
    )

    first_page = fetch_dataset(
        "annual_facility",
        filters=filters,
        page=1,
        per_page=100,
    )

    records = list(first_page["records"])
    total = int(first_page.get("total", len(records)) or 0)

    # Limit each state/year request to five pages to avoid excessive
    # API requests. The returned total still reports EPA's total count.
    page_count = min((total + 99) // 100, 5)

    for page in range(2, page_count + 1):
        response = fetch_dataset(
            "annual_facility",
            filters=filters,
            page=page,
            per_page=100,
        )
        records.extend(response["records"])

    return records, total


@main_bp.route("/search", methods=["GET"])
def search():
    """Search landing page."""
    return render_template("search.html")


@main_bp.route("/basic-search", methods=["GET"])
def basic_search():
    """Basic and description-based EPA search."""
    query_text = request.args.get("query", "").strip()
    interpreted, residual = interpret_basic_query(query_text)

    results = []
    basic_error = None
    basic_notice = None

    if query_text:
        try:
            state_codes = [code for code, _ in STATE_OPTIONS]

            if "state" in interpreted:
                selected_state = interpreted["state"][0]

                if selected_state not in state_codes:
                    raise CAMPDServiceError(
                        "That state is not currently supported."
                    )

                state_codes = [selected_state]

            if "year" in interpreted:
                years = [int(interpreted["year"])]

                if not 2015 <= years[0] <= 2025:
                    raise CAMPDServiceError(
                        "Choose a reporting year from 2015 through 2025."
                    )
            else:
                years = list(range(2025, 2014, -1))

            residual_terms = residual.lower().split()
            matches = []

            for state_code in state_codes:
                for year in years:
                    records, _ = _fetch_annual_facility_records(
                        state_code, year
                    )

                    year_matches = []

                    for record in records:
                        if not isinstance(record, dict):
                            continue

                        if "co2_gt" in interpreted:
                            co2_value = _api_number(
                                _api_value(record, "co2Mass", "co2_mass")
                            )

                            if (
                                co2_value is None
                                or co2_value <= interpreted["co2_gt"]
                            ):
                                continue

                        if "fuel" in interpreted:
                            fuel_value = _api_value(
                                record,
                                "primaryFuel",
                                "secondaryFuel",
                                "fuelType",
                                "fuel",
                            )

                            if fuel_value is None:
                                raise CAMPDServiceError(
                                    "The annual facility endpoint does not "
                                    "provide fuel details for these records. "
                                    "Try searching by facility, state, or year."
                                )

                            if interpreted["fuel"].lower() not in str(
                                fuel_value
                            ).lower():
                                continue

                        searchable_text = " ".join(
                            str(value)
                            for value in record.values()
                            if value is not None
                        ).lower()

                        if not all(
                            term in searchable_text
                            for term in residual_terms
                        ):
                            continue

                        record.setdefault("stateCode", state_code)
                        record.setdefault("year", year)
                        year_matches.append(record)

                    if year_matches:
                        matches.extend(year_matches)

                        if "year" not in interpreted:
                            break

            results = matches

            if not results:
                basic_notice = (
                    "No matching records were found in the annual facility "
                    "data returned by EPA. Try another query or reporting year."
                )

        except (CAMPDServiceError, ValueError, TypeError) as exc:
            basic_error = str(exc)
            results = []

    return render_template(
        "basic_search.html",
        query=query_text,
        results=results,
        search_performed=bool(query_text),
        basic_error=basic_error,
        basic_notice=basic_notice,
    )


@main_bp.route("/campd-search", methods=["GET"])
def campd_search():
    """Live EPA CAMPD search with independent pagination."""
    campd_records = []
    campd_columns = []
    campd_total = None
    campd_error = None

    campd_searched = request.args.get("campd_search") == "1"
    campd_state = request.args.get("campd_state", "").strip().upper()
    campd_dataset = request.args.get(
        "campd_dataset", "annual_facility"
    ).strip()
    campd_year = request.args.get("campd_year", "").strip()
    campd_oris_code = request.args.get("campd_oris_code", "").strip()
    campd_begin_date = request.args.get("campd_begin_date", "").strip()
    campd_end_date = request.args.get("campd_end_date", "").strip()
    campd_page = max(request.args.get("campd_page", 1, type=int), 1)
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
                page=campd_page,
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

    return render_template(
        "campd_search.html",
        campd_datasets=campd_datasets,
        campd_states=STATE_OPTIONS,
        campd_emission_datasets=EMISSION_DATASETS,
        campd_state=campd_state,
        campd_dataset=campd_dataset,
        campd_year=campd_year,
        campd_oris_code=campd_oris_code,
        campd_begin_date=campd_begin_date,
        campd_end_date=campd_end_date,
        campd_page=campd_page,
        campd_per_page=campd_per_page,
        campd_records=campd_records,
        campd_columns=campd_columns,
        campd_total=campd_total,
        campd_error=campd_error,
        campd_searched=campd_searched,
    )
    
    
@main_bp.route("/advanced-search", methods=["GET"])
def advanced_search():
    values = {
        "state": request.args.get("state", "").strip().upper(),
        "year_from": request.args.get("year_from", "").strip(),
        "year_to": request.args.get("year_to", "").strip(),
        "fuel": request.args.get("fuel", "").strip(),
        "facility_id": request.args.get("facility_id", "").strip(),
        "unit_id": request.args.get("unit_id", "").strip(),
        "metric": request.args.get("metric", "co2_mass").strip(),
        "operator": request.args.get("operator", ">").strip(),
        "value": request.args.get("value", "").strip(),
        "value_to": request.args.get("value_to", "").strip(),
    }

    performed = any(values[key] for key in (
        "state", "year_from", "year_to", "fuel",
        "facility_id", "unit_id", "value",
    ))

    results = []
    error = None
    notice = None

    metric_fields = {
        "co2_mass": ("co2Mass", "co2_mass"),
        "so2_mass": ("so2Mass", "so2_mass"),
        "nox_mass": ("noxMass", "nox_mass"),
        "heat_input": ("heatInput", "heat_input"),
        "gross_load": ("grossLoad", "gross_load"),
        "steam_load": ("steamLoad", "steam_load"),
        "operating_time": ("operatingTime", "operating_time"),
    }

    operators = {"=", ">", ">=", "<", "<=", "between"}

    if performed:
        try:
            # This endpoint aggregates emissions by facility. It cannot
            # reliably perform unit-level or fuel-level filtering.
            if values["fuel"]:
                raise ValueError(
                    "Fuel filtering is not supported by the annual "
                    "facility endpoint. Clear the Fuel field to continue."
                )

            if values["unit_id"]:
                raise ValueError(
                    "Unit ID filtering is not supported by the annual "
                    "facility endpoint. Clear the Unit ID field to continue."
                )

            state_codes = [code for code, _ in STATE_OPTIONS]

            if values["state"]:
                if values["state"] not in state_codes:
                    raise ValueError("Choose a supported state.")
                state_codes = [values["state"]]

            year_from = (
                int(values["year_from"]) if values["year_from"] else None
            )
            year_to = (
                int(values["year_to"]) if values["year_to"] else None
            )

            if year_from is not None and not 2015 <= year_from <= 2025:
                raise ValueError("The starting year must be from 2015 to 2025.")

            if year_to is not None and not 2015 <= year_to <= 2025:
                raise ValueError("The ending year must be from 2015 to 2025.")

            if year_from and year_to and year_from > year_to:
                raise ValueError(
                    "The starting year must not exceed the ending year."
                )

            if values["facility_id"] and not values["facility_id"].isdigit():
                raise ValueError("Facility ID must contain digits only.")

            metric_names = metric_fields.get(values["metric"])
            operator = values["operator"]

            if values["value"]:
                if metric_names is None or operator not in operators:
                    raise ValueError(
                        "Choose a valid measurement and operator."
                    )

                first = float(values["value"].replace(",", ""))
                second = None

                if operator == "between":
                    if not values["value_to"]:
                        raise ValueError(
                            "Enter an upper value for the range search."
                        )

                    second = float(values["value_to"].replace(",", ""))

                    if second < first:
                        raise ValueError(
                            "The upper value must not be below the lower value."
                        )

            # If no year is supplied, find the latest matching year for
            # each state. If a range is supplied, query every year in it.
            explicit_year_range = year_from is not None or year_to is not None

            if explicit_year_range:
                first_year = year_from if year_from is not None else 2015
                last_year = year_to if year_to is not None else 2025
                years = list(range(first_year, last_year + 1))
            else:
                years = list(range(2025, 2014, -1))

            for state_code in state_codes:
                for year in years:
                    records, _ = _fetch_annual_facility_records(
                        state_code,
                        year,
                        oris_code=values["facility_id"],
                    )

                    year_matches = []

                    for record in records:
                        if not isinstance(record, dict):
                            continue

                        record.setdefault("stateCode", state_code)
                        record.setdefault("year", year)

                        if values["value"]:
                            raw_metric = _api_value(record, *metric_names)
                            metric_value = _api_number(raw_metric)

                            # Do not claim a metric filter worked if the
                            # API record does not include that measurement.
                            if metric_value is None:
                                continue

                            if operator == "=" and metric_value != first:
                                continue
                            if operator == ">" and metric_value <= first:
                                continue
                            if operator == ">=" and metric_value < first:
                                continue
                            if operator == "<" and metric_value >= first:
                                continue
                            if operator == "<=" and metric_value > first:
                                continue
                            if (
                                operator == "between"
                                and not first <= metric_value <= second
                            ):
                                continue

                        year_matches.append(record)

                    results.extend(year_matches)

                    # Without a year range, keep only the latest year
                    # that has matching results for each state.
                    if year_matches and not explicit_year_range:
                        break

            if not results:
                notice = (
                    "No EPA records matched these filters. The annual "
                    "facility endpoint may not expose every requested field."
                )

        except CAMPDServiceError as exc:
            error = str(exc)
        except (ValueError, TypeError) as exc:
            error = str(exc) or (
                "Please check the year and measurement values."
            )

    return render_template(
        "advanced_search.html",
        query="",
        results=[],
        search_performed=False,
        search_mode="advanced",
        advanced_results=results,
        advanced_performed=performed,
        advanced_error=error,
        advanced_notice=notice,
        advanced_states=sorted(STATE_NAMES.items()),
        advanced_values=values,

        campd_datasets=campd_datasets,
        campd_states=STATE_OPTIONS,
        campd_emission_datasets=EMISSION_DATASETS,
        campd_state="",
        campd_dataset="annual_facility",
        campd_year="",
        campd_oris_code="",
        campd_begin_date="",
        campd_end_date="",
        campd_page=1,
        campd_per_page=50,
        campd_records=[],
        campd_columns=[],
        campd_total=None,
        campd_error=None,
        campd_searched=False,
    )