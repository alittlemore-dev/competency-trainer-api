from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

publish_status_enum = postgresql.ENUM(
    "DRAFT",
    "PUBLISHED",
    name="publish_status_enum",
    create_type=False,
)

old_articles = sa.table(
    "articles__article_model",
    sa.column("id", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("title_ru", sa.String()),
    sa.column("title_en", sa.String()),
    sa.column("content_ru", sa.String()),
    sa.column("content_en", sa.String()),
    sa.column("folder_ru", sa.String()),
    sa.column("folder_en", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("publish_status", publish_status_enum),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

new_articles = sa.table(
    "articles__article_model",
    sa.column("id", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("folder_id", sa.String()),
)

article_folders = sa.table(
    "articles__article_folder_model",
    sa.column("id", sa.String()),
    sa.column("key", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)


class TestMigration0003:
    async def test_upgrade_normalizes_article_folders_and_backfills_articles(
        self,
        engine: AsyncEngine,
        migrated_to_0002: None,
    ) -> None:
        _ = migrated_to_0002
        async with engine.begin() as connection:
            await connection.execute(
                old_articles.insert(),
                [
                    article_row(
                        article_id="10000000000040008000000000000001",
                        slug="database-a",
                        folder_ru="База",
                        folder_en="Database",
                    ),
                    article_row(
                        article_id="10000000000040008000000000000002",
                        slug="database-b",
                        folder_ru="Базы",
                        folder_en="Database",
                    ),
                    article_row(
                        article_id="10000000000040008000000000000003",
                        slug="architecture",
                        folder_ru="Архитектура",
                        folder_en="Architecture",
                    ),
                ],
            )

        migrate(revision="0003")

        async with engine.connect() as connection:
            folder_rows = (
                (
                    await connection.execute(
                        sa.select(
                            article_folders.c.id,
                            article_folders.c.key,
                            article_folders.c.name_ru,
                            article_folders.c.name_en,
                            article_folders.c.priority,
                        ).order_by(article_folders.c.priority),
                    )
                )
                .mappings()
                .all()
            )
            article_rows = (
                (
                    await connection.execute(
                        sa.select(new_articles.c.slug, new_articles.c.folder_id).order_by(
                            new_articles.c.slug,
                        ),
                    )
                )
                .mappings()
                .all()
            )

        assert [
            (row["key"], row["name_ru"], row["name_en"], row["priority"]) for row in folder_rows
        ] == [
            ("architecture", "Архитектура", "Architecture", 1),
            ("database", "База", "Database", 2),
            ("database-2", "Базы", "Database", 3),
        ]
        folder_id_by_key = {row["key"]: row["id"] for row in folder_rows}
        assert [(row["slug"], row["folder_id"]) for row in article_rows] == [
            ("architecture", folder_id_by_key["architecture"]),
            ("database-a", folder_id_by_key["database"]),
            ("database-b", folder_id_by_key["database-2"]),
        ]

    async def test_downgrade_restores_article_folder_columns_from_folder_rows(
        self,
        engine: AsyncEngine,
        migrated_to_0002: None,
    ) -> None:
        _ = migrated_to_0002
        async with engine.begin() as connection:
            await connection.execute(
                old_articles.insert().values(
                    article_row(
                        article_id="10000000000040008000000000000001",
                        slug="database-a",
                        folder_ru="База",
                        folder_en="Database",
                    ),
                ),
            )

        migrate(revision="0003")
        downgrade(revision="0002")

        async with engine.connect() as connection:
            row = (
                (
                    await connection.execute(
                        sa.select(
                            old_articles.c.slug,
                            old_articles.c.folder_ru,
                            old_articles.c.folder_en,
                        ),
                    )
                )
                .mappings()
                .one()
            )

        assert row == {
            "slug": "database-a",
            "folder_ru": "База",
            "folder_en": "Database",
        }


def article_row(
    *,
    article_id: str,
    slug: str,
    folder_ru: str,
    folder_en: str,
) -> dict[str, object]:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return {
        "id": article_id,
        "slug": slug,
        "title_ru": slug,
        "title_en": slug,
        "content_ru": slug,
        "content_en": slug,
        "folder_ru": folder_ru,
        "folder_en": folder_en,
        "author_username": "admin",
        "publish_status": "PUBLISHED",
        "created_at": now,
        "updated_at": now,
    }
