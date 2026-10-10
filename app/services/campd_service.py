import json
import os
from datetime import date

import requests
from dotenv import load_dotenv # loads the environment from .env file
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

BASE_URL = "https://api.epa.gov/easey"


class CAMPDServiceError(RuntimeError):
    """Raised when the CAMPD API cannot be reached or configured."""


DATASET_PATHS = {
    "facilities": "/facilities-mgmt/facilities",
    "hourly_facility": (
        "/emissions-mgmt/emissions/apportioned/hourly/by-facility"
    ),
    "hourly_state": (
        "/emissions-mgmt/emissions/apportioned/hourly/by-state"
    ),
    "annual_facility": (
        "/emissions-mgmt/emissions/apportioned/annual/by-facility"
    ),
    "annual_state": (
        "/emissions-mgmt/emissions/apportioned/annual/by-state"
    ),
}

DATASETS = {
    "facilities": "Facilities",
    "hourly_facility": "Hourly Emissions by Facility",
    "hourly_state": "Hourly Emissions by State",
    "annual_facility": "Annual Emissions by Facility",
    "annual_state": "Annual Emissions by State",
}

EMISSION_DATASETS = {
    key: value for key, value in DATASETS.items() if key != "facilities"
}

STATE_OPTIONS = (
    ("AL", "Alabama"),
    ("GA", "Georgia"),
    ("KY", "Kentucky"),
    ("MS", "Mississippi"),
    ("TN", "Tennessee")
)

MIN_CAMPD_DATE = date(2015, 1, 1)
MAX_CAMPD_DATE = date(2025, 1, 1)


def build_dataset_filters( # validates search filters, NOT AUTHENTICATES
    dataset: str,
    state_code: str,
    year: str = "",
    begin_date: str = "",
    end_date: str = "",
    oris_code: str = "",
) -> dict:
    """Validate a single-state CAMPD search and return API filters."""
    valid_states = {code for code, _ in STATE_OPTIONS}
    if state_code not in valid_states:
        raise CAMPDServiceError("Choose a valid U.S. state.")
    if dataset not in EMISSION_DATASETS:
        raise CAMPDServiceError("Choose one of the CAMPD emissions datasets.")

    filters = {"stateCode": state_code}
    if oris_code:
        if not oris_code.isdigit():
            raise CAMPDServiceError("Facility ID must contain digits only.")
        if not dataset.endswith("_facility"):
            raise CAMPDServiceError(
                "Facility ID filtering is available only for "
                "by-facility datasets."
            )
        filters["orisCode"] = oris_code

    if dataset in ("hourly_facility", "hourly_state"):
        try:
            start = date.fromisoformat(begin_date)
            end = date.fromisoformat(end_date)
        except ValueError as exc:
            raise CAMPDServiceError(
                "Enter valid start and end dates."
            ) from exc

        if (
            start < MIN_CAMPD_DATE
            or end > MAX_CAMPD_DATE
            or start >= end
        ):
            raise CAMPDServiceError(
                "Hourly searches must be within 2015-01-01 "
                "through 2025-01-01, with the start before the end."
            )
        filters.update({
            "beginDate": start.isoformat(),
            "endDate": end.isoformat(),
        })
    elif dataset in ("annual_facility", "annual_state"):
        try:
            reporting_year = int(year)
        except (TypeError, ValueError) as exc:
            raise CAMPDServiceError(
                "Choose a reporting year from 2015 through 2025."
            ) from exc
        if not 2015 <= reporting_year <= 2025:
            raise CAMPDServiceError(
                "Choose a reporting year from 2015 through 2025."
            )
        filters["year"] = reporting_year

    return filters

 
def _api_key() -> str: # retrieves and validates the key from the environment
    key = os.getenv("CAMPD_API_KEY") or os.getenv("EPA_API_KEY")
    if not key:
        raise CAMPDServiceError(
            "CAMPD_API_KEY is not configured. "
            "Set it in your environment or .env file."
        )
    return key

# Authentican process
def fetch_dataset(
    dataset: str,
    filters: dict | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Fetch one page of records from a CAMPD dataset."""
    if dataset not in DATASET_PATHS:
        raise CAMPDServiceError(
            f"Unsupported CAMPD dataset: {dataset}"
        )

    if page < 1 or per_page not in (25, 50, 100, 500):
        raise CAMPDServiceError("Invalid page or per_page value.")

    params = {
        key: value
        for key, value in (filters or {}).items()
        if value is not None and value != ""
    }

    params.update({
        "api_key": _api_key(),
        "page": page,
        "perPage": per_page,
    })

    url = BASE_URL + DATASET_PATHS[dataset]

    try:
        response = requests.get(
            url,
            headers={"Accept": "application/json"},
            params=params,
            timeout=60,
        )
        response.raise_for_status() # is there's an error 
        payload = response.json()
    except requests.RequestException as exc:
        raise CAMPDServiceError(
            "CAMPD request failed for "
            f"{dataset} ({type(exc).__name__})."
        ) from exc
    except ValueError as exc:
        raise CAMPDServiceError(
            f"CAMPD returned invalid JSON for {dataset}."
        ) from exc

    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = None
        for key in ("records", "results", "items", "data"):
            if isinstance(payload.get(key), list):
                records = payload[key]
                break
        if records is None:
            raise CAMPDServiceError(
                "Unexpected API response format. "
                f"Response keys: {list(payload.keys())}"
            )
    else:
        raise CAMPDServiceError("Unexpected API response format.")

    total_header = response.headers.get("X-Total-Count")
    if total_header is not None:
        try:
            total = int(total_header)
        except ValueError:
            total = len(records)
    else:
        total = payload.get("total", len(records)) if isinstance(
            payload, dict
        ) else len(records)

    return {
        "records": records,
        "total": total,
    }


def fetch_dataset_with_provenance( # calls the API and saves metadata about the retrieval, but not the records themselves
    dataset: str,
    filters: dict | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Fetch one live page and persist its non-secret retrieval metadata."""
    result = fetch_dataset(
        dataset=dataset,
        filters=filters,
        page=page,
        per_page=per_page,
    )

    safe_parameters = {
        key: value
        for key, value in (filters or {}).items()
        if key.lower() not in {"api_key", "apikey"}
    }
    safe_parameters.update({"page": page, "perPage": per_page})
    records = result["records"]
    reporting_year = safe_parameters.get("year")
    if reporting_year is None:
        begin_date = safe_parameters.get("beginDate")
        end_date = safe_parameters.get("endDate")
        if (
            isinstance(begin_date, str)
            and isinstance(end_date, str)
            and begin_date[:4] == end_date[:4]
        ):
            reporting_year = int(begin_date[:4])

    try:
        from app import db
        from app.models import DataProvenance, Dataset

        dataset_row = Dataset(
            dataset_name=(
                f"CAMPD live query: {DATASETS[dataset]} "
                f"({safe_parameters.get('stateCode', 'all states')}, "
                f"page {page})"
            ),
            data_source="EPA CAMPD API",
            reporting_year=reporting_year,
            raw_record_count=len(records),
            accepted_record_count=len(records),
            notes=(
                "Live API results were displayed but not stored. "
                f"API-reported total: {result['total']}."
            ),
        )
        db.session.add(dataset_row)
        db.session.flush()
        db.session.add(DataProvenance(
            dataset_id=dataset_row.id,
            source="EPA CAMPD API",
            source_url=BASE_URL + DATASET_PATHS[dataset],
            query_parameters=json.dumps(
                safe_parameters,
                sort_keys=True,
                separators=(",", ":"),
            ),
            reporting_year=reporting_year,
            record_count=len(records),
            notes=f"Live CAMPD response page {page}; not persisted.",
        ))
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise CAMPDServiceError(
            "CAMPD returned data, but its retrieval metadata "
            "could not be saved."
        ) from exc

    return result


def filter_records( # searches records already retrieved from the API, without making a new request
    records: list[dict],
    query: str = "",
) -> list[dict]:
    """Filter returned records by a free-text query."""
    if not records:
        return []

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return list(records)

    return [
        record
        for record in records
        if isinstance(record, dict)
        and any(
            normalized_query in str(value).lower()
            for value in record.values()
        )
    ]
