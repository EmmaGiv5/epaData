# Handles general website pages.

# Such as: project intro, current data coverage, 
# number of facilities, number of units, and navigation

# Creates your first webpage
from flask import Blueprint, render_template


main_bp = Blueprint(
    "main",
    __name__
)


@main_bp.route("/")
def home():
    return render_template("index.html")
