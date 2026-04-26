"""Add Phase 2 ingestion lineage and mapping fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0002_ingestion_phase2"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "is_active" in {column["name"] for column in inspector.get_columns("mapping_templates")}:
        return

    op.add_column(
        "mapping_templates",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "mapping_templates",
        sa.Column("created_by_id", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "mapping_templates",
        sa.Column("required_fields", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "mapping_templates",
        sa.Column(
            "transformation_hints", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    if op.get_context().dialect.name != "sqlite":
        op.create_foreign_key(
            "fk_mapping_templates_created_by_id_users",
            "mapping_templates",
            "users",
            ["created_by_id"],
            ["id"],
        )

    op.add_column(
        "upload_batches",
        sa.Column("applied_rows", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "upload_batches",
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "upload_batches",
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "upload_batches",
        sa.Column("duplicate_of_batch_id", sa.String(length=40), nullable=True),
    )
    op.add_column(
        "upload_batches",
        sa.Column("preview_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "upload_batches",
        sa.Column(
            "validation_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
        ),
    )
    op.add_column(
        "upload_batches",
        sa.Column("status_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )


def downgrade() -> None:
    op.drop_column("upload_batches", "status_payload")
    op.drop_column("upload_batches", "validation_payload")
    op.drop_column("upload_batches", "preview_payload")
    op.drop_column("upload_batches", "duplicate_of_batch_id")
    op.drop_column("upload_batches", "warning_count")
    op.drop_column("upload_batches", "failed_rows")
    op.drop_column("upload_batches", "applied_rows")

    if op.get_context().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_mapping_templates_created_by_id_users",
            "mapping_templates",
            type_="foreignkey",
        )
    op.drop_column("mapping_templates", "transformation_hints")
    op.drop_column("mapping_templates", "required_fields")
    op.drop_column("mapping_templates", "created_by_id")
    op.drop_column("mapping_templates", "is_active")
