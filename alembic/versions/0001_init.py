"""init

Revision ID: 0001_init
Revises: 
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=255)),
        sa.Column("follow_status", sa.String(length=50)),
        sa.Column("follower_count", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_external_id", "users", ["external_id"], unique=True)

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_user_message_at", sa.DateTime(timezone=True)),
        sa.Column("last_bot_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversations.id"), index=True),
        sa.Column("role", sa.Text()),
        sa.Column("type", sa.Text()),
        sa.Column("content_text", sa.Text()),
        sa.Column("media_url", sa.Text()),
        sa.Column("payload_json", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "bot_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ai_mode", sa.String(length=20)),
        sa.Column("system_prompt", sa.Text()),
        sa.Column("max_history_messages", sa.Integer()),
        sa.Column("max_output_chars", sa.Integer()),
        sa.Column("fallback_text", sa.Text()),
        sa.Column("language", sa.String(length=10)),
        sa.Column("active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=20)),
        sa.Column("tokens_in", sa.Integer()),
        sa.Column("tokens_out", sa.Integer()),
        sa.Column("cost_estimate", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_usage_date", "usage", ["date"], unique=False)

    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=150), unique=True, index=True),
        sa.Column("hashed_password", sa.String(length=255)),
        sa.Column("role", sa.String(length=20)),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "admin_refresh_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id"), index=True),
        sa.Column("token_hash", sa.String(length=255), unique=True, index=True),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("ip", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255)),
        sa.Column("body", sa.Text()),
        sa.Column("discount_code", sa.String(length=100)),
        sa.Column("link", sa.String(length=500)),
        sa.Column("start_at", sa.DateTime(timezone=True)),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean()),
        sa.Column("priority", sa.Integer()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "faqs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question", sa.Text()),
        sa.Column("answer", sa.Text()),
        sa.Column("tags", postgresql.JSONB()),
        sa.Column("verified", sa.Boolean()),
        sa.Column("category", sa.String(length=100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=255)),
        sa.Column("category", sa.String(length=120)),
        sa.Column("price_range", sa.String(length=120)),
        sa.Column("sizes", postgresql.JSONB()),
        sa.Column("colors", postgresql.JSONB()),
        sa.Column("images", postgresql.JSONB()),
        sa.Column("link", sa.Text()),
        sa.Column("in_stock", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id")),
        sa.Column("entity", sa.String(length=100)),
        sa.Column("action", sa.String(length=20)),
        sa.Column("before_json", postgresql.JSONB()),
        sa.Column("after_json", postgresql.JSONB()),
        sa.Column("ip", sa.String(length=64)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "app_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("level", sa.String(length=20)),
        sa.Column("event_type", sa.String(length=100)),
        sa.Column("message", sa.Text()),
        sa.Column("data", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("app_logs")
    op.drop_table("audit_logs")
    op.drop_table("products")
    op.drop_table("faqs")
    op.drop_table("campaigns")
    op.drop_table("admin_refresh_tokens")
    op.drop_table("admin_users")
    op.drop_index("ix_usage_date", table_name="usage")
    op.drop_table("usage")
    op.drop_table("bot_settings")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_users_external_id", table_name="users")
    op.drop_table("users")
