from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import migrate

file_purpose_enum = postgresql.ENUM(
    "ARTICLE_CONTENT_IMAGE",
    "ARTICLE_COVER_IMAGE",
    "ATTACHMENT",
    name="file_purpose_enum",
    create_type=False,
)

old_files = sa.table(
    "files__file_model",
    sa.column("id", sa.String()),
    sa.column("purpose", file_purpose_enum),
    sa.column("namespace", sa.String()),
    sa.column("relative_path", sa.String()),
    sa.column("mime_type", sa.String()),
    sa.column("size_bytes", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column("original_name", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

new_files = sa.table(
    "files__file_model",
    sa.column("id", sa.String()),
    sa.column("purpose", file_purpose_enum),
    sa.column("namespace", sa.String()),
    sa.column("original_sha256", sa.String()),
)


class TestMigration0005:
    async def test_upgrade_adds_nullable_original_sha256_to_existing_files(
        self,
        engine: AsyncEngine,
        migrated_to_0004: None,
    ) -> None:
        _ = migrated_to_0004
        async with engine.begin() as connection:
            await connection.execute(
                old_files.insert().values(
                    id="10000000000050008000000000000001",
                    purpose="ARTICLE_CONTENT_IMAGE",
                    namespace="media",
                    relative_path="article-content-images/existing.png",
                    mime_type="image/png",
                    size_bytes=4,
                    name="Existing image",
                    original_name="existing.png",
                    created_at=datetime(2026, 7, 6, tzinfo=UTC),
                    updated_at=datetime(2026, 7, 6, tzinfo=UTC),
                ),
            )

        migrate(revision="0005")

        async with engine.begin() as connection:
            existing_hash = await connection.scalar(
                sa.select(new_files.c.original_sha256).where(
                    new_files.c.id == "10000000000050008000000000000001",
                ),
            )
            await connection.execute(
                sa.update(new_files)
                .where(new_files.c.id == "10000000000050008000000000000001")
                .values(original_sha256="a" * 64),
            )
            queried_id = await connection.scalar(
                sa.select(new_files.c.id).where(
                    new_files.c.namespace == "media",
                    new_files.c.purpose == "ARTICLE_CONTENT_IMAGE",
                    new_files.c.original_sha256 == "a" * 64,
                ),
            )

        assert existing_hash is None
        assert queried_id == "10000000000050008000000000000001"
