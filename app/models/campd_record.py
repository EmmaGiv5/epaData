from datetime import datetime

from app import db


class CampdRecord(db.Model):
    __tablename__ = "campd_records"

    id = db.Column(db.Integer, primary_key=True)
    dataset_type = db.Column(db.String(40), nullable=False, index=True)
    state_code = db.Column(db.String(2), nullable=False, index=True)
    reporting_year = db.Column(db.Integer, nullable=False, index=True)
    record_hash = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(db.Text, nullable=False)
    fetched_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "dataset_type",
            "state_code",
            "reporting_year",
            "record_hash",
            name="unique_campd_record",
        ),
    )

    def __repr__(self):
        return (
            f"<CampdRecord {self.dataset_type} "
            f"{self.state_code} {self.reporting_year}>"
        )
