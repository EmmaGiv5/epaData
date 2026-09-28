# It represents yearly operating/emissions data for a particular facility/unit.

from app import db


class AnnualRecord(db.Model):
    __tablename__ = "annual_records"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    unit_id = db.Column(
        db.Integer,
        db.ForeignKey("units.id"),
        nullable=False,
        index=True
    )

    reporting_year = db.Column(
        db.Integer,
        nullable=False,
        index=True
    )

    operating_time = db.Column(
        db.Float,
        nullable=True
    )

    gross_load = db.Column(
        db.Float,
        nullable=True
    )

    steam_load = db.Column(
        db.Float,
        nullable=True
    )

    heat_input = db.Column(
        db.Float,
        nullable=True
    )

    co2_mass = db.Column(
        db.Float,
        nullable=True
    )

    so2_mass = db.Column(
        db.Float,
        nullable=True
    )

    nox_mass = db.Column(
        db.Float,
        nullable=True
    )

    so2_control = db.Column(
        db.String(100),
        nullable=True
    )

    nox_control = db.Column(
        db.String(100),
        nullable=True
    )

    pm_control = db.Column(
        db.String(100),
        nullable=True
    )

    program_code = db.Column(
        db.String(100),
        nullable=True
    )

    # Relationship
    unit = db.relationship(
        "Unit",
        back_populates="annual_records"
    )

    # Prevent duplicate unit/year records
    __table_args__ = (
        db.UniqueConstraint(
            "unit_id",
            "reporting_year",
            name="unique_unit_reporting_year"
        ),
    )

    def __repr__(self):
        return (
            f"<AnnualRecord "
            f"unit={self.unit_id} "
            f"year={self.reporting_year}>"
        )
