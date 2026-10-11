import csv
import io
import json

from flask import Response


def _csv_value(value):
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def csv_download(columns, rows, filename):
    """Return rows as a UTF-8 CSV attachment."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=columns,
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({
            key: _csv_value(value)
            for key, value in row.items()
        })

    response = Response(
        buffer.getvalue(),
        content_type="text/csv; charset=utf-8",
    )
    response.headers.set(
        "Content-Disposition",
        "attachment",
        filename=filename,
    )
    return response
