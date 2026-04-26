"""Add Phase 5 assistant sessions and messages."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0004_assistant_phase5"
down_revision = "0003_reserve_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "assistant_sessions" in inspector.get_table_names():
        return

    op.create_table(
        "assistant_sessions",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("created_by_id", sa.String(length=40), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Новая сессия"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("pinned_context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column(
            "last_intent",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "preferred_mode",
            sa.String(length=32),
            nullable=False,
            server_default="deterministic",
        ),
        sa.Column(
            "provider",
            sa.String(length=64),
            nullable=False,
            server_default="deterministic",
        ),
        sa.Column("latest_trace_id", sa.String(length=64), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistant_sessions_created_by_id"), "assistant_sessions", ["created_by_id"]
    )
    op.create_index(op.f("ix_assistant_sessions_status"), "assistant_sessions", ["status"])

    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("session_id", sa.String(length=40), nullable=False),
        sa.Column("created_by_id", sa.String(length=40), nullable=True),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="completed"),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("context_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("response_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("source_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("tool_calls", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("warnings", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(["session_id"], ["assistant_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_assistant_messages_created_by_id"), "assistant_messages", ["created_by_id"]
    )
    op.create_index(op.f("ix_assistant_messages_role"), "assistant_messages", ["role"])
    op.create_index(op.f("ix_assistant_messages_session_id"), "assistant_messages", ["session_id"])
    op.create_index(op.f("ix_assistant_messages_trace_id"), "assistant_messages", ["trace_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_assistant_messages_trace_id"), table_name="assistant_messages")
    op.drop_index(op.f("ix_assistant_messages_session_id"), table_name="assistant_messages")
    op.drop_index(op.f("ix_assistant_messages_role"), table_name="assistant_messages")
    op.drop_index(op.f("ix_assistant_messages_created_by_id"), table_name="assistant_messages")
    op.drop_table("assistant_messages")

    op.drop_index(op.f("ix_assistant_sessions_status"), table_name="assistant_sessions")
    op.drop_index(op.f("ix_assistant_sessions_created_by_id"), table_name="assistant_sessions")
    op.drop_table("assistant_sessions")
