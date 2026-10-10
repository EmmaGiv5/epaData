from flask import Blueprint, render_template, request

from app.services.campd_service import (
    DATASETS,
    CAMPDServiceError,
    fetch_dataset,
    filter_records,
)

campd_bp = Blueprint(
    "campd",
    __name__,
    url_prefix="/campd",
)


@campd_bp.route("/search", methods=["GET"])
def search():
    dataset = request.args.get("dataset", "facilities")

    if dataset not in DATASETS:
        dataset = "facilities"

    query = request.args.get("q", "").strip()
    state_code = request.args.get("state", "").strip().upper()
    year_text = request.args.get("year", "").strip()
    begin_date = request.args.get("beginDate", "").strip()
    end_date = request.args.get("endDate", "").strip()
    oris_code = request.args.get("orisCode", "").strip()

    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = int(request.args.get("per_page", 50))
    except ValueError:
        page, per_page = 1, 50

    if per_page not in (25, 50, 100, 500):
        per_page = 50

    filters = {
        "stateCode": state_code,
        "orisCode": oris_code,
        "beginDate": begin_date,
        "endDate": end_date,
    }

    error = None
    records = []
    total = None
    searched = request.args.get("search") == "1"

    if year_text:
        try:
            year = int(year_text)
            if not 1900 <= year <= 2100:
                raise ValueError
            filters["year"] = year
        except ValueError:
            error = "Enter a valid four-digit reporting year."

    if searched and not error:
        try:
            result = fetch_dataset(
                dataset=dataset,
                filters=filters,
                page=page,
                per_page=per_page,
            )

            records = filter_records(
                result["records"],
                query=query,
            )
            total = result["total"]

        except CAMPDServiceError as exc:
            error = str(exc)

    columns = list(records[0].keys()) if records else []

    return render_template(
        "campd/search.html",
        datasets=DATASETS,
        selected_dataset=dataset,
        query=query,
        state_code=state_code,
        year_text=year_text,
        oris_code=oris_code,
        page=page,
        per_page=per_page,
        records=records,
        columns=columns,
        total=total,
        error=error,
        begin_date=begin_date,
        end_date=end_date,
        searched=searched,
    )