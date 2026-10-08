# Represents the datasets table.
# It stores information about an imported or retrieved dataset.
# keeps track of where a collection of data came from
from datetime import datetime

from app import db


class Dataset(db.Model):
    __tablename__ = "datasets"

    id = db.Column(db.Integer, primary_key=True)

    dataset_name = db.Column(
        db.String(200),
        nullable=False
    )

    data_source = db.Column(
        db.String(200),
        nullable=False
    )

    reporting_year = db.Column(
        db.Integer,
        nullable=True
    )

    retrieval_upload_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    original_filename = db.Column(
        db.String(255),
        nullable=True
    )

    raw_record_count = db.Column(
        db.Integer,
        default=0
    )

    accepted_record_count = db.Column(
        db.Integer,
        default=0
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    # Relationships
    facilities = db.relationship(
        "Facility",
        back_populates="dataset",
        cascade="all, delete-orphan"
    )

    uploaded_files = db.relationship(
        "UploadedFile",
        back_populates="dataset"
    )

    provenance_records = db.relationship(
        "DataProvenance",
        back_populates="dataset"
    )

    dataset_metadata = db.relationship(
            "DatasetMetadata", 
            back_populates="dataset",
            cascade="all, delete-orphan",
            uselist=False
    )

    def __repr__(self):
        return f"<Dataset {self.dataset_name}>"



