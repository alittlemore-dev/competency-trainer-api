from alembic import op
import sqlalchemy as sa
from sqlalchemy_dev_utils.types.datetime import UTCDateTime


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

FILE_TABLE = "files__file_model"
ARTICLE_TABLE = "articles__article_model"
ARTICLE_FILE_USAGE_TABLE = "articles__article_file_usage_model"
ORPHAN_INDEX = "files_file_namespace_orphaned_id_idx"

files = sa.table(
    FILE_TABLE,
    sa.column("id", sa.String()),
    sa.column("orphaned_at", UTCDateTime(timezone=True)),
)
articles = sa.table(
    ARTICLE_TABLE,
    sa.column("cover_image_file_id", sa.String()),
)
article_file_usages = sa.table(
    ARTICLE_FILE_USAGE_TABLE,
    sa.column("file_id", sa.String()),
)


def upgrade() -> None:
    op.add_column(
        FILE_TABLE,
        sa.Column("orphaned_at", UTCDateTime(timezone=True), nullable=True),
    )
    has_cover_usage = sa.exists().where(articles.c.cover_image_file_id == files.c.id)
    has_content_usage = sa.exists().where(article_file_usages.c.file_id == files.c.id)
    op.get_bind().execute(
        sa.update(files)
        .where(~has_cover_usage, ~has_content_usage)
        .values(orphaned_at=sa.func.timezone("utc", sa.func.current_timestamp())),
    )
    op.create_index(
        ORPHAN_INDEX,
        FILE_TABLE,
        ["namespace", "orphaned_at", "id"],
        unique=False,
        postgresql_where=sa.column("orphaned_at").is_not(None),
    )


def downgrade() -> None:
    op.drop_index(ORPHAN_INDEX, table_name=FILE_TABLE)
    op.drop_column(FILE_TABLE, "orphaned_at")
