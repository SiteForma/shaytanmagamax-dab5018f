"""Add Google Sheet inbound sync fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_inbound_google_sheet_sync"
down_revision = "0006_management_report_knowledge"
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names("inbound_deliveries")

    if "container_ref" not in columns:
        op.add_column(
            "inbound_deliveries", sa.Column("container_ref", sa.String(length=120), nullable=True)
        )
        op.create_index(
            op.f("ix_inbound_deliveries_container_ref"), "inbound_deliveries", ["container_ref"]
        )
    if "free_stock_after_allocation_qty" not in columns:
        op.add_column(
            "inbound_deliveries",
            sa.Column(
                "free_stock_after_allocation_qty", sa.Float(), nullable=False, server_default="0"
            ),
        )
    if "client_order_qty" not in columns:
        op.add_column(
            "inbound_deliveries",
            sa.Column("client_order_qty", sa.Float(), nullable=False, server_default="0"),
        )
    if "sheet_status" not in columns:
        op.add_column(
            "inbound_deliveries", sa.Column("sheet_status", sa.String(length=120), nullable=True)
        )
    if "client_allocations" not in columns:
        op.add_column(
            "inbound_deliveries",
            sa.Column(
                "client_allocations", sa.JSON(), nullable=False, server_default=sa.text("'{}'")
            ),
        )
    if "raw_payload" not in columns:
        op.add_column(
            "inbound_deliveries",
            sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )


def downgrade() -> None:
    columns = _column_names("inbound_deliveries")
    if "raw_payload" in columns:
        op.drop_column("inbound_deliveries", "raw_payload")
    if "client_allocations" in columns:
        op.drop_column("inbound_deliveries", "client_allocations")
    if "sheet_status" in columns:
        op.drop_column("inbound_deliveries", "sheet_status")
    if "client_order_qty" in columns:
        op.drop_column("inbound_deliveries", "client_order_qty")
    if "free_stock_after_allocation_qty" in columns:
        op.drop_column("inbound_deliveries", "free_stock_after_allocation_qty")
    if "container_ref" in columns:
        op.drop_index(op.f("ix_inbound_deliveries_container_ref"), table_name="inbound_deliveries")
        op.drop_column("inbound_deliveries", "container_ref")
