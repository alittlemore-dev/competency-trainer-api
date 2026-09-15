import re
import unicodedata
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


ARTICLES = "articles__article_model"
ARTICLE_FOLDERS = "articles__article_folder_model"
ARTICLE_FOLDER_FK = "articles_article_folder_id_fkey"

articles = sa.table(
    ARTICLES,
    sa.column("id", sa.String(length=32)),
    sa.column("folder_ru", sa.String(length=255)),
    sa.column("folder_en", sa.String(length=255)),
    sa.column("folder_id", sa.String(length=32)),
)
article_folders = sa.table(
    ARTICLE_FOLDERS,
    sa.column("id", sa.String(length=32)),
    sa.column("key", sa.String(length=255)),
    sa.column("name_ru", sa.String(length=255)),
    sa.column("name_en", sa.String(length=255)),
    sa.column("priority", sa.Integer()),
)
published_article_condition = sa.column("publish_status") == sa.literal("PUBLISHED")


def upgrade() -> None:
    connection = op.get_bind()
    op.create_table(
        ARTICLE_FOLDERS,
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("name_ru", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column(
            "id",
            sa.String(length=32),
            server_default=sa.func.replace(
                sa.cast(sa.func.gen_random_uuid(), sa.String()),
                "-",
                "",
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "articles_folder_name_en_idx",
        ARTICLE_FOLDERS,
        [sa.func.lower(sa.column("name_en")).label("folder_name_en_lower"), "id"],
        unique=False,
    )
    op.create_index(
        "articles_folder_name_ru_idx",
        ARTICLE_FOLDERS,
        [sa.func.lower(sa.column("name_ru")).label("folder_name_ru_lower"), "id"],
        unique=False,
    )
    op.create_index(
        "articles_folder_priority_id_idx",
        ARTICLE_FOLDERS,
        ["priority", "id"],
        unique=False,
    )
    op.create_index(
        "articles_folder_key_lower_uniq",
        ARTICLE_FOLDERS,
        [sa.func.lower(sa.column("key")).label("folder_key_lower")],
        unique=True,
    )
    op.add_column(ARTICLES, sa.Column("folder_id", sa.String(length=32), nullable=True))

    folder_rows = _article_folder_rows(connection=connection)
    if folder_rows:
        connection.execute(article_folders.insert(), folder_rows)
        for folder_row in folder_rows:
            connection.execute(
                articles.update()
                .where(
                    articles.c.folder_ru == folder_row["name_ru"],
                    articles.c.folder_en == folder_row["name_en"],
                )
                .values(folder_id=folder_row["id"]),
            )

    op.alter_column(ARTICLES, "folder_id", existing_type=sa.String(length=32), nullable=False)
    op.drop_index(
        op.f("articles_article_tree_en_published_idx"),
        table_name=ARTICLES,
        postgresql_where=published_article_condition,
        postgresql_include=("slug", "publish_status"),
    )
    op.drop_index(
        op.f("articles_article_tree_ru_published_idx"),
        table_name=ARTICLES,
        postgresql_where=published_article_condition,
        postgresql_include=("slug", "publish_status"),
    )
    op.create_index(
        "articles_article_tree_folder_ru_published_idx",
        ARTICLES,
        [
            "folder_id",
            sa.column("published_at").desc().nullslast(),
            sa.column("updated_at").desc(),
            "title_ru",
        ],
        unique=False,
        postgresql_include=("slug", "publish_status"),
        postgresql_where=published_article_condition,
    )
    op.create_index(
        "articles_article_tree_folder_en_published_idx",
        ARTICLES,
        [
            "folder_id",
            sa.column("published_at").desc().nullslast(),
            sa.column("updated_at").desc(),
            "title_en",
        ],
        unique=False,
        postgresql_include=("slug", "publish_status"),
        postgresql_where=published_article_condition,
    )
    op.create_foreign_key(
        ARTICLE_FOLDER_FK,
        ARTICLES,
        ARTICLE_FOLDERS,
        ["folder_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column(ARTICLES, "folder_ru")
    op.drop_column(ARTICLES, "folder_en")


def downgrade() -> None:
    connection = op.get_bind()
    op.add_column(ARTICLES, sa.Column("folder_en", sa.String(length=255), nullable=True))
    op.add_column(ARTICLES, sa.Column("folder_ru", sa.String(length=255), nullable=True))
    connection.execute(
        articles.update()
        .where(articles.c.folder_id == article_folders.c.id)
        .values(
            folder_ru=article_folders.c.name_ru,
            folder_en=article_folders.c.name_en,
        ),
    )
    op.alter_column(ARTICLES, "folder_ru", existing_type=sa.String(length=255), nullable=False)
    op.alter_column(ARTICLES, "folder_en", existing_type=sa.String(length=255), nullable=False)
    op.drop_constraint(ARTICLE_FOLDER_FK, ARTICLES, type_="foreignkey")
    op.drop_index(
        "articles_article_tree_folder_en_published_idx",
        table_name=ARTICLES,
        postgresql_include=("slug", "publish_status"),
        postgresql_where=published_article_condition,
    )
    op.drop_index(
        "articles_article_tree_folder_ru_published_idx",
        table_name=ARTICLES,
        postgresql_include=("slug", "publish_status"),
        postgresql_where=published_article_condition,
    )
    op.create_index(
        op.f("articles_article_tree_ru_published_idx"),
        ARTICLES,
        [
            "folder_ru",
            sa.column("published_at").desc().nullslast(),
            sa.column("updated_at").desc(),
            "title_ru",
        ],
        unique=False,
        postgresql_where=published_article_condition,
        postgresql_include=("slug", "publish_status"),
    )
    op.create_index(
        op.f("articles_article_tree_en_published_idx"),
        ARTICLES,
        [
            "folder_en",
            sa.column("published_at").desc().nullslast(),
            sa.column("updated_at").desc(),
            "title_en",
        ],
        unique=False,
        postgresql_where=published_article_condition,
        postgresql_include=("slug", "publish_status"),
    )
    op.drop_column(ARTICLES, "folder_id")
    op.drop_index("articles_folder_key_lower_uniq", table_name=ARTICLE_FOLDERS)
    op.drop_index("articles_folder_priority_id_idx", table_name=ARTICLE_FOLDERS)
    op.drop_index("articles_folder_name_ru_idx", table_name=ARTICLE_FOLDERS)
    op.drop_index("articles_folder_name_en_idx", table_name=ARTICLE_FOLDERS)
    op.drop_table(ARTICLE_FOLDERS)


def _article_folder_rows(*, connection: Connection) -> list[dict[str, object]]:
    rows = (
        connection.execute(
            sa.select(articles.c.folder_ru, articles.c.folder_en)
            .group_by(articles.c.folder_ru, articles.c.folder_en)
            .order_by(sa.func.lower(articles.c.folder_en), sa.func.lower(articles.c.folder_ru)),
        )
        .mappings()
        .all()
    )
    key_counts: dict[str, int] = {}
    folder_rows: list[dict[str, object]] = []
    for priority, row in enumerate(rows, start=1):
        base_key = _folder_key(value=row["folder_en"])
        key_counts[base_key] = key_counts.get(base_key, 0) + 1
        key = base_key if key_counts[base_key] == 1 else f"{base_key}-{key_counts[base_key]}"
        folder_rows.append(
            {
                "id": _folder_id(name_ru=row["folder_ru"], name_en=row["folder_en"]),
                "key": key,
                "name_ru": row["folder_ru"],
                "name_en": row["folder_en"],
                "priority": priority,
            },
        )
    return folder_rows


def _folder_key(*, value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    key = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return key or "folder"


def _folder_id(*, name_ru: str, name_en: str) -> str:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"article-folder:{name_ru}:{name_en}").hex
