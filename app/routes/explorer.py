# Handles the Data Explorer

from flask import Blueprint, render_template, request

from app.models import AnnualRecord, Unit, Facility


explorer_bp = Blueprint(
    "explorer",
    __name__,
    url_prefix="/explorer"
)


@explorer_bp.route("/", methods=["GET"])
def explorer():

    # -----------------------------
    # Get filter values
    # -----------------------------

    facility_name = request.args.get("facility", "").strip()
    state = request.args.get("state", "").strip()
    unit_id = request.args.get("unit", "").strip()
    fuel = request.args.get("fuel", "").strip()
    year = request.args.get("year", "").strip()
    control = request.args.get("control", "").strip()

    # Numeric range filters
    min_gross_load = request.args.get("min_gross_load", "").strip()
    max_gross_load = request.args.get("max_gross_load", "").strip()

    min_co2 = request.args.get("min_co2", "").strip()
    max_co2 = request.args.get("max_co2", "").strip()

    min_so2 = request.args.get("min_so2", "").strip()
    max_so2 = request.args.get("max_so2", "").strip()

    min_nox = request.args.get("min_nox", "").strip()
    max_nox = request.args.get("max_nox", "").strip()

    min_heat_input = request.args.get("min_heat_input", "").strip()
    max_heat_input = request.args.get("max_heat_input", "").strip()


    # -----------------------------
    # Base query
    # -----------------------------

    query = (
        AnnualRecord.query
        .join(Unit, AnnualRecord.unit_id == Unit.id)
        .join(Facility, Unit.facility_id == Facility.id)
    )


    # -----------------------------
    # Facility Search
    # -----------------------------

    if facility_name:
        query = query.filter(
            Facility.facility_name.ilike(
                f"%{facility_name}%"
            )
        )


    # -----------------------------
    # State
    # -----------------------------

    if state:
        query = query.filter(
            Facility.state == state
        )


    # -----------------------------
    # Unit
    # -----------------------------

    if unit_id:
        query = query.filter(
            Unit.epa_unit_id.ilike(
                f"%{unit_id}%"
            )
        )


    # -----------------------------
    # Fuel
    # -----------------------------

    if fuel:
        query = query.filter(
            Unit.primary_fuel.ilike(
                f"%{fuel}%"
            )
        )


    # -----------------------------
    # Year
    # -----------------------------

    if year:
        try:
            query = query.filter(
                AnnualRecord.reporting_year == int(year)
            )
        except ValueError:
            pass


    # -----------------------------
    # Control Technology
    # -----------------------------

    if control:

        query = query.filter(
            (
                Unit.id.in_(
                    query.session.query(Unit.id)
                    .filter(
                        Unit.primary_fuel.ilike(
                            f"%{control}%"
                        )
                    )
                )
            )
            |
            (
                AnnualRecord.so2_control.ilike(
                    f"%{control}%"
                )
            )
            |
            (
                AnnualRecord.nox_control.ilike(
                    f"%{control}%"
                )
            )
            |
            (
                AnnualRecord.pm_control.ilike(
                    f"%{control}%"
                )
            )
        )


    # -----------------------------
    # Numeric ranges
    # -----------------------------

    def apply_min_max(query, column, minimum, maximum):

        if minimum:
            try:
                query = query.filter(
                    column >= float(minimum)
                )
            except ValueError:
                pass

        if maximum:
            try:
                query = query.filter(
                    column <= float(maximum)
                )
            except ValueError:
                pass

        return query


    query = apply_min_max(
        query,
        AnnualRecord.gross_load,
        min_gross_load,
        max_gross_load
    )

    query = apply_min_max(
        query,
        AnnualRecord.co2_mass,
        min_co2,
        max_co2
    )

    query = apply_min_max(
        query,
        AnnualRecord.so2_mass,
        min_so2,
        max_so2
    )

    query = apply_min_max(
        query,
        AnnualRecord.nox_mass,
        min_nox,
        max_nox
    )

    query = apply_min_max(
        query,
        AnnualRecord.heat_input,
        min_heat_input,
        max_heat_input
    )


    # -----------------------------
    # Get results
    # -----------------------------

    records = (
        query
        .order_by(
            AnnualRecord.reporting_year.desc(),
            Facility.facility_name,
            Unit.epa_unit_id
        )
        .all()
    )


    # -----------------------------
    # Filter dropdown values
    # -----------------------------

    years = [
        row[0]
        for row in (
            AnnualRecord.query
            .with_entities(
                AnnualRecord.reporting_year
            )
            .distinct()
            .order_by(
                AnnualRecord.reporting_year.desc()
            )
            .all()
        )
    ]


    states = [
        row[0]
        for row in (
            Facility.query
            .with_entities(
                Facility.state
            )
            .filter(
                Facility.state.isnot(None)
            )
            .distinct()
            .order_by(
                Facility.state
            )
            .all()
        )
    ]


    fuels = [
        row[0]
        for row in (
            Unit.query
            .with_entities(
                Unit.primary_fuel
            )
            .filter(
                Unit.primary_fuel.isnot(None)
            )
            .distinct()
            .order_by(
                Unit.primary_fuel
            )
            .all()
        )
    ]


    # -----------------------------
    # Control technology values
    # -----------------------------

    controls = set()

    for row in (
        AnnualRecord.query
        .with_entities(
            AnnualRecord.so2_control,
            AnnualRecord.nox_control,
            AnnualRecord.pm_control
        )
        .all()
    ):

        for value in row:

            if value:
                controls.add(value)


    controls = sorted(controls)


    # -----------------------------
    # Render page
    # -----------------------------

    return render_template(
        "explorer.html",

        records=records,

        years=years,
        states=states,
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
    )