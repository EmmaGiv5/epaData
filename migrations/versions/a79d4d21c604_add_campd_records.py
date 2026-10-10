"""add stored CAMPD records

Revision ID: a79d4d21c604
Revises: 302a29e0f279
Create Date: 2026-10-10
"""
from alembic import op
import sqlalchemy as sa


revision = "a79d4d21c604"
down_revision = "302a29e0f279"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "campd_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_type", sa.String(length=40), nullable=False),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column("reporting_year", sa.Integer(), nullable=False),
        sa.Column("record_hash", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_type",
            "state_code",
            "reporting_year",
            "record_hash",
            name="unique_campd_record",
        ),
    )
    op.create_index(
        "ix_campd_records_dataset_type",
        "campd_records",
        ["dataset_type"],
    )
    op.create_index(
        "ix_campd_records_state_code",
        "campd_records",
        ["state_code"],
    )
    op.create_index(
        "ix_campd_records_reporting_year",
        "campd_records",
        ["reporting_year"],
    )


def downgrade():
    op.drop_index(
        "ix_campd_records_reporting_year",
        table_name="campd_records",
    )
    op.drop_index(
        "ix_campd_records_state_code",
        table_name="campd_records",
    )
    op.drop_index(
        "ix_campd_records_dataset_type",
        table_name="campd_records",
    )
    op.drop_table("campd_records")
