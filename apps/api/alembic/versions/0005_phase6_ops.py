"""Add Phase 6 exports persistence."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0005_phase6_ops"
down_revision = "0004_assistant_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "export_jobs" in inspector.get_table_names():
        return

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("requested_by_id", sa.String(length=40), nullable=True),
        sa.Column("export_type", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("format", sa.String(length=16), nullable=False, server_default="csv"),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("storage_key", sa.String(length=500), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filters_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("summary_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("download_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_export_jobs_requested_by_id"), "export_jobs", ["requested_by_id"])
    op.create_index(op.f("ix_export_jobs_export_type"), "export_jobs", ["export_type"])
    op.create_index(op.f("ix_export_jobs_status"), "export_jobs", ["status"])


def downgrade() -> None:
    op.drop_index(op.f("ix_export_jobs_status"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_export_type"), table_name="export_jobs")
    op.drop_index(op.f("ix_export_jobs_requested_by_id"), table_name="export_jobs")
    op.drop_table("export_jobs")
