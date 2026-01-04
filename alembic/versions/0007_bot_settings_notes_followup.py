"""bot settings notes and followups

Revision ID: 0007_bot_settings_notes_followup
Revises: 0006_conversation_state_behavior_followups
Create Date: 2026-01-04 18:30:00
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_bot_settings_notes_followup"
down_revision = "0006_conversation_state_behavior_followups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bot_settings", sa.Column("admin_notes", sa.Text()))
    op.add_column("bot_settings", sa.Column("followup_enabled", sa.Boolean()))
    op.add_column("bot_settings", sa.Column("followup_delay_hours", sa.Integer()))
    op.add_column("bot_settings", sa.Column("followup_message", sa.Text()))


def downgrade() -> None:
    op.drop_column("bot_settings", "followup_message")
    op.drop_column("bot_settings", "followup_delay_hours")
    op.drop_column("bot_settings", "followup_enabled")
    op.drop_column("bot_settings", "admin_notes")
