from alembic import op
import sqlalchemy as sa
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

article_tags = sa.table(
    "articles__tag_model",
    sa.column("deleted_at", UTCDateTime(timezone=True)),
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.delete(article_tags).where(article_tags.c.deleted_at.is_not(None)),
    )
    op.drop_index(
        op.f("articles_tag_active_name_en_id_idx"),
        table_name="articles__tag_model",
    )
    op.drop_index(
        op.f("articles_tag_active_name_ru_id_idx"),
        table_name="articles__tag_model",
    )
    op.drop_column("articles__tag_model", "deleted_at")


def downgrade() -> None:
    op.add_column(
        "articles__tag_model",
        sa.Column(
            "deleted_at", UTCDateTime(timezone=True), autoincrement=False, nullable=True
        ),
    )
    op.create_index(
        op.f("articles_tag_active_name_ru_id_idx"),
        "articles__tag_model",
        [sa.func.lower(sa.column("name_ru")).label("active_name_ru_lower"), "id"],
        unique=False,
        postgresql_where=sa.column("deleted_at").is_(None),
        postgresql_include=["name_ru", "name_en", "slug", "deleted_at", "created_at", "updated_at"],
    )
    op.create_index(
        op.f("articles_tag_active_name_en_id_idx"),
        "articles__tag_model",
        [sa.func.lower(sa.column("name_en")).label("active_name_en_lower"), "id"],
        unique=False,
        postgresql_where=sa.column("deleted_at").is_(None),
        postgresql_include=["name_ru", "name_en", "slug", "deleted_at", "created_at", "updated_at"],
    )
