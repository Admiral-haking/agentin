"""product sync tables and fields

Revision ID: 0004_product_sync
Revises: 0003_user_profile_json
Create Date: 2026-01-02 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_product_sync"
down_revision = "0003_user_profile_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    availability_enum = sa.Enum(
        "instock", "outofstock", "unknown", name="product_availability"
    )
    availability_enum.create(op.get_bind(), checkfirst=True)

    op.add_column("products", sa.Column("product_id", sa.String(length=64)))
    op.add_column("products", sa.Column("slug", sa.String(length=255)))
    op.add_column("products", sa.Column("page_url", sa.Text()))
    op.add_column("products", sa.Column("description", sa.Text()))
    op.add_column("products", sa.Column("price", sa.Integer()))
    op.add_column("products", sa.Column("old_price", sa.Integer()))
    op.add_column(
        "products",
        sa.Column(
            "availability",
            availability_enum,
            server_default=sa.text("'unknown'"),
        ),
    )
    op.add_column("products", sa.Column("lastmod", sa.DateTime(timezone=True)))
    op.add_column(
        "products",
        sa.Column(
            "source_flags",
            postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
        ),
    )

    op.alter_column(
        "products",
        "title",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.execute(
        "UPDATE products SET page_url = link WHERE page_url IS NULL AND link IS NOT NULL"
    )
    op.execute(
        "UPDATE products SET availability = 'instock' "
        "WHERE availability IS NULL AND in_stock IS TRUE"
    )
    op.execute(
        "UPDATE products SET availability = 'outofstock' "
        "WHERE availability IS NULL AND in_stock IS FALSE"
    )
    op.execute(
        "UPDATE products SET availability = 'unknown' WHERE availability IS NULL"
    )
    op.execute(
        "UPDATE products SET source_flags = '{}'::jsonb WHERE source_flags IS NULL"
    )

    op.create_index("ix_products_page_url", "products", ["page_url"], unique=True)
    op.create_index("ix_products_product_id", "products", ["product_id"], unique=True)
    op.create_index("ix_products_slug", "products", ["slug"])
    op.create_index("ix_products_updated_at", "products", ["updated_at"])
    op.create_index(
        "ix_products_availability_updated_at",
        "products",
        ["availability", "updated_at"],
    )

    op.create_table(
        "product_sync_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("torob_count", sa.Integer()),
        sa.Column("sitemap_count", sa.Integer()),
        sa.Column("created_count", sa.Integer()),
        sa.Column("updated_count", sa.Integer()),
        sa.Column("unchanged_count", sa.Integer()),
        sa.Column("error_count", sa.Integer()),
        sa.Column("error_message", sa.Text()),
    )
    op.create_index(
        "ix_product_sync_runs_started_at",
        "product_sync_runs",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_product_sync_runs_started_at", table_name="product_sync_runs")
    op.drop_table("product_sync_runs")

    op.drop_index("ix_products_availability_updated_at", table_name="products")
    op.drop_index("ix_products_updated_at", table_name="products")
    op.drop_index("ix_products_slug", table_name="products")
    op.drop_index("ix_products_product_id", table_name="products")
    op.drop_index("ix_products_page_url", table_name="products")

    op.drop_column("products", "source_flags")
    op.drop_column("products", "lastmod")
    op.drop_column("products", "availability")
    op.drop_column("products", "old_price")
    op.drop_column("products", "price")
    op.drop_column("products", "description")
    op.drop_column("products", "page_url")
    op.drop_column("products", "slug")
    op.drop_column("products", "product_id")

    availability_enum = sa.Enum(
        "instock", "outofstock", "unknown", name="product_availability"
    )
    availability_enum.drop(op.get_bind(), checkfirst=True)
