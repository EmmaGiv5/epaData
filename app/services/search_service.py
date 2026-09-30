# Handles Data Explorer searches.
# Constructs the SQLAlchemy database query 
# Handle: sorting, pagination, ranges, topN, bottomN, and historical searches

from app.models import AnnualRecord


SORT_COLUMNS = {
    "year": AnnualRecord.reporting_year,
    "gross_load": AnnualRecord.gross_load,
    "co2_mass": AnnualRecord.co2_mass,
    "so2_mass": AnnualRecord.so2_mass,
    "nox_mass": AnnualRecord.nox_mass,
    "heat_input": AnnualRecord.heat_input,
}


def apply_min_max(query, column, minimum, maximum):
    """Apply optional numeric minimum/maximum filters."""

    if minimum:
        try:
            query = query.filter(column >= float(minimum))
        except (ValueError, TypeError):
            pass

    if maximum:
        try:
            query = query.filter(column <= float(maximum))
        except (ValueError, TypeError):
            pass

    return query


def apply_sorting(query, sort_by, sort_order="desc"):
    """Apply user-selected sorting."""

    column = SORT_COLUMNS.get(sort_by)

    if column is None:
        return query

    if sort_order == "asc":
        return query.order_by(column.asc())

    return query.order_by(column.desc())


def apply_ranking(query, rank_mode, rank_by, rank_n):
    """Apply Top-N or Bottom-N ranking."""

    column = SORT_COLUMNS.get(rank_by)

    if column is None:
        return query

    if not rank_n or rank_n < 1:
        return query

    if rank_mode == "top":
        query = query.order_by(column.desc())
    elif rank_mode == "bottom":
        query = query.order_by(column.asc())
    else:
        return query

    return query.limit(rank_n)