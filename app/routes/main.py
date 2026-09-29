# Handles general website pages.

# Such as: project intro, current data coverage, 
# number of facilities, number of units, and navigation

# Creates your first webpage

import os

from flask import (
    Blueprint,
    render_template,
    request,
)

from werkzeug.utils import secure_filename

from app.services.validator import (
    read_uploaded_file,
    validate_dataframe,
    get_file_extension,
)


main_bp = Blueprint(
    "main",
    __name__
)


@main_bp.route("/")
def home():

    return render_template(
        "index.html"
    )


@main_bp.route(
    "/upload",
    methods=["GET", "POST"]
)
def upload():

    if request.method == "GET":

        return render_template(
            "upload.html"
        )

    uploaded_file = request.files.get(
        "data_file"
    )

    if not uploaded_file:

        return render_template(
            "upload.html",
            error="No file was selected."
        )

    if uploaded_file.filename == "":

        return render_template(
            "upload.html",
            error="No file was selected."
        )

    extension = get_file_extension(
        uploaded_file.filename
    )

    allowed_extensions = {
        ".csv",
        ".xlsx",
        ".xls",
    }

    if extension not in allowed_extensions:

        return render_template(
            "upload.html",
            error=(
                "Unsupported file type. "
                "Please upload CSV or Excel."
            )
        )

    filename = secure_filename(
        uploaded_file.filename
    )

    upload_folder = os.path.join(
        os.getcwd(),
        "uploads"
    )

    os.makedirs(
        upload_folder,
        exist_ok=True
    )

    file_path = os.path.join(
        upload_folder,
        filename
    )

    uploaded_file.save(file_path)

    try:

        dataframe = read_uploaded_file(
            file_path
        )

        validation = validate_dataframe(
            dataframe
        )

    except Exception as error:

        return render_template(
            "upload.html",
            error=f"Could not read file: {error}"
        )

    preview = dataframe.head(10).to_html(
        classes="data-table",
        index=False
    )

    return render_template(
        "upload.html",
        validation=validation,
        preview=preview,
    )