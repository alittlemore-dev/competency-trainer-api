from typing import Protocol, TypedDict, cast

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

ITEM_TABLE = "knowledge__knowledge_item_model"
TAG_TABLE = "knowledge__knowledge_tag_model"
ITEM_TAG_TABLE = "knowledge__knowledge_item_tag_model"
DETAILS_TABLE = "knowledge__person_details_model"
RELATIONSHIP_TYPE_TABLE = "knowledge__person_relationship_type_model"
RELATIONSHIP_TABLE = "knowledge__person_relationship_model"
FILE_TABLE = "knowledge__knowledge_file_model"
KNOWLEDGE_ENUM = "knowledge_item_kind_enum"
FILE_ENUM = "knowledge_file_kind_enum"


class ReflectedEnum(TypedDict):
    name: str
    labels: list[str]


class PostgreSQLInspector(Protocol):
    def get_enums(self) -> list[ReflectedEnum]: ...


role_enum = postgresql.ENUM(
    "ANON",
    "USER",
    "MODERATOR",
    "ADMIN",
    "OWNER",
    name="role_enum",
    create_type=False,
)
knowledge_item_kind_enum = postgresql.ENUM(
    "PERSON",
    name=KNOWLEDGE_ENUM,
    create_type=False,
)
knowledge_file_kind_enum = postgresql.ENUM(
    "ATTACHMENT",
    "PERSON_PHOTO",
    name=FILE_ENUM,
    create_type=False,
)
users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
    sa.column("role", role_enum),
)
items = sa.table(
    ITEM_TABLE,
    sa.column("id", sa.String()),
    sa.column("kind", knowledge_item_kind_enum),
    sa.column("author_username", sa.String()),
    sa.column("display_name", sa.String()),
    sa.column("description", sa.Text()),
)
details = sa.table(
    DETAILS_TABLE,
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
relationship_types = sa.table(
    RELATIONSHIP_TYPE_TABLE,
    sa.column("id", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("is_symmetric", sa.Boolean()),
    sa.column("forward_name", sa.String()),
    sa.column("reverse_name", sa.String()),
)
relationships = sa.table(
    RELATIONSHIP_TABLE,
    sa.column("id", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("source_person_id", sa.String()),
    sa.column("target_person_id", sa.String()),
    sa.column("relationship_type_id", sa.String()),
    sa.column("note", sa.Text()),
)
knowledge_files = sa.table(
    FILE_TABLE,
    sa.column("id", sa.String()),
    sa.column("item_id", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("kind", knowledge_file_kind_enum),
    sa.column("relative_path", sa.String()),
    sa.column("mime_type", sa.String()),
    sa.column("size_bytes", sa.Integer()),
    sa.column("name", sa.String()),
    sa.column("original_name", sa.String()),
    sa.column("original_sha256", sa.String()),
)


async def get_owner_username(engine: AsyncEngine) -> str:
    async with engine.connect() as connection:
        username = await connection.scalar(
            sa.select(users.c.username).where(users.c.role == "OWNER"),
        )
    assert username is not None
    return cast("str", username)


class TestMigration0014:
    async def test_upgrade_creates_native_enum_and_enforces_people_constraints(
        self,
        engine: AsyncEngine,
        migrated_to_0013: None,
    ) -> None:
        _ = migrated_to_0013
        migrate(revision="0014")
        owner_username = await get_owner_username(engine)
        first_id = "14000000000040008000000000000001"
        second_id = "14000000000040008000000000000002"
        invalid_id = "14000000000040008000000000000003"
        type_id = "14000000000040008000000000000004"
        relationship_id = "14000000000040008000000000000005"

        async with engine.begin() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names()),
            )
            enums = await connection.run_sync(
                lambda sync_connection: {
                    enum["name"]: enum["labels"]
                    for enum in cast(
                        "PostgreSQLInspector",
                        sa.inspect(sync_connection),
                    ).get_enums()
                },
            )
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    table_name: {
                        index["name"]
                        for index in sa.inspect(sync_connection).get_indexes(table_name)
                    }
                    for table_name in (TAG_TABLE, DETAILS_TABLE, RELATIONSHIP_TABLE)
                },
            )
            details_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column
                    for column in sa.inspect(sync_connection).get_columns(DETAILS_TABLE)
                },
            )
            await connection.execute(
                items.insert(),
                [
                    {
                        "id": first_id,
                        "kind": "PERSON",
                        "author_username": owner_username,
                        "display_name": "Иванов Иван",
                        "description": "",
                    },
                    {
                        "id": second_id,
                        "kind": "PERSON",
                        "author_username": owner_username,
                        "display_name": "Петров Пётр",
                        "description": "",
                    },
                    {
                        "id": invalid_id,
                        "kind": "PERSON",
                        "author_username": owner_username,
                        "display_name": "Будущий Человек",
                        "description": "",
                    },
                ],
            )
            await connection.execute(
                details.insert(),
                [
                    {
                        "item_id": first_id,
                        "author_username": owner_username,
                        "last_name": "Иванов",
                        "first_name": "Иван",
                        "middle_name": "",
                        "email": "",
                        "phone": "",
                        "telegram": "@ivanov",
                        "birthday_day": 29,
                        "birthday_month": 2,
                        "birthday_year": None,
                    },
                    {
                        "item_id": second_id,
                        "author_username": owner_username,
                        "last_name": "Петров",
                        "first_name": "Пётр",
                        "middle_name": "",
                        "email": "",
                        "phone": "",
                        "telegram": "",
                        "birthday_day": None,
                        "birthday_month": None,
                        "birthday_year": None,
                    },
                ],
            )
            await connection.execute(
                relationship_types.insert().values(
                    id=type_id,
                    author_username=owner_username,
                    is_symmetric=True,
                    forward_name="друг",
                    reverse_name="друг",
                ),
            )
            await connection.execute(
                relationships.insert().values(
                    id=relationship_id,
                    author_username=owner_username,
                    source_person_id=first_id,
                    target_person_id=second_id,
                    relationship_type_id=type_id,
                    note="",
                ),
            )
            await connection.execute(
                knowledge_files.insert(),
                [
                    {
                        "id": "14000000000040008000000000000008",
                        "item_id": first_id,
                        "author_username": owner_username,
                        "kind": "PERSON_PHOTO",
                        "relative_path": "person-photos/photo.webp",
                        "mime_type": "image/webp",
                        "size_bytes": 10,
                        "name": "Photo",
                        "original_name": "photo.png",
                        "original_sha256": "a" * 64,
                    },
                    {
                        "id": "14000000000040008000000000000009",
                        "item_id": first_id,
                        "author_username": owner_username,
                        "kind": "ATTACHMENT",
                        "relative_path": "attachments/notes.txt",
                        "mime_type": "text/plain",
                        "size_bytes": 5,
                        "name": "Notes",
                        "original_name": "notes.txt",
                        "original_sha256": "b" * 64,
                    },
                ],
            )

        assert {
            ITEM_TABLE,
            TAG_TABLE,
            ITEM_TAG_TABLE,
            DETAILS_TABLE,
            RELATIONSHIP_TYPE_TABLE,
            RELATIONSHIP_TABLE,
            FILE_TABLE,
        }.issubset(table_names)
        assert enums[KNOWLEDGE_ENUM] == ["PERSON"]
        assert enums[FILE_ENUM] == ["ATTACHMENT", "PERSON_PHOTO"]
        assert "knowledge_tags_name_trgm_idx" in indexes[TAG_TABLE]
        assert {
            "person_details_last_name_trgm_idx",
            "person_details_first_name_trgm_idx",
            "person_details_middle_name_trgm_idx",
            "person_details_email_trgm_idx",
        }.issubset(indexes[DETAILS_TABLE])
        assert "person_details_author_email_item_idx" in indexes[DETAILS_TABLE]
        assert "person_details_phone_trgm_idx" not in indexes[DETAILS_TABLE]
        assert details_columns["telegram"]["nullable"] is False
        telegram_type = details_columns["telegram"]["type"]
        assert isinstance(telegram_type, sa.String)
        assert telegram_type.length == 255
        assert "person_relationships_author_type_id_idx" in indexes[RELATIONSHIP_TABLE]

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    details.insert().values(
                        item_id=invalid_id,
                        author_username=owner_username,
                        last_name="Без",
                        first_name="Telegram",
                        middle_name="",
                        email="",
                        phone="",
                        birthday_day=None,
                        birthday_month=None,
                        birthday_year=None,
                    ),
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    details.insert().values(
                        item_id=invalid_id,
                        author_username=owner_username,
                        last_name="Будущий",
                        first_name="Человек",
                        middle_name="",
                        email="",
                        phone="",
                        telegram="",
                        birthday_day=31,
                        birthday_month=4,
                        birthday_year=None,
                    ),
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    details.insert().values(
                        item_id=invalid_id,
                        author_username=owner_username,
                        last_name="Будущий",
                        first_name="Человек",
                        middle_name="",
                        email="",
                        phone="",
                        telegram="",
                        birthday_day=1,
                        birthday_month=1,
                        birthday_year=9999,
                    ),
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    relationships.insert().values(
                        id="14000000000040008000000000000006",
                        author_username=owner_username,
                        source_person_id=first_id,
                        target_person_id=first_id,
                        relationship_type_id=type_id,
                        note="",
                    ),
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    knowledge_files.insert().values(
                        id="14000000000040008000000000000010",
                        item_id=first_id,
                        author_username=owner_username,
                        kind="PERSON_PHOTO",
                        relative_path="person-photos/second.webp",
                        mime_type="image/webp",
                        size_bytes=10,
                        name="Second photo",
                        original_name="second.png",
                        original_sha256="c" * 64,
                    ),
                )

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    relationships.insert().values(
                        id="14000000000040008000000000000007",
                        author_username=owner_username,
                        source_person_id=second_id,
                        target_person_id=first_id,
                        relationship_type_id=type_id,
                        note="duplicate reverse pair",
                    ),
                )

    async def test_downgrade_removes_people_tables_and_native_enum(
        self,
        engine: AsyncEngine,
        migrated_to_0013: None,
    ) -> None:
        _ = migrated_to_0013
        migrate(revision="0014")

        downgrade(revision="0013")

        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names()),
            )
            enum_names = await connection.run_sync(
                lambda sync_connection: {
                    enum["name"]
                    for enum in cast(
                        "PostgreSQLInspector",
                        sa.inspect(sync_connection),
                    ).get_enums()
                },
            )

        assert ITEM_TABLE not in table_names
        assert DETAILS_TABLE not in table_names
        assert RELATIONSHIP_TABLE not in table_names
        assert FILE_TABLE not in table_names
        assert KNOWLEDGE_ENUM not in enum_names
        assert FILE_ENUM not in enum_names
