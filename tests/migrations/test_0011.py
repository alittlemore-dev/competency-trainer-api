from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

tags = sa.table(
    "articles__tag_model",
    sa.column("id", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("deleted_at", sa.DateTime(timezone=True)),
)


class TestMigration0011:
    async def test_upgrade_physically_removes_soft_deleted_tags_and_column(
        self,
        engine: AsyncEngine,
        migrated_to_0010: None,
    ) -> None:
        _ = migrated_to_0010
        active_tag_id = "10000000000040008000000000000001"
        deleted_tag_id = "10000000000040008000000000000002"
        async with engine.begin() as connection:
            await connection.execute(
                tags.insert(),
                [
                    {
                        "id": active_tag_id,
                        "name_ru": "Питон",
                        "name_en": "Python",
                        "slug": "python",
                        "deleted_at": None,
                    },
                    {
                        "id": deleted_tag_id,
                        "name_ru": "Старый",
                        "name_en": "Old",
                        "slug": "old",
                        "deleted_at": datetime(2026, 1, 4, 3, 4, 5, tzinfo=UTC),
                    },
                ],
            )

        migrate(revision="0011")

        async with engine.begin() as connection:
            tag_ids = (await connection.scalars(sa.select(tags.c.id))).all()
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns("articles__tag_model")
                },
            )
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]
                    for index in sa.inspect(sync_connection).get_indexes("articles__tag_model")
                },
            )

        assert tag_ids == [active_tag_id]
        assert "deleted_at" not in columns
        assert "articles_tag_name_ru_id_idx" not in indexes
        assert "articles_tag_name_en_id_idx" not in indexes
        assert "articles_tag_active_name_ru_id_idx" not in indexes
        assert "articles_tag_active_name_en_id_idx" not in indexes

    async def test_downgrade_restores_soft_delete_storage_shape(
        self,
        engine: AsyncEngine,
        migrated_to_0010: None,
    ) -> None:
        _ = migrated_to_0010
        migrate(revision="0011")
        downgrade(revision="0010")

        async with engine.begin() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns("articles__tag_model")
                },
            )
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]
                    for index in sa.inspect(sync_connection).get_indexes("articles__tag_model")
                },
            )

        assert "deleted_at" in columns
        assert "articles_tag_active_name_ru_id_idx" in indexes
        assert "articles_tag_active_name_en_id_idx" in indexes
        assert "articles_tag_name_ru_id_idx" not in indexes
        assert "articles_tag_name_en_id_idx" not in indexes
