"""Add management report knowledge tables."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_management_report_knowledge"
down_revision = "0005_phase6_ops"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    if "management_report_imports" in table_names:
        return

    op.create_table(
        "management_report_imports",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("report_year", sa.Integer(), nullable=True),
        sa.Column("sheet_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_row_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metric_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_by_id", sa.String(length=40), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["imported_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("checksum"),
    )
    op.create_index(
        op.f("ix_management_report_imports_checksum"),
        "management_report_imports",
        ["checksum"],
    )
    op.create_index(
        op.f("ix_management_report_imports_report_year"),
        "management_report_imports",
        ["report_year"],
    )

    op.create_table(
        "management_report_rows",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("import_id", sa.String(length=40), nullable=False),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("is_header", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("parsed_metric_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("raw_values", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"], ["management_report_imports.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_management_report_rows_import_id"), "management_report_rows", ["import_id"]
    )
    op.create_index(
        op.f("ix_management_report_rows_sheet_name"), "management_report_rows", ["sheet_name"]
    )

    op.create_table(
        "organization_units",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("unit_type", sa.String(length=64), nullable=False, server_default="department"),
        sa.Column("code", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source_import_id", sa.String(length=40), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_import_id"], ["management_report_imports.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("unit_type", "code", name="uq_organization_unit_type_code"),
    )
    op.create_index(op.f("ix_organization_units_code"), "organization_units", ["code"])
    op.create_index(op.f("ix_organization_units_name"), "organization_units", ["name"])
    op.create_index(
        op.f("ix_organization_units_source_import_id"),
        "organization_units",
        ["source_import_id"],
    )
    op.create_index(op.f("ix_organization_units_unit_type"), "organization_units", ["unit_type"])

    op.create_table(
        "management_report_metrics",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("import_id", sa.String(length=40), nullable=False),
        sa.Column("source_row_id", sa.String(length=40), nullable=True),
        sa.Column("sheet_name", sa.String(length=255), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column("dimension_type", sa.String(length=80), nullable=False),
        sa.Column("dimension_code", sa.String(length=120), nullable=True),
        sa.Column("dimension_name", sa.String(length=255), nullable=False),
        sa.Column("metric_name", sa.String(length=120), nullable=False),
        sa.Column("metric_year", sa.Integer(), nullable=True),
        sa.Column("metric_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("metric_unit", sa.String(length=32), nullable=False, server_default="rub"),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"], ["management_report_imports.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_row_id"],
            ["management_report_rows.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_management_report_metrics_dimension_code"),
        "management_report_metrics",
        ["dimension_code"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_dimension_name"),
        "management_report_metrics",
        ["dimension_name"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_dimension_type"),
        "management_report_metrics",
        ["dimension_type"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_import_id"),
        "management_report_metrics",
        ["import_id"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_metric_name"),
        "management_report_metrics",
        ["metric_name"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_metric_year"),
        "management_report_metrics",
        ["metric_year"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_sheet_name"),
        "management_report_metrics",
        ["sheet_name"],
    )
    op.create_index(
        op.f("ix_management_report_metrics_source_row_id"),
        "management_report_metrics",
        ["source_row_id"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_management_report_metrics_source_row_id"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_sheet_name"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_metric_year"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_metric_name"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_import_id"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_dimension_type"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_dimension_name"),
        table_name="management_report_metrics",
    )
    op.drop_index(
        op.f("ix_management_report_metrics_dimension_code"),
        table_name="management_report_metrics",
    )
    op.drop_table("management_report_metrics")

    op.drop_index(op.f("ix_organization_units_unit_type"), table_name="organization_units")
    op.drop_index(op.f("ix_organization_units_source_import_id"), table_name="organization_units")
    op.drop_index(op.f("ix_organization_units_name"), table_name="organization_units")
    op.drop_index(op.f("ix_organization_units_code"), table_name="organization_units")
    op.drop_table("organization_units")

    op.drop_index(op.f("ix_management_report_rows_sheet_name"), table_name="management_report_rows")
    op.drop_index(op.f("ix_management_report_rows_import_id"), table_name="management_report_rows")
    op.drop_table("management_report_rows")

    op.drop_index(
        op.f("ix_management_report_imports_report_year"),
        table_name="management_report_imports",
    )
    op.drop_index(
        op.f("ix_management_report_imports_checksum"),
        table_name="management_report_imports",
    )
    op.drop_table("management_report_imports")
