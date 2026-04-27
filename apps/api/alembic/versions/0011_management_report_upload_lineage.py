"""Add upload lineage to management report imports."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0011_mgmt_report_lineage"
down_revision = "0010_sku_cost_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("management_report_imports")}
    if "upload_file_id" not in columns:
        op.add_column(
            "management_report_imports",
            sa.Column("upload_file_id", sa.String(length=40), nullable=True),
        )
        op.create_foreign_key(
            op.f("fk_management_report_imports_upload_file_id_upload_files"),
            "management_report_imports",
            "upload_files",
            ["upload_file_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            op.f("ix_management_report_imports_upload_file_id"),
            "management_report_imports",
            ["upload_file_id"],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("management_report_imports")}
    if "upload_file_id" in columns:
        op.drop_index(
            op.f("ix_management_report_imports_upload_file_id"),
            table_name="management_report_imports",
        )
        op.drop_constraint(
            op.f("fk_management_report_imports_upload_file_id_upload_files"),
            "management_report_imports",
            type_="foreignkey",
        )
        op.drop_column("management_report_imports", "upload_file_id")
