"""add admin media notes

Revision ID: 0010_admin_media_notes
Revises: 0009_state_loop
Create Date: 2026-01-05
"""
from __future__ import annotations

from alembic import op

revision = "0010_admin_media_notes"
down_revision = "0009_state_loop"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_media_notes (
            id SERIAL PRIMARY KEY,
            conversation_id INTEGER NOT NULL REFERENCES conversations(id),
            message_id INTEGER REFERENCES messages(id),
            media_url TEXT NOT NULL,
            tag VARCHAR(64),
            category VARCHAR(32),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_media_notes_conversation "
        "ON admin_media_notes (conversation_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admin_media_notes_created_at "
        "ON admin_media_notes (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admin_media_notes")
