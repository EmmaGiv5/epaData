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


import csv
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    MetaData,
    Table,
    cast,
    func,
    or_,
    select,
    String,
)
from sqlalchemy.exc import SQLAlchemyError

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

TRACI_EMISSIONS_COLUMNS = {
    "CARBON DIOXIDE": "CO2 Mass (short tons)",
    "SULFUR DIOXIDE": "SO2 Mass (short tons)",
    "NITROGEN OXIDES": "NOx Mass (short tons)",
}
SHORT_TON_TO_KILOGRAMS = 907.18474


def _read_traci_factors():
    factor_path = (
        Path(__file__).resolve().parents[2]
        / "CAMPD_Data_NEW"
        / "traci_2_2.csv"
    )
    factors_by_category = {}

    with factor_path.open(encoding="utf-8-sig", newline="") as factor_file:
        reader = csv.DictReader(factor_file)
        if not reader.fieldnames or "Substance Name" not in reader.fieldnames:
            raise ValueError("The TRACI factor file has an invalid format.")

        for row in reader:
            substance = (row.get("Substance Name") or "").strip().upper()
            if substance not in TRACI_EMISSIONS_COLUMNS:
                continue

            for category, raw_factor in row.items():
                if category in (
                    "CAS #",
                    "Formatted CAS #",
                    "Substance Name",
                ):
                    continue
                if not raw_factor or raw_factor.strip().lower() in ("n/a", "x"):
                    continue

                try:
                    factor_value = float(raw_factor.strip().replace(",", ""))
                except ValueError:
                    continue

                factors_by_category.setdefault(category, {})[
                    substance
                ] = factor_value

    if not factors_by_category:
        raise ValueError("No matching TRACI factors were found.")

    return factors_by_category


@main_bp.route("/")
def home():
    return render_template("index.html")


@main_bp.route("/visualize")
def visualize():

    # Get available states
    states = [
        row[0]
        for row in db.session.query(Facility.state)
        .filter(Facility.state.isnot(None))
        .distinct()
        .order_by(Facility.state)
        .all()
    ]

    # Get available facilities
    facilities = (
        db.session.query(
            Facility.id,
            Facility.facility_name
        )
        .order_by(Facility.facility_name)
        .all()
    )

    # Get available reporting years
    years = [
        row[0]
        for row in db.session.query(
            AnnualRecord.reporting_year
        )
        .filter(AnnualRecord.reporting_year.isnot(None))
        .distinct()
        .order_by(AnnualRecord.reporting_year)
        .all()
    ]

    # Get available fuel types
    fuels = [
        row[0]
        for row in db.session.query(Unit.primary_fuel)
        .filter(Unit.primary_fuel.isnot(None))
        .distinct()
        .order_by(Unit.primary_fuel)
        .all()
    ]

    return render_template(
        "visualize.html",
        states=states,
        facilities=facilities,
        years=years,
        fuels=fuels
    )

@main_bp.route("/api/visualization-data")
def visualization_data():

    try:

        query = (
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
        )

        # Get filter selections
        start_year = request.args.get(
            "start_year", type=int
        )

        end_year = request.args.get(
            "end_year", type=int
        )

        state = request.args.get("state", "").strip()

        facility_id = request.args.get(
            "facility_id", type=int
        )

        fuel = request.args.get("fuel", "").strip()

        # Apply filters
        if start_year:
            query = query.filter(
                AnnualRecord.reporting_year >= start_year
            )

        if end_year:
            query = query.filter(
                AnnualRecord.reporting_year <= end_year
            )

        if start_year and end_year and start_year > end_year:
            return {
                "error": "Start year cannot exceed end year."
            }, 400

        if state:
            query = query.filter(
                Facility.state == state
            )

        if facility_id:
            query = query.filter(
                Facility.id == facility_id
            )

        if fuel:
            query = query.filter(
                Unit.primary_fuel == fuel
            )

        records = query.all()

        data = []

        for annual, unit, facility in records:

            data.append({

                "year": annual.reporting_year,

                "state": facility.state,

                "facility": facility.facility_name,

                "facility_id": facility.id,

                "unit": unit.epa_unit_id,

                "fuel": unit.primary_fuel,

                "gross_load": annual.gross_load,

                "heat_input": annual.heat_input,

                "operating_time": annual.operating_time,

                "co2_mass": annual.co2_mass,

                "so2_mass": annual.so2_mass,

                "nox_mass": annual.nox_mass

            })

        return {
            "total_records": len(data),
            "records": data
        }

    except SQLAlchemyError:

        current_app.logger.exception(
            "Visualization data retrieval failed"
        )

        return {
            "error": "Unable to retrieve visualization data."
        }, 500
    
@main_bp.route("/calculate", methods=["GET", "POST"])
def calculate():
    states = []
    years = []
    calc_state = ""
    calc_year = ""
    calc_results = []
    calc_error = None
    calc_submitted = request.method == "POST"

    try:
        annual_data = Table(
            "calc_data_annual",
            MetaData(),
            autoload_with=db.engine,
        )
        required_columns = (
            "State",
            "Year",
            *TRACI_EMISSIONS_COLUMNS.values(),
        )
        missing_columns = [
            column for column in required_columns if column not in annual_data.c
        ]
        if missing_columns:
            raise ValueError(
                "The calc_data_annual table is missing required columns: "
                + ", ".join(missing_columns)
            )

        states = [
            row[0]
            for row in db.session.execute(
                select(annual_data.c["State"])
                .where(annual_data.c["State"].is_not(None))
                .distinct()
                .order_by(annual_data.c["State"])
            ).all()
        ]
        years = [
            int(row[0])
            for row in db.session.execute(
                select(annual_data.c["Year"])
                .where(annual_data.c["Year"].is_not(None))
                .distinct()
                .order_by(annual_data.c["Year"].desc())
            ).all()
        ]

        if request.method == "POST":
            calc_state = request.form.get("state", "").strip()
            calc_year = request.form.get("year", "").strip()

            if calc_state and calc_state not in states:
                raise ValueError("Choose a state available in the annual data.")
            if calc_year and (
                not calc_year.isdigit() or int(calc_year) not in years
            ):
                raise ValueError("Choose a year available in the annual data.")

            factors_by_category = _read_traci_factors()
            query = select(
                annual_data.c["State"].label("state"),
                annual_data.c["Year"].label("year"),
                *[
                    func.sum(annual_data.c[column]).label(substance)
                    for substance, column in TRACI_EMISSIONS_COLUMNS.items()
                ],
            ).group_by(annual_data.c["State"], annual_data.c["Year"])

            if calc_state:
                query = query.where(annual_data.c["State"] == calc_state)
            if calc_year:
                query = query.where(annual_data.c["Year"] == int(calc_year))

            emissions_groups = db.session.execute(query).mappings().all()
            for group in emissions_groups:
                for category, category_factors in factors_by_category.items():
                    impact_value = 0.0
                    contributing_substances = []

                    for substance, factor in category_factors.items():
                        mass_short_tons = group[substance]
                        if mass_short_tons is None:
                            continue

                        mass_kg = float(mass_short_tons) * SHORT_TON_TO_KILOGRAMS
                        impact_value += mass_kg * factor
                        contributing_substances.append(substance)

                    if not contributing_substances:
                        continue

                    unit_start = category.find("(")
                    unit_end = category.rfind(")")
                    impact_unit = (
                        category[unit_start + 1:unit_end]
                        if unit_start >= 0 and unit_end > unit_start
                        else ""
                    )
                    calc_results.append({
                        "state": group["state"],
                        "year": group["year"],
                        "category": category.split(" (", 1)[0],
                        "value": impact_value,
                        "unit": impact_unit,
                        "substances": ", ".join(contributing_substances),
                    })

    except SQLAlchemyError:
        current_app.logger.exception("Unable to connect to calculation data")
        calc_error = (
            "Could not load calculation data. Verify the database connection "
            "and that calc_data_annual is available."
        )
    except (OSError, ValueError) as exc:
        current_app.logger.exception("Unable to calculate TRACI impacts")
        calc_error = str(exc)

    return render_template(
        "calc.html",
        states=states,
        years=years,
        calc_state=calc_state,
        calc_year=calc_year,
        calc_results=calc_results,
        calc_error=calc_error,
        calc_submitted=calc_submitted,
    )


@main_bp.route("/factored-calculations")
def factored_calculations():
    return render_template("factored_calculations.html")


@main_bp.route("/descriptive-stats")
def descriptive_stats():
    return render_template("descriptive_stats.html")

@main_bp.route("/comparisons")
def comparisons():

    states = [
        "Kentucky",
        "Tennessee",
        "Georgia",
        "Mississippi",
        "Alabama",
    ]

    facilities = (
        db.session.query(
            Facility.id,
            Facility.facility_name
        )
        .filter(Facility.state.in_([
            "KY", "TN", "GA", "MS", "AL"
        ]))
        .order_by(Facility.facility_name)
        .all()
    )

    years = list(range(2015, 2026))

    return render_template(
        "comparisons.html",
        states=states,
        facilities=facilities,
        years=years
    )

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


def _normalized_facility_id(value):
    if value is None:
        return None

    text = str(value).strip()
    if text.endswith(".0") and text[:-2].isdigit():
        text = text[:-2]
    if text.isdigit():
        return str(int(text))
    return text.upper()


def _facilities_data_table():
    try:
        table = Table(
            "facilities_data",
            MetaData(),
            autoload_with=db.engine,
        )
    except NoSuchTableError as exc:
        raise CAMPDServiceError(
            "Fuel and unit filters require the facilities_data table."
        ) from exc

    required_columns = (
        "State",
        "Year",
        "Facility ID",
        "Unit ID",
        "Primary Fuel Type",
        "Secondary Fuel Type",
    )
    missing_columns = [
        name for name in required_columns if name not in table.c
    ]
    if missing_columns:
        raise CAMPDServiceError(
            "The facilities_data table is missing required columns: "
            + ", ".join(missing_columns)
        )

    return table


def _facility_ids_for_search(table, state_code, year, fuel="", unit_id=""):
    """Find facility IDs with matching fuel or unit metadata for a year."""
    conditions = [
        table.c["State"] == state_code,
        table.c["Year"] == year,
    ]

    if fuel:
        fuel_pattern = f"%{fuel}%"
        conditions.append(
            or_(
                table.c["Primary Fuel Type"].ilike(fuel_pattern),
                table.c["Secondary Fuel Type"].ilike(fuel_pattern),
            )
        )

    if unit_id:
        conditions.append(
            cast(table.c["Unit ID"], String).ilike(f"%{unit_id}%")
        )

    facility_ids = db.session.execute(
        select(table.c["Facility ID"]).where(*conditions)
    ).scalars()
    return {
        normalized_id
        for value in facility_ids
        if (normalized_id := _normalized_facility_id(value)) is not None
    }


def _record_facility_id(record):
    return _normalized_facility_id(
        _api_value(
            record,
            "orisCode",
            "facilityId",
            "facility_id",
            "facilityNumber",
        )
    )


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


@main_bp.route("/results", methods=["GET"])
def results():
    """Dispatch a submitted search to its dedicated results view."""
    search_handlers = {
        "basic": basic_search,
        "advanced": advanced_search,
        "campd": campd_search,
    }
    search_type = request.args.get("search_type", "")
    handler = search_handlers.get(search_type)

    if handler is None:
        return redirect(url_for("main.search"))

    return handler()


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
            facility_table = (
                _facilities_data_table()
                if "fuel" in interpreted
                else None
            )

            for state_code in state_codes:
                for year in years:
                    matching_facility_ids = None
                    if "fuel" in interpreted:
                        matching_facility_ids = _facility_ids_for_search(
                            facility_table,
                            state_code,
                            year,
                            fuel=interpreted["fuel"],
                        )
                        if not matching_facility_ids:
                            continue

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
                            facility_id = _record_facility_id(record)
                            if facility_id is None:
                                raise CAMPDServiceError(
                                    "CAMPD did not return a facility ID, so "
                                    "the fuel filter could not be applied."
                                )
                            if facility_id not in matching_facility_ids:
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

    if query_text and basic_error is None:
        return render_template(
            "results.html",
            result_kind="records",
            result_title="Basic Search Results",
            result_source="EPA annual facility data",
            query=query_text,
            results=results,
            notice=basic_notice,
            back_url=url_for("main.basic_search", query=query_text),
        )

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

    if campd_searched:
        return render_template(
            "results.html",
            result_kind="campd",
            result_title="Live CAMPD Results",
            result_source="EPA CAMPD API",
            campd_datasets=campd_datasets,
            campd_states=STATE_OPTIONS,
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
            back_url=url_for(
                "main.campd_search",
                campd_state=campd_state,
                campd_dataset=campd_dataset,
                campd_year=campd_year,
                campd_oris_code=campd_oris_code,
                campd_begin_date=campd_begin_date,
                campd_end_date=campd_end_date,
                campd_per_page=campd_per_page,
            ),
        )

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

            facility_table = (
                _facilities_data_table()
                if values["fuel"] or values["unit_id"]
                else None
            )

            for state_code in state_codes:
                for year in years:
                    matching_facility_ids = None
                    if values["fuel"] or values["unit_id"]:
                        matching_facility_ids = _facility_ids_for_search(
                            facility_table,
                            state_code,
                            year,
                            fuel=values["fuel"],
                            unit_id=values["unit_id"],
                        )
                        if values["facility_id"]:
                            requested_facility_id = _normalized_facility_id(
                                values["facility_id"]
                            )
                            matching_facility_ids.intersection_update(
                                {requested_facility_id}
                            )
                        if not matching_facility_ids:
                            continue

                    records, _ = _fetch_annual_facility_records(
                        state_code,
                        year,
                        oris_code=values["facility_id"],
                    )

                    year_matches = []

                    for record in records:
                        if not isinstance(record, dict):
                            continue

                        if matching_facility_ids is not None:
                            facility_id = _record_facility_id(record)
                            if facility_id is None:
                                raise CAMPDServiceError(
                                    "CAMPD did not return a facility ID, "
                                    "so the fuel or unit filter could not "
                                    "be applied."
                                )
                            if facility_id not in matching_facility_ids:
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

    if performed and error is None:
        return render_template(
            "results.html",
            result_kind="records",
            result_title="Advanced Search Results",
            result_source="EPA annual facility data",
            results=results,
            notice=notice,
            back_url=url_for(
                "main.advanced_search",
                **request.args.to_dict(),
            ),
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