"""performance indexes for admin queries

Revision ID: 0005_perf_indexes
Revises: 0004_product_sync
Create Date: 2026-01-04 12:00:00
"""

from alembic import op

revision = "0005_perf_indexes"
down_revision = "0004_product_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index(
        "ix_messages_conversation_created_at",
        "messages",
        ["conversation_id", "created_at"],
    )
    op.create_index("ix_app_logs_created_at", "app_logs", ["created_at"])
    op.create_index("ix_app_logs_event_type", "app_logs", ["event_type"])
    op.create_index("ix_app_logs_level", "app_logs", ["level"])
    op.create_index("ix_users_updated_at", "users", ["updated_at"])
    op.create_index(
        "ix_conversations_last_user_message_at",
        "conversations",
        ["last_user_message_at"],
    )
    op.create_index(
        "ix_assistant_messages_conversation_created_at",
        "assistant_messages",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_assistant_actions_status_created_at",
        "assistant_actions",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_assistant_actions_status_created_at", table_name="assistant_actions"
    )
    op.drop_index(
        "ix_assistant_messages_conversation_created_at",
        table_name="assistant_messages",
    )
    op.drop_index(
        "ix_conversations_last_user_message_at", table_name="conversations"
    )
    op.drop_index("ix_users_updated_at", table_name="users")
    op.drop_index("ix_app_logs_level", table_name="app_logs")
    op.drop_index("ix_app_logs_event_type", table_name="app_logs")
    op.drop_index("ix_app_logs_created_at", table_name="app_logs")
    op.drop_index(
        "ix_messages_conversation_created_at", table_name="messages"
    )
    op.drop_index("ix_messages_created_at", table_name="messages")
