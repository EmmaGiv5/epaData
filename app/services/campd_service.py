import os
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class CAMPDServiceError(RuntimeError):
    """Raised when the CAMPD API cannot be reached or configured."""


DATASET_PATHS = {
    "facilities": "/facilities-mgmt/facilities",
}

DATASETS = {name: "Facilities" for name in DATASET_PATHS}


def _api_headers():
    headers = {"Accept": "application/json"}
    api_key = os.getenv("CAMPD_API_KEY") or os.getenv("EPA_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def fetch_dataset(dataset: str, filters=None, page: int = 1, per_page: int = 50):
    """Fetch records for a CAMPD dataset.

    The project keeps the service lazy so importing the Flask app does not fail
    when the API key is not configured yet.
    """
    if dataset not in DATASET_PATHS:
        raise CAMPDServiceError(f"Unsupported CAMPD dataset: {dataset}")

    api_key = os.getenv("CAMPD_API_KEY") or os.getenv("EPA_API_KEY")
    if not api_key:
        raise CAMPDServiceError(
            "CAMPD_API_KEY is not configured. Set it in the environment or .env file."
        )

    params = dict(filters or {})
    params.update({"page": page, "per_page": per_page})

    response = requests.get(
        "https://api.epa.gov/easey" + DATASET_PATHS[dataset],
        headers=_api_headers(),
        params=params,
        timeout=30,
    )

    try:
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network path
        raise CAMPDServiceError(f"CAMPD request failed: {exc}") from exc

    payload = response.json()
    records = payload.get("records")
    if records is None:
        records = payload.get("results")
    if records is None:
        records = payload.get("items", [])

    return {
        "records": records,
        "total": payload.get("total", len(records)),
    }


def filter_records(records, query: str = ""):
    """Filter records by a free-text query across all values."""
    if not records:
        return []

    normalized_query = (query or "").strip().lower()
    if not normalized_query:
        return list(records)

    filtered = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if any(normalized_query in str(value).lower() for value in record.values()):
            filtered.append(record)
    return filtered
