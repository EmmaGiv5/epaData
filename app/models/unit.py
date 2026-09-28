# Represents generating units belonging to a facility.

from app import db


class Unit(db.Model):
    __tablename__ = "units"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    facility_id = db.Column(
        db.Integer,
        db.ForeignKey("facilities.id"),
        nullable=False,
        index=True
    )

    epa_unit_id = db.Column(
        db.String(50),
        nullable=False
    )

    unit_type = db.Column(
        db.String(100),
        nullable=True
    )

    primary_fuel = db.Column(
        db.String(100),
        nullable=True,
        index=True
    )

    secondary_fuel = db.Column(
        db.String(100),
        nullable=True
    )

    operating_date = db.Column(
        db.Date,
        nullable=True
    )

    retirement_date = db.Column(
        db.Date,
        nullable=True
    )

    # Relationships
    facility = db.relationship(
        "Facility",
        back_populates="units"
    )

    annual_records = db.relationship(
        "AnnualRecord",
        back_populates="unit",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Unit {self.epa_unit_id}>"
