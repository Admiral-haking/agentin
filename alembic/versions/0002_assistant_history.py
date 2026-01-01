"""assistant history

Revision ID: 0002_assistant_history
Revises: 0001_init
Create Date: 2025-12-31 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_assistant_history"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id"), index=True),
        sa.Column("title", sa.String(length=255)),
        sa.Column("context", sa.Text()),
        sa.Column("mode", sa.String(length=20)),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_table(
        "assistant_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("assistant_conversations.id"),
            index=True,
        ),
        sa.Column("role", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("provider", sa.String(length=20)),
        sa.Column("usage_json", postgresql.JSONB()),
        sa.Column("truncated", sa.Boolean(), server_default=sa.false()),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "assistant_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("assistant_conversations.id"),
            index=True,
        ),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id"), index=True),
        sa.Column("status", sa.String(length=20)),
        sa.Column("action_type", sa.String(length=50)),
        sa.Column("summary", sa.String(length=255)),
        sa.Column("payload_json", postgresql.JSONB()),
        sa.Column("result_json", postgresql.JSONB()),
        sa.Column("error", sa.Text()),
        sa.Column("approved_by", sa.Integer(), sa.ForeignKey("admin_users.id")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_assistant_actions_status",
        "assistant_actions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_assistant_actions_status", table_name="assistant_actions")
    op.drop_table("assistant_actions")
    op.drop_table("assistant_messages")
    op.drop_table("assistant_conversations")
