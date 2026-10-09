# Stores TRACI environmental-impact characterization factors.
# allows searching and comparing environmental impacts easier 

from app import db


class TraciFactor(db.Model):
    __tablename__ = "traci_factors"

    id = db.Column(db.Integer, primary_key=True)

    cas_number = db.Column(
        db.String(50),
        nullable=True,
        index=True
    )

    substance_name = db.Column(
        db.String(255),
        nullable=False,
        index=True
    )

    impact_category = db.Column(
        db.String(255),
        nullable=False,
        index=True
    )

    characterization_factor = db.Column(
        db.Float,
        nullable=True
    )

    unit = db.Column(
        db.String(100),
        nullable=True
    )

    cf_flag = db.Column(
        db.String(100),
        nullable=True
    )

    def __repr__(self):
        return (
            f"&lt;TraciFactor {self.substance_name}: "
            f"{self.impact_category}&gt;"
        )