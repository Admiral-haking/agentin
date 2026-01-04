"""conversation state, behavior profiles, support tickets, followups

Revision ID: 0006_conv_state_followups
Revises: 0005_perf_indexes
Create Date: 2026-01-04 18:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_conv_state_followups"
down_revision = "0005_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_vip", sa.Boolean(), server_default=sa.text("false")),
    )
    op.add_column(
        "users",
        sa.Column("vip_score", sa.Integer(), server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("followup_opt_out", sa.Boolean(), server_default=sa.text("false")),
    )

    op.create_table(
        "conversation_states",
        sa.Column(
            "conversation_id",
            sa.Integer(),
            sa.ForeignKey("conversations.id"),
            primary_key=True,
        ),
        sa.Column("current_intent", sa.String(length=32)),
        sa.Column("current_category", sa.String(length=32)),
        sa.Column("required_slots", postgresql.JSONB()),
        sa.Column("filled_slots", postgresql.JSONB()),
        sa.Column("last_user_question", sa.String(length=500)),
        sa.Column("last_bot_action", sa.String(length=64)),
        sa.Column("last_bot_answers", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "user_behavior_profiles",
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("last_pattern", sa.String(length=64)),
        sa.Column("confidence", sa.Float()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("pattern_history", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "behavior_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column(
            "conversation_id", sa.Integer(), sa.ForeignKey("conversations.id")
        ),
        sa.Column("pattern", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("reason", sa.String(length=255)),
        sa.Column("keywords", postgresql.JSONB()),
        sa.Column("tags", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column(
            "conversation_id", sa.Integer(), sa.ForeignKey("conversations.id")
        ),
        sa.Column("status", sa.String(length=20), server_default="open"),
        sa.Column("summary", sa.Text()),
        sa.Column("last_message", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_table(
        "followup_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column(
            "conversation_id", sa.Integer(), sa.ForeignKey("conversations.id")
        ),
        sa.Column("status", sa.String(length=20), server_default="scheduled"),
        sa.Column(
            "scheduled_for", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(length=100)),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_conversation_states_updated_at",
        "conversation_states",
        ["updated_at"],
    )
    op.create_index(
        "ix_user_behavior_profiles_updated_at",
        "user_behavior_profiles",
        ["updated_at"],
    )
    op.create_index(
        "ix_behavior_events_user_id_created_at",
        "behavior_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_behavior_events_conversation_id_created_at",
        "behavior_events",
        ["conversation_id", "created_at"],
    )
    op.create_index(
        "ix_support_tickets_status_created_at",
        "support_tickets",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_followup_tasks_status_scheduled_for",
        "followup_tasks",
        ["status", "scheduled_for"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_followup_tasks_status_scheduled_for", table_name="followup_tasks"
    )
    op.drop_index(
        "ix_support_tickets_status_created_at", table_name="support_tickets"
    )
    op.drop_index(
        "ix_behavior_events_conversation_id_created_at",
        table_name="behavior_events",
    )
    op.drop_index(
        "ix_behavior_events_user_id_created_at", table_name="behavior_events"
    )
    op.drop_index(
        "ix_user_behavior_profiles_updated_at",
        table_name="user_behavior_profiles",
    )
    op.drop_index(
        "ix_conversation_states_updated_at",
        table_name="conversation_states",
    )
    op.drop_table("followup_tasks")
    op.drop_table("support_tickets")
    op.drop_table("behavior_events")
    op.drop_table("user_behavior_profiles")
    op.drop_table("conversation_states")

    op.drop_column("users", "followup_opt_out")
    op.drop_column("users", "vip_score")
    op.drop_column("users", "is_vip")
