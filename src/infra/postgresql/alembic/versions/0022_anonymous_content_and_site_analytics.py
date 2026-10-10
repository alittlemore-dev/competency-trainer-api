from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "articles_daily_analytics_date_idx",
        "articles__article_daily_analytics_model",
        ["date", "article_id"],
        unique=False,
    )
    op.create_table(
        "analytics__analytics_daily_model",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("ARTICLES", "MATRIX", "SITE", "SUGGESTIONS", name="analytics_kind_enum"),
            nullable=False,
        ),
        sa.Column("target_id", sa.String(length=255), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM(
                "DIRECT",
                "INTERNAL",
                "SEARCH",
                "SOCIAL",
                "EXTERNAL",
                "UNKNOWN",
                name="article_view_source_category_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("engaged", sa.Integer(), nullable=False),
        sa.Column("reactions", sa.Integer(), nullable=False),
        sa.Column("suggestions", sa.Integer(), nullable=False),
        sa.Column("visitors", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.text("replace(CAST(gen_random_uuid() AS VARCHAR), '-', '')"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "kind", "target_id", "source", name="analytics_daily_uniq"),
    )
    op.create_index(
        "analytics_daily_kind_date_idx",
        "analytics__analytics_daily_model",
        ["kind", "date"],
        unique=False,
    )
    op.create_table(
        "analytics__analytics_receipt_model",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("scope", sa.String(length=300), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM(
                "DIRECT",
                "INTERNAL",
                "SEARCH",
                "SOCIAL",
                "EXTERNAL",
                "UNKNOWN",
                name="article_view_source_category_enum",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("engaged", sa.Boolean(), nullable=False),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.text("replace(CAST(gen_random_uuid() AS VARCHAR), '-', '')"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("date", "scope", "digest", name="analytics_receipt_uniq"),
    )


def downgrade() -> None:
    op.drop_index("articles_daily_analytics_date_idx", table_name="articles__article_daily_analytics_model")
    op.drop_table("analytics__analytics_receipt_model")
    op.drop_index("analytics_daily_kind_date_idx", table_name="analytics__analytics_daily_model")
    op.drop_table("analytics__analytics_daily_model")
    sa.Enum(name="analytics_kind_enum").drop(op.get_bind(), checkfirst=False)
