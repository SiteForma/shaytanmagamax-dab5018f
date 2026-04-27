"""Add SKU cost import history."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_sku_cost_history"
down_revision = "0009_sku_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "sku_cost_history" in inspector.get_table_names():
        return

    op.create_table(
        "sku_cost_history",
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
    )
    op.create_index(op.f("ix_sku_cost_history_article"), "sku_cost_history", ["article"])
    op.create_index(op.f("ix_sku_cost_history_sku_id"), "sku_cost_history", ["sku_id"])
    op.create_index(
        op.f("ix_sku_cost_history_upload_file_id"),
        "sku_cost_history",
        ["upload_file_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_sku_cost_history_upload_file_id"), table_name="sku_cost_history")
    op.drop_index(op.f("ix_sku_cost_history_sku_id"), table_name="sku_cost_history")
    op.drop_index(op.f("ix_sku_cost_history_article"), table_name="sku_cost_history")
    op.drop_table("sku_cost_history")
