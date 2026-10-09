import json

from app import db
from app.models import DatasetMetadata


def create_dataset_metadata(
    dataset,
    title,
    description=None,
    source=None,
    source_url=None,
    geographic_scope=None,
    filters_applied=None,
    file_format="CSV",
    notes=None,
    record_count=None,
):
    metadata = DatasetMetadata(
        dataset_id=dataset.id,
        title=title,
        description=description,
        source=source or dataset.data_source,
        source_url=source_url,
        reporting_year=dataset.reporting_year,
        geographic_scope=geographic_scope,
        filters_applied=json.dumps(filters_applied)
        if filters_applied
        else None,
        record_count=(
            record_count
            if record_count is not None
            else dataset.accepted_record_count
        ),
        file_format=file_format,
        notes=notes,
    )

    db.session.add(metadata)

    return metadata