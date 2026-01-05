"""add handler tracking and loop counter to conversation_states

Revision ID: 0009_state_loop
Revises: 0008_state_machine
Create Date: 2026-01-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_state_loop"
down_revision = "0008_state_machine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE conversation_states "
        "ADD COLUMN IF NOT EXISTS last_handler_used VARCHAR(64)"
    )
    op.execute(
        "ALTER TABLE conversation_states "
        "ADD COLUMN IF NOT EXISTS loop_counter INTEGER DEFAULT 0"
    )


def downgrade() -> None:
    op.drop_column("conversation_states", "loop_counter")
    op.drop_column("conversation_states", "last_handler_used")
