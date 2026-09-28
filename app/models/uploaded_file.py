# This represents information about a file a user uploaded.
# The database table stores metadata about the file.

from datetime import datetime

from app import db


class UploadedFile(db.Model):
    __tablename__ = "uploaded_files"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("datasets.id"),
        nullable=True
    )

    original_filename = db.Column(
        db.String(255),
        nullable=False
    )

    stored_filename = db.Column(
        db.String(255),
        nullable=True
    )

    file_type = db.Column(
        db.String(20),
        nullable=False
    )

    file_size = db.Column(
        db.Integer,
        nullable=True
    )

    upload_date = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    status = db.Column(
        db.String(50),
        default="uploaded",
        nullable=False
    )

    dataset = db.relationship(
        "Dataset",
        back_populates="uploaded_files"
    )

    def __repr__(self):
        return f"<UploadedFile {self.original_filename}>"
