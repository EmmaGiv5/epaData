
# Handles the Data Explorer using the existing Supabase emissions tables.

from datetime import date

from flask import Blueprint, render_template, request
from sqlalchemy import MetaData, Table, select, func, extract

from app import db

from app.services.campd_service import (
    CAMPDServiceError,
    EMISSION_DATASETS,
    STATE_OPTIONS,
    build_dataset_filters,
    fetch_dataset_with_provenance,
)

explorer_bp = Blueprint("explorer", __name__, url_prefix="/explorer")


# The four populated tables already in Supabase.
LOCAL_DATASETS = {
    "annual_facility": {
        "table": "annual_emissions_facility",
        "label": "Annual — Facility",
        "year_column": "Year",
    },
    "annual_state": {
        "table": "annual_emissions_state",
        "label": "Annual — State",
        "year_column": "Year",
    },
    "hourly_facility": {
        "table": "hourly_emissions_facility",
        "label": "Hourly — Facility",
        "year_column": "Date",
    },
    "hourly_state": {
        "table": "hourly_emissions_state",
        "label": "Hourly — State",
        "year_column": "Date",
    },
}

# Standard names used by the template, mapped to actual database columns.
COLUMN_CANDIDATES = {
    "state": ["State"],
    "facility_name": ["Facility Name"],
    "facility_id": ["Facility ID"],
    "year": ["Year"],
    "date": ["Date"],
    "hour": ["Hour"],
    "gross_load": ["Gross Load (MWh)", "Gross Load (MW)"],
    "co2_mass": ["CO2 Mass (short tons)"],
    "so2_mass": ["SO2 Mass (short tons)", "SO2 Mass (lbs)"],
    "nox_mass": ["NOx Mass (short tons)", "NOx Mass (lbs)"],
    "heat_input": ["Heat Input (mmBtu)"],
    "steam_load": ["Steam Load (1000 lb)", "Steam Load (1000 lb/hr)"],
}


def get_column(table, candidates):
    """Return the first matching reflected database column, if available."""
    for name in candidates:
        if name in table.c:
            return table.c[name]
    return None


def parse_number(value):
    """Convert a non-empty filter value to a number, or ignore invalid input."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@explorer_bp.route("/", methods=["GET"])
def explorer():
    args = request.args

    # Local, imported-data filters.
    dataset_key = args.get("dataset", "annual_facility").strip()
    if dataset_key not in LOCAL_DATASETS:
        dataset_key = "annual_facility"

    facility_name = args.get("facility", "").strip()
    state = args.get("state", "").strip()
    year = args.get("year", "").strip()
    min_year = args.get("min_year", "").strip()
    max_year = args.get("max_year", "").strip()

    min_gross_load = args.get("min_gross_load", "").strip()
    max_gross_load = args.get("max_gross_load", "").strip()
    min_co2 = args.get("min_co2", "").strip()
    max_co2 = args.get("max_co2", "").strip()
    min_so2 = args.get("min_so2", "").strip()
    max_so2 = args.get("max_so2", "").strip()
    min_nox = args.get("min_nox", "").strip()
    max_nox = args.get("max_nox", "").strip()
    min_heat_input = args.get("min_heat_input", "").strip()
    max_heat_input = args.get("max_heat_input", "").strip()

    # These fields are retained for the existing UI. The imported tables
    # do not currently contain unit, fuel, or control-technology columns.
    unit_id = args.get("unit", "").strip()
    fuel = args.get("fuel", "").strip()
    control = args.get("control", "").strip()

    sort_by = args.get("sort_by", "").strip()
    sort_order = args.get("sort_order", "desc").strip().lower()
    if sort_order not in ("asc", "desc"):
        sort_order = "desc"

    rank_mode = args.get("rank_mode", "").strip()
    rank_by = args.get("rank_by", "co2_mass").strip()
    rank_n = max(1, min(args.get("rank_n", 10, type=int) or 10, 1000))
    page = max(1, args.get("page", 1, type=int) or 1)
    per_page = 25

    # Keep the live CAMPD API search independent of the local imported data.
    campd_search = args.get("campd_search") == "1"
    campd_dataset = args.get("campd_dataset", "annual_facility").strip()
    campd_state = args.get("campd_state", state).strip().upper()
    campd_year = args.get("campd_year", year).strip()
    campd_oris_code = args.get("campd_oris_code", "").strip()
    campd_page = max(1, args.get("campd_page", 1, type=int) or 1)
    campd_per_page = args.get("campd_per_page", 50, type=int) or 50

    if campd_per_page not in (25, 50, 100, 500):
        campd_per_page = 50

    campd_records = []
    campd_columns = []
    campd_total = None
    campd_error = None

    if campd_search:
        try:
            if campd_state not in {code for code, _ in STATE_OPTIONS}:
                raise CAMPDServiceError("Choose a state before searching CAMPD.")

            if campd_dataset.startswith("hourly_"):
                begin_date = args.get("campd_begin_date", "").strip()
                end_date = args.get("campd_end_date", "").strip()

                if not begin_date and campd_year.isdigit():
                    begin_date = f"{campd_year}-01-01"
                if not end_date and campd_year.isdigit():
                    end_date = f"{int(campd_year) + 1}-01-01"
            else:
                begin_date = ""
                end_date = ""

            filters = build_dataset_filters(
                dataset=campd_dataset,
                state_code=campd_state,
                year=campd_year,
                begin_date=begin_date,
                end_date=end_date,
                oris_code=campd_oris_code,
            )

            result = fetch_dataset_with_provenance(
                dataset=campd_dataset,
                filters=filters,
                page=campd_page,
                per_page=campd_per_page,
            )

            campd_records = [
                item for item in result["records"] if isinstance(item, dict)
            ]
            campd_total = result["total"]

            for item in campd_records:
                for key in item:
                    if key not in campd_columns and len(campd_columns) < 12:
                        campd_columns.append(key)

        except CAMPDServiceError as exc:
            campd_error = str(exc)

    # Reflect the selected, existing Supabase table.
    dataset_config = LOCAL_DATASETS[dataset_key]
    metadata = MetaData()

    try:
        table = Table(
            dataset_config["table"],
            metadata,
            autoload_with=db.engine,
        )
    except Exception:
        # A missing table or database connection should not silently look
        # like a successful search returning zero rows.
        raise

    columns = {
        key: get_column(table, candidates)
        for key, candidates in COLUMN_CANDIDATES.items()
    }

    def selected_column(key):
        column = columns.get(key)
        return column if column is not None else None

    # Select into predictable names so the template doesn't depend on
    # database column names containing spaces or units.
    select_items = []
    for key, column in columns.items():
        if column is not None:
            select_items.append(column.label(key))

    if not select_items:
        records = []
        pagination = None
        years = []
        fuels = []
        controls = []
    else:
        query = select(*select_items)
        conditions = []

        # Facility search is available only for facility-level datasets.
        if facility_name and selected_column("facility_name") is not None:
            conditions.append(
                selected_column("facility_name").ilike(f"%{facility_name}%")
            )

        if state and selected_column("state") is not None:
            conditions.append(selected_column("state") == state)

        # Annual tables have a Year column; hourly tables have a Date column.
        year_column = selected_column("year")
        date_column = selected_column("date")

        def year_expression():
            if year_column is not None:
                return year_column
            if date_column is not None:
                return extract("year", date_column)
            return None

        year_expr = year_expression()

        if year and year.isdigit() and year_expr is not None:
            conditions.append(year_expr == int(year))

        if min_year.isdigit() and year_expr is not None:
            conditions.append(year_expr >= int(min_year))

        if max_year.isdigit() and year_expr is not None:
            conditions.append(year_expr <= int(max_year))

        # Apply the numeric range filters only where the selected table
        # actually has that measurement.
        numeric_filters = [
            ("gross_load", min_gross_load, max_gross_load),
            ("co2_mass", min_co2, max_co2),
            ("so2_mass", min_so2, max_so2),
            ("nox_mass", min_nox, max_nox),
            ("heat_input", min_heat_input, max_heat_input),
        ]

        for key, minimum, maximum in numeric_filters:
            column = selected_column(key)
            if column is None:
                continue

            low = parse_number(minimum)
            high = parse_number(maximum)

            if low is not None:
                conditions.append(column >= low)
            if high is not None:
                conditions.append(column <= high)

        if conditions:
            query = query.where(*conditions)

        # Count matching records before pagination.
        count_query = select(func.count()).select_from(
            query.order_by(None).subquery()
        )
        total = db.session.execute(count_query).scalar_one()

        # Sorting and Top/Bottom N use only known numeric/date columns.
        allowed_sort_columns = {
            key: selected_column(key)
            for key in (
                "year",
                "gross_load",
                "co2_mass",
                "so2_mass",
                "nox_mass",
                "heat_input",
            )
            if selected_column(key) is not None
        }

        if rank_mode in ("top", "bottom"):
            metric = allowed_sort_columns.get(rank_by)
            if metric is not None:
                query = query.order_by(
                    metric.desc() if rank_mode == "top" else metric.asc()
                )
            elif year_expr is not None:
                query = query.order_by(year_expr.desc())
            query = query.limit(rank_n)
            pagination = None
            result_rows = db.session.execute(query).mappings().all()
        else:
            metric = allowed_sort_columns.get(sort_by)
            if metric is not None:
                query = query.order_by(
                    metric.asc() if sort_order == "asc" else metric.desc()
                )
            elif year_expr is not None:
                query = query.order_by(year_expr.desc())

            if selected_column("facility_name") is not None:
                query = query.order_by(selected_column("facility_name").asc())

            query = query.limit(per_page).offset((page - 1) * per_page)
            result_rows = db.session.execute(query).mappings().all()

            # A small pagination object compatible with the existing template.
            class Pagination:
                def __init__(self, current_page, page_size, total_rows):
                    self.page = current_page
                    self.per_page = page_size
                    self.total = total_rows
                    self.pages = (total_rows + page_size - 1) // page_size
                    self.has_prev = current_page > 1
                    self.has_next = current_page < self.pages
                    self.prev_num = current_page - 1
                    self.next_num = current_page + 1

            pagination = Pagination(page, per_page, total)

        # Convert SQLAlchemy mapping rows to dictionaries with the same keys
        # expected by the revised results table.
        records = [dict(row) for row in result_rows]

        years = []
        if year_column is not None:
            years = [
                row[0]
                for row in db.session.execute(
                    select(year_column).distinct().order_by(year_column.desc())
                ).all()
                if row[0] is not None
            ]
        elif date_column is not None:
            years = [
                row[0]
                for row in db.session.execute(
                    select(extract("year", date_column).label("yr"))
                    .distinct()
                    .order_by(extract("year", date_column).desc())
                ).all()
                if row[0] is not None
            ]

        years = sorted({int(y) for y in years}, reverse=True)

        # These imported tables do not currently provide fuel/control options.
        fuels = []
        controls = []

    return render_template(
        "explorer.html",
        records=records,
        pagination=pagination,
        datasets=LOCAL_DATASETS,
        selected_dataset=dataset_key,
        years=years,
        fuels=fuels,
        controls=controls,
        selected_facility=facility_name,
        selected_state=state,
        selected_unit=unit_id,
        selected_fuel=fuel,
        selected_year=year,
        selected_control=control,
        min_gross_load=min_gross_load,
        max_gross_load=max_gross_load,
        min_co2=min_co2,
        max_co2=max_co2,
        min_so2=min_so2,
        max_so2=max_so2,
        min_nox=min_nox,
        max_nox=max_nox,
        min_heat_input=min_heat_input,
        max_heat_input=max_heat_input,
        min_year=min_year,
        max_year=max_year,
        sort_by=sort_by,
        sort_order=sort_order,
        rank_mode=rank_mode,
        rank_by=rank_by,
        rank_n=rank_n,
        campd_records=campd_records,
        campd_columns=campd_columns,
        campd_total=campd_total,
        campd_error=campd_error,
        campd_searched=campd_search,
        campd_page=campd_page,
        campd_per_page=campd_per_page,
        campd_datasets=EMISSION_DATASETS,
        campd_states=STATE_OPTIONS,
        campd_state=campd_state,
        campd_year=campd_year,
        campd_oris_code=campd_oris_code,
        campd_begin_date=args.get("campd_begin_date", ""),
        campd_end_date=args.get("campd_end_date", ""),
    )