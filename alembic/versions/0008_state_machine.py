"""add selected_product and last_user_message_id to conversation_states

Revision ID: 0008_state_machine
Revises: 0007_bot_settings_notes_followup
Create Date: 2026-01-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_state_machine"
down_revision = "0007_bot_settings_notes_followup"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE conversation_states "
        "ADD COLUMN IF NOT EXISTS selected_product JSONB"
    )
    op.execute(
        "ALTER TABLE conversation_states "
        "ADD COLUMN IF NOT EXISTS last_user_message_id INTEGER"
    )


def downgrade() -> None:
    op.drop_column("conversation_states", "last_user_message_id")
    op.drop_column("conversation_states", "selected_product")
