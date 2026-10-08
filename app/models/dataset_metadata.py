from datetime import datetime

from app import db


class DatasetMetadata(db.Model):
    __tablename__ = "dataset_metadata"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id"),
        nullable=False,
        unique=True
    )

    title = db.Column(
        db.String(255),
        nullable=True
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    source = db.Column(
        db.String(255),
        nullable=True
    )

    source_url = db.Column(
        db.String(1000),
        nullable=True
    )

    retrieval_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    reporting_year = db.Column(
        db.Integer,
        nullable=True
    )

    geographic_scope = db.Column(
        db.String(255),
        nullable=True
    )

    filters_applied = db.Column(
        db.Text,
        nullable=True
    )

    record_count = db.Column(
        db.Integer,
        nullable=True
    )

    file_format = db.Column(
        db.String(50),
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    # Relationship back to Dataset
    dataset = db.relationship(
        "Dataset",
        back_populates="dataset_metadata"
    )

    def __repr__(self):
        return f"<DatasetMetadata {self.title}>"