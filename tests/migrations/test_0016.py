from typing import cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

PERSON_DETAILS_TABLE = "knowledge__person_details_model"
BIRTHDAY_INDEX = "person_details_author_birthday_item_idx"


async def person_index_columns(engine: AsyncEngine) -> dict[str, list[str]]:
    async with engine.connect() as connection:
        indexes = await connection.run_sync(
            lambda sync_connection: sa.inspect(sync_connection).get_indexes(
                PERSON_DETAILS_TABLE,
            ),
        )
    return {
        cast("str", index["name"]): cast("list[str]", index["column_names"]) for index in indexes
    }


class TestMigration0016:
    async def test_upgrade_adds_author_scoped_birthday_calendar_index(
        self,
        engine: AsyncEngine,
        migrated_to_0015: None,
    ) -> None:
        _ = migrated_to_0015

        migrate(revision="0016")

        assert (await person_index_columns(engine))[BIRTHDAY_INDEX] == [
            "author_username",
            "birthday_month",
            "birthday_day",
            "item_id",
        ]

    async def test_downgrade_removes_birthday_calendar_index(
        self,
        engine: AsyncEngine,
        migrated_to_0015: None,
    ) -> None:
        _ = migrated_to_0015
        migrate(revision="0016")

        downgrade(revision="0015")

        assert BIRTHDAY_INDEX not in await person_index_columns(engine)
