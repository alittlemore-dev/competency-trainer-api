from datetime import date
from typing import cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql.base import PGInspector
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

DAILY = "analytics__analytics_daily_model"
RECEIPTS = "analytics__analytics_receipt_model"


async def test_analytics_upgrade_and_downgrade_preserve_shared_source_enum(
    engine: AsyncEngine,
    migrated_to_0021: None,
) -> None:
    _ = migrated_to_0021
    migrate(revision="0022")
    async with engine.begin() as connection:
        metadata = sa.MetaData()
        await connection.run_sync(metadata.reflect)
        await connection.execute(
            metadata.tables[DAILY]
            .insert()
            .values(
                id="00000000000040008000000000000001",
                date=date(2026, 1, 1),
                kind="SITE",
                target_id="articles",
                source="DIRECT",
                views=1,
                engaged=0,
                reactions=0,
                suggestions=0,
                visitors=0,
            )
        )
        await connection.execute(
            metadata.tables[RECEIPTS]
            .insert()
            .values(
                id="00000000000040008000000000000002",
                date=date(2026, 1, 1),
                scope="Site:articles",
                digest="a" * 64,
                source="DIRECT",
                engaged=False,
            )
        )
        assert await connection.scalar(sa.select(sa.func.sum(metadata.tables[DAILY].c.views))) == 1
    downgrade(revision="0021")
    async with engine.connect() as connection:
        tables = set(await connection.run_sync(lambda conn: sa.inspect(conn).get_table_names()))
        enums = set(
            await connection.run_sync(
                lambda conn: [
                    enum["name"] for enum in cast("PGInspector", sa.inspect(conn)).get_enums()
                ]
            )
        )
        assert DAILY not in tables
        assert RECEIPTS not in tables
        assert "analytics_kind_enum" not in enums
        assert "article_view_source_category_enum" in enums
    migrate(revision="0022")
