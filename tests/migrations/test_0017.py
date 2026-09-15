from datetime import UTC, datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

FILE_TABLE = "files__file_model"
ARTICLE_TABLE = "articles__article_model"
ARTICLE_FOLDER_TABLE = "articles__article_folder_model"
ARTICLE_FILE_USAGE_TABLE = "articles__article_file_usage_model"
ORPHAN_INDEX = "files_file_namespace_orphaned_id_idx"

file_purpose_enum = postgresql.ENUM(
    "ARTICLE_CONTENT_IMAGE",
    "ARTICLE_COVER_IMAGE",
    "ATTACHMENT",
    name="file_purpose_enum",
    create_type=False,
)
publish_status_enum = postgresql.ENUM(
    "DRAFT",
    "PUBLISHED",
    name="publish_status_enum",
    create_type=False,
)
files = sa.table(
    FILE_TABLE,
    sa.column("id", sa.String()),
    sa.column("purpose", file_purpose_enum),
    sa.column("namespace", sa.String()),
    sa.column("relative_path", sa.String()),
    sa.column("mime_type", sa.String()),
    sa.column("size_bytes", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column("original_name", sa.String()),
)
article_folders = sa.table(
    ARTICLE_FOLDER_TABLE,
    sa.column("id", sa.String()),
    sa.column("key", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
articles = sa.table(
    ARTICLE_TABLE,
    sa.column("id", sa.String()),
    sa.column("title_ru", sa.String()),
    sa.column("title_en", sa.String()),
    sa.column("content_ru", sa.String()),
    sa.column("content_en", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("folder_id", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("publish_status", publish_status_enum),
    sa.column("cover_image_file_id", sa.String()),
)
article_file_usages = sa.table(
    ARTICLE_FILE_USAGE_TABLE,
    sa.column("article_id", sa.String()),
    sa.column("file_id", sa.String()),
    sa.column("usage", file_purpose_enum),
)


class TestMigration0017:
    async def test_upgrade_backfills_only_unreferenced_files_and_adds_partial_index(
        self,
        engine: AsyncEngine,
        migrated_to_0016: None,
    ) -> None:
        _ = migrated_to_0016
        cover_id = "17000000000000000000000000000001"
        content_id = "17000000000000000000000000000002"
        orphan_id = "17000000000000000000000000000003"
        folder_id = "17000000000000000000000000000004"
        article_id = "17000000000000000000000000000005"
        async with engine.begin() as connection:
            await connection.execute(
                files.insert(),
                [
                    {
                        "id": cover_id,
                        "purpose": "ARTICLE_COVER_IMAGE",
                        "namespace": "media",
                        "relative_path": "covers/used.png",
                        "mime_type": "image/png",
                        "size_bytes": 1,
                        "name": "Used cover",
                        "original_name": "used.png",
                    },
                    {
                        "id": content_id,
                        "purpose": "ARTICLE_CONTENT_IMAGE",
                        "namespace": "media",
                        "relative_path": "content/used.png",
                        "mime_type": "image/png",
                        "size_bytes": 1,
                        "name": "Used content",
                        "original_name": "used.png",
                    },
                    {
                        "id": orphan_id,
                        "purpose": "ATTACHMENT",
                        "namespace": "media",
                        "relative_path": "attachments/orphan.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 1,
                        "name": "Orphan",
                        "original_name": "orphan.pdf",
                    },
                ],
            )
            await connection.execute(
                article_folders.insert().values(
                    id=folder_id,
                    key="migration-0017",
                    name_ru="Миграция",
                    name_en="Migration",
                    priority=17,
                ),
            )
            await connection.execute(
                articles.insert().values(
                    id=article_id,
                    title_ru="Статья",
                    title_en="Article",
                    content_ru="Содержимое",
                    content_en="Content",
                    slug="migration-0017",
                    folder_id=folder_id,
                    author_username="owner",
                    publish_status="DRAFT",
                    cover_image_file_id=cover_id,
                ),
            )
            await connection.execute(
                article_file_usages.insert().values(
                    article_id=article_id,
                    file_id=content_id,
                    usage="ARTICLE_CONTENT_IMAGE",
                ),
            )
        started_at = datetime.now(tz=UTC)

        migrate(revision="0017")

        async with engine.connect() as connection:
            result: CursorResult[Any] = await connection.execute(
                sa.select(
                    sa.column("id"),
                    sa.column("orphaned_at"),
                ).select_from(sa.table(FILE_TABLE)),
            )
            rows: dict[str, datetime | None] = {
                cast("str", row.id): cast("datetime | None", row.orphaned_at) for row in result
            }
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    cast("str", index["name"]): cast("dict[str, Any]", index)
                    for index in sa.inspect(sync_connection).get_indexes(FILE_TABLE)
                },
            )

        assert rows[cover_id] is None
        assert rows[content_id] is None
        orphaned_at = rows[orphan_id]
        assert orphaned_at is not None
        assert orphaned_at >= started_at
        assert indexes[ORPHAN_INDEX]["column_names"] == ["namespace", "orphaned_at", "id"]
        assert indexes[ORPHAN_INDEX]["dialect_options"]["postgresql_where"] is not None

    async def test_downgrade_removes_orphan_lifecycle_schema(
        self,
        engine: AsyncEngine,
        migrated_to_0016: None,
    ) -> None:
        _ = migrated_to_0016
        migrate(revision="0017")

        downgrade(revision="0016")

        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"] for column in sa.inspect(sync_connection).get_columns(FILE_TABLE)
                },
            )
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"] for index in sa.inspect(sync_connection).get_indexes(FILE_TABLE)
                },
            )
        assert "orphaned_at" not in columns
        assert ORPHAN_INDEX not in indexes
