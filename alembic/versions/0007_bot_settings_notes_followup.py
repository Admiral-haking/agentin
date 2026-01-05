"""bot settings notes and followups

Revision ID: 0007_bot_settings_notes_followup
Revises: 0006_conv_state_followups
Create Date: 2026-01-04 18:30:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_bot_settings_notes_followup"
down_revision = "0006_conv_state_followups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS admin_notes TEXT")
    op.execute(
        "ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS followup_enabled BOOLEAN"
    )
    op.execute(
        "ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS followup_delay_hours INTEGER"
    )
    op.execute("ALTER TABLE bot_settings ADD COLUMN IF NOT EXISTS followup_message TEXT")


def downgrade() -> None:
    op.drop_column("bot_settings", "followup_message")
    op.drop_column("bot_settings", "followup_delay_hours")
    op.drop_column("bot_settings", "followup_enabled")
    op.drop_column("bot_settings", "admin_notes")
