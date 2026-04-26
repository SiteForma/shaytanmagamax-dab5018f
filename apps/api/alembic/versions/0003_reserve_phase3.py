"""Add Phase 3 reserve engine and policy fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0003_reserve_phase3"
down_revision = "0002_ingestion_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "active" in {column["name"] for column in inspector.get_columns("diy_policies")}:
        return

    op.add_column(
        "diy_policies",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "diy_policies",
        sa.Column("allowed_fallback_depth", sa.Integer(), nullable=False, server_default="4"),
    )
    op.add_column(
        "diy_policies",
        sa.Column("category_overrides", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "diy_policies",
        sa.Column("sku_overrides", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column("diy_policies", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("diy_policies", sa.Column("effective_from", sa.Date(), nullable=True))
    op.add_column("diy_policies", sa.Column("effective_to", sa.Date(), nullable=True))

    op.add_column(
        "reserve_runs",
        sa.Column("scope_type", sa.String(length=64), nullable=False, server_default="portfolio"),
    )
    op.add_column(
        "reserve_runs",
        sa.Column(
            "grouping_mode", sa.String(length=64), nullable=False, server_default="client_sku"
        ),
    )
    op.add_column(
        "reserve_runs",
        sa.Column(
            "demand_strategy",
            sa.String(length=64),
            nullable=False,
            server_default="weighted_recent_average",
        ),
    )
    op.add_column(
        "reserve_runs",
        sa.Column("include_inbound", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "reserve_runs",
        sa.Column("inbound_statuses", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column("reserve_runs", sa.Column("as_of_date", sa.Date(), nullable=True))
    op.add_column(
        "reserve_runs",
        sa.Column("summary_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    op.add_column("reserve_rows", sa.Column("policy_id", sa.String(length=40), nullable=True))
    op.add_column(
        "reserve_rows",
        sa.Column("client_priority_level", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "reserve_rows", sa.Column("sales_qty_1m", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "reserve_rows", sa.Column("sales_qty_3m", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "reserve_rows", sa.Column("sales_qty_6m", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column(
        "reserve_rows",
        sa.Column("history_months_available", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "reserve_rows",
        sa.Column(
            "demand_basis_type", sa.String(length=64), nullable=False, server_default="none"
        ),
    )
    op.add_column(
        "reserve_rows",
        sa.Column("basis_window_used", sa.String(length=64), nullable=False, server_default="none"),
    )
    op.add_column("reserve_rows", sa.Column("last_sale_date", sa.Date(), nullable=True))
    op.add_column(
        "reserve_rows",
        sa.Column("trend_signal", sa.String(length=32), nullable=False, server_default="flat"),
    )
    op.add_column(
        "reserve_rows",
        sa.Column("demand_stability", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column("reserve_rows", sa.Column("status_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("reserve_rows", "status_reason")
    op.drop_column("reserve_rows", "demand_stability")
    op.drop_column("reserve_rows", "trend_signal")
    op.drop_column("reserve_rows", "last_sale_date")
    op.drop_column("reserve_rows", "basis_window_used")
    op.drop_column("reserve_rows", "demand_basis_type")
    op.drop_column("reserve_rows", "history_months_available")
    op.drop_column("reserve_rows", "sales_qty_6m")
    op.drop_column("reserve_rows", "sales_qty_3m")
    op.drop_column("reserve_rows", "sales_qty_1m")
    op.drop_column("reserve_rows", "client_priority_level")
    op.drop_column("reserve_rows", "policy_id")

    op.drop_column("reserve_runs", "summary_payload")
    op.drop_column("reserve_runs", "as_of_date")
    op.drop_column("reserve_runs", "inbound_statuses")
    op.drop_column("reserve_runs", "include_inbound")
    op.drop_column("reserve_runs", "demand_strategy")
    op.drop_column("reserve_runs", "grouping_mode")
    op.drop_column("reserve_runs", "scope_type")

    op.drop_column("diy_policies", "effective_to")
    op.drop_column("diy_policies", "effective_from")
    op.drop_column("diy_policies", "notes")
    op.drop_column("diy_policies", "sku_overrides")
    op.drop_column("diy_policies", "category_overrides")
    op.drop_column("diy_policies", "allowed_fallback_depth")
    op.drop_column("diy_policies", "active")
