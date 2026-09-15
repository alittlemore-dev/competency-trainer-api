from typing import Protocol, TypedDict, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate
from tests.migrations.test_0014 import get_owner_username

ITEM_TABLE = "knowledge__knowledge_item_model"
PERSON_DETAILS_TABLE = "knowledge__person_details_model"
DATE_DETAILS_TABLE = "knowledge__date_details_model"
DATE_PERSON_TABLE = "knowledge__date_person_model"
KNOWLEDGE_ENUM = "knowledge_item_kind_enum"


class ReflectedEnum(TypedDict):
    name: str
    labels: list[str]


class PostgreSQLInspector(Protocol):
    def get_enums(self) -> list[ReflectedEnum]: ...


person_only_enum = postgresql.ENUM(
    "PERSON",
    name=KNOWLEDGE_ENUM,
    create_type=False,
)
date_and_person_enum = postgresql.ENUM(
    "DATE",
    "PERSON",
    name=KNOWLEDGE_ENUM,
    create_type=False,
)
items_before_upgrade = sa.table(
    ITEM_TABLE,
    sa.column("id", sa.String()),
    sa.column("kind", person_only_enum),
    sa.column("author_username", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("description", sa.Text()),
)
items_after_upgrade = sa.table(
    ITEM_TABLE,
    sa.column("id", sa.String()),
    sa.column("kind", date_and_person_enum),
    sa.column("author_username", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("description", sa.Text()),
)
person_details = sa.table(
    PERSON_DETAILS_TABLE,
    sa.column("item_id", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("last_name", sa.String()),
    sa.column("first_name", sa.String()),
    sa.column("middle_name", sa.String()),
    sa.column("email", sa.String()),
    sa.column("phone", sa.String()),
    sa.column("telegram", sa.String()),
    sa.column("birthday_day", sa.Integer()),
    sa.column("birthday_month", sa.Integer()),
    sa.column("birthday_year", sa.Integer()),
)
date_details = sa.table(
    DATE_DETAILS_TABLE,
    sa.column("item_id", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("day", sa.Integer()),
    sa.column("month", sa.Integer()),
    sa.column("year", sa.Integer()),
)
date_people = sa.table(
    DATE_PERSON_TABLE,
    sa.column("date_item_id", sa.String()),
    sa.column("person_item_id", sa.String()),
    sa.column("author_username", sa.String()),
)


async def get_enum_labels(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as connection:
        enums = await connection.run_sync(
            lambda sync_connection: {
                enum["name"]: enum["labels"]
                for enum in cast(
                    "PostgreSQLInspector",
                    sa.inspect(sync_connection),
                ).get_enums()
            },
        )
    return enums[KNOWLEDGE_ENUM]


class TestMigration0015:
    async def test_upgrade_preserves_people_and_adds_dates(
        self,
        engine: AsyncEngine,
        migrated_to_0014: None,
    ) -> None:
        _ = migrated_to_0014
        owner_username = await get_owner_username(engine)
        person_id = "15000000000040008000000000000001"
        date_id = "15000000000040008000000000000002"

        async with engine.begin() as connection:
            await connection.execute(
                items_before_upgrade.insert().values(
                    id=person_id,
                    kind="PERSON",
                    author_username=owner_username,
                    display_name="Иван Иванов",
                    description="",
                ),
            )
            await connection.execute(
                person_details.insert().values(
                    item_id=person_id,
                    author_username=owner_username,
                    last_name="Иванов",
                    first_name="Иван",
                    middle_name="",
                    email="",
                    phone="",
                    telegram="",
                    birthday_day=None,
                    birthday_month=None,
                    birthday_year=None,
                ),
            )

        migrate(revision="0015")

        async with engine.begin() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names()),
            )
            item_indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"] for index in sa.inspect(sync_connection).get_indexes(ITEM_TABLE)
                },
            )
            person = (
                await connection.execute(
                    sa.select(items_after_upgrade.c.kind, items_after_upgrade.c.display_name).where(
                        items_after_upgrade.c.id == person_id,
                    ),
                )
            ).one()
            await connection.execute(
                items_after_upgrade.insert().values(
                    id=date_id,
                    kind="DATE",
                    author_username=owner_username,
                    display_name="Годовщина",
                    description="",
                ),
            )
            await connection.execute(
                date_details.insert().values(
                    item_id=date_id,
                    author_username=owner_username,
                    day=29,
                    month=2,
                    year=None,
                ),
            )
            await connection.execute(
                date_people.insert().values(
                    date_item_id=date_id,
                    person_item_id=person_id,
                    author_username=owner_username,
                ),
            )

        assert await get_enum_labels(engine) == ["DATE", "PERSON"]
        assert {DATE_DETAILS_TABLE, DATE_PERSON_TABLE}.issubset(table_names)
        assert "knowledge_items_display_name_trgm_idx" in item_indexes
        assert person == ("PERSON", "Иван Иванов")

    async def test_downgrade_removes_dates_and_preserves_people(
        self,
        engine: AsyncEngine,
        migrated_to_0014: None,
    ) -> None:
        _ = migrated_to_0014
        owner_username = await get_owner_username(engine)
        person_id = "15000000000040008000000000000003"
        date_id = "15000000000040008000000000000004"
        migrate(revision="0015")

        async with engine.begin() as connection:
            await connection.execute(
                items_after_upgrade.insert(),
                [
                    {
                        "id": person_id,
                        "kind": "PERSON",
                        "author_username": owner_username,
                        "display_name": "Пётр Петров",
                        "description": "",
                    },
                    {
                        "id": date_id,
                        "kind": "DATE",
                        "author_username": owner_username,
                        "display_name": "Памятная дата",
                        "description": "",
                    },
                ],
            )
            await connection.execute(
                person_details.insert().values(
                    item_id=person_id,
                    author_username=owner_username,
                    last_name="Петров",
                    first_name="Пётр",
                    middle_name="",
                    email="",
                    phone="",
                    telegram="",
                    birthday_day=None,
                    birthday_month=None,
                    birthday_year=None,
                ),
            )
            await connection.execute(
                date_details.insert().values(
                    item_id=date_id,
                    author_username=owner_username,
                    day=1,
                    month=1,
                    year=2020,
                ),
            )

        downgrade(revision="0014")

        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names()),
            )
            remaining_items = (
                await connection.execute(
                    sa.select(items_before_upgrade.c.id, items_before_upgrade.c.kind),
                )
            ).all()

        assert await get_enum_labels(engine) == ["PERSON"]
        assert DATE_DETAILS_TABLE not in table_names
        assert DATE_PERSON_TABLE not in table_names
        assert [tuple(row) for row in remaining_items] == [(person_id, "PERSON")]
