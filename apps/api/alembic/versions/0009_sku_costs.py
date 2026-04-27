"""Add SKU cost reference table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_sku_costs"
down_revision = "0008_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "sku_costs" in inspector.get_table_names():
        return

    op.create_table(
        "sku_costs",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("article", sa.String(length=120), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("cost_rub", sa.Numeric(18, 4), nullable=False),
        sa.Column("sku_id", sa.String(length=40), nullable=True),
        sa.Column("upload_file_id", sa.String(length=40), nullable=True),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sku_id"], ["skus.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["upload_file_id"], ["upload_files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article", name="uq_sku_costs_article"),
    )
    op.create_index(op.f("ix_sku_costs_article"), "sku_costs", ["article"])
    op.create_index(op.f("ix_sku_costs_sku_id"), "sku_costs", ["sku_id"])
    op.create_index(op.f("ix_sku_costs_upload_file_id"), "sku_costs", ["upload_file_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_sku_costs_upload_file_id"), table_name="sku_costs")
    op.drop_index(op.f("ix_sku_costs_sku_id"), table_name="sku_costs")
    op.drop_index(op.f("ix_sku_costs_article"), table_name="sku_costs")
    op.drop_table("sku_costs")
