# Represents the facilities table.

from app import db


class Facility(db.Model):
    __tablename__ = "facilities"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id"),
        nullable=True
    )

    epa_facility_id = db.Column(
        db.String(50),
        nullable=False
    )

    facility_name = db.Column(
        db.String(255),
        nullable=False
    )

    state = db.Column(
        db.String(2),
        nullable=True,
        index=True
    )

    latitude = db.Column(
        db.Float,
        nullable=True
    )

    longitude = db.Column(
        db.Float,
        nullable=True
    )

    source_category = db.Column(
        db.String(100),
        nullable=True
    )

    # Relationships
    dataset = db.relationship(
        "Dataset",
        back_populates="facilities"
    )

    units = db.relationship(
        "Unit",
        back_populates="facility",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Facility {self.epa_facility_id}>"
