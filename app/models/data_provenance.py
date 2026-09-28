# to preserve retrieval information

from datetime import datetime

from app import db


class DataProvenance(db.Model):
    __tablename__ = "data_provenance"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id"),
        nullable=False
    )

    source = db.Column(
        db.String(255),
        nullable=False
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

    query_parameters = db.Column(
        db.Text,
        nullable=True
    )

    reporting_year = db.Column(
        db.Integer,
        nullable=True
    )

    record_count = db.Column(
        db.Integer,
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    dataset = db.relationship(
        "Dataset",
        back_populates="provenance_records"
    )

    def __repr__(self):
        return f"<DataProvenance {self.source}>"
