"""user profile json

Revision ID: 0003_user_profile_json
Revises: 0002_assistant_history
Create Date: 2025-12-31 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_user_profile_json"
down_revision = "0002_assistant_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_json", postgresql.JSONB()))


def downgrade() -> None:
    op.drop_column("users", "profile_json")
