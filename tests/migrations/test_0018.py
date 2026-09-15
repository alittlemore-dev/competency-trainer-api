from typing import Protocol, TypedDict, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

REMOVED_TABLES = (
    "knowledge__date_person_model",
    "knowledge__person_relationship_model",
    "knowledge__knowledge_item_tag_model",
    "knowledge__knowledge_file_model",
    "knowledge__date_details_model",
    "knowledge__person_details_model",
    "knowledge__person_relationship_type_model",
    "knowledge__knowledge_tag_model",
    "knowledge__knowledge_item_model",
    "resumes__resume_model",
)
REMOVED_ENUMS = {"knowledge_file_kind_enum", "knowledge_item_kind_enum"}


class ReflectedEnum(TypedDict):
    name: str
    labels: list[str]


class PostgreSQLInspector(Protocol):
    def get_enums(self) -> list[ReflectedEnum]: ...


knowledge_item_kind = postgresql.ENUM(
    "DATE",
    "PERSON",
    name="knowledge_item_kind_enum",
    create_type=False,
)
knowledge_file_kind = postgresql.ENUM(
    "ATTACHMENT",
    "PERSON_PHOTO",
    name="knowledge_file_kind_enum",
    create_type=False,
)
language = postgresql.ENUM("RU", "EN", name="language_enum", create_type=False)

users = sa.table("auth__user_model", sa.column("username", sa.String(length=255)))
resumes = sa.table(
    "resumes__resume_model",
    sa.column("title", sa.String(length=255)),
    sa.column("language", language),
    sa.column("author_username", sa.String(length=255)),
    sa.column("content", postgresql.JSONB()),
)
items = sa.table(
    "knowledge__knowledge_item_model",
    sa.column("id", sa.String(length=32)),
    sa.column("kind", knowledge_item_kind),
    sa.column("author_username", sa.String(length=255)),
    sa.column("display_name", sa.String(length=255)),
    sa.column("description", sa.Text()),
)
tags = sa.table(
    "knowledge__knowledge_tag_model",
    sa.column("id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
    sa.column("name", sa.String(length=255)),
)
relationship_types = sa.table(
    "knowledge__person_relationship_type_model",
    sa.column("id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
    sa.column("is_symmetric", sa.Boolean()),
    sa.column("forward_name", sa.String(length=255)),
    sa.column("reverse_name", sa.String(length=255)),
)
files = sa.table(
    "knowledge__knowledge_file_model",
    sa.column("id", sa.String(length=32)),
    sa.column("item_id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
    sa.column("kind", knowledge_file_kind),
    sa.column("relative_path", sa.String(length=1024)),
    sa.column("mime_type", sa.String(length=255)),
    sa.column("size_bytes", sa.Integer()),
    sa.column("name", sa.String(length=255)),
    sa.column("original_name", sa.String(length=255)),
    sa.column("original_sha256", sa.String(length=64)),
)
item_tags = sa.table(
    "knowledge__knowledge_item_tag_model",
    sa.column("item_id", sa.String(length=32)),
    sa.column("tag_id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
)
person_details = sa.table(
    "knowledge__person_details_model",
    sa.column("item_id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
    sa.column("last_name", sa.String(length=255)),
    sa.column("first_name", sa.String(length=255)),
    sa.column("middle_name", sa.String(length=255)),
    sa.column("email", sa.String(length=320)),
    sa.column("phone", sa.String(length=64)),
    sa.column("telegram", sa.String(length=255)),
    sa.column("birthday_day", sa.Integer()),
    sa.column("birthday_month", sa.Integer()),
    sa.column("birthday_year", sa.Integer()),
)
relationships = sa.table(
    "knowledge__person_relationship_model",
    sa.column("id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
    sa.column("source_person_id", sa.String(length=32)),
    sa.column("target_person_id", sa.String(length=32)),
    sa.column("relationship_type_id", sa.String(length=32)),
    sa.column("note", sa.Text()),
)
date_details = sa.table(
    "knowledge__date_details_model",
    sa.column("item_id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
    sa.column("day", sa.Integer()),
    sa.column("month", sa.Integer()),
    sa.column("year", sa.Integer()),
)
date_people = sa.table(
    "knowledge__date_person_model",
    sa.column("date_item_id", sa.String(length=32)),
    sa.column("person_item_id", sa.String(length=32)),
    sa.column("author_username", sa.String(length=255)),
)


def database_enum_names(connection: Connection) -> set[str]:
    inspector = cast("PostgreSQLInspector", sa.inspect(connection))
    return {enum["name"] for enum in inspector.get_enums()}


def legacy_schema(connection: Connection) -> dict[str, dict[str, object]]:
    inspector = sa.inspect(connection)
    return {
        table_name: {
            "columns": tuple(
                (
                    column["name"],
                    str(column["type"]),
                    column["nullable"],
                    str(column["default"]),
                )
                for column in inspector.get_columns(table_name)
            ),
            "primary_key": tuple(inspector.get_pk_constraint(table_name)["constrained_columns"]),
            "unique_constraints": tuple(
                sorted(
                    (
                        constraint["name"],
                        tuple(constraint["column_names"]),
                    )
                    for constraint in inspector.get_unique_constraints(table_name)
                ),
            ),
            "foreign_keys": tuple(
                sorted(
                    (
                        foreign_key["name"],
                        tuple(foreign_key["constrained_columns"]),
                        foreign_key["referred_table"],
                        tuple(foreign_key["referred_columns"]),
                        tuple(sorted(foreign_key["options"].items())),
                    )
                    for foreign_key in inspector.get_foreign_keys(table_name)
                ),
            ),
            "checks": tuple(
                sorted(
                    (constraint["name"], constraint["sqltext"])
                    for constraint in inspector.get_check_constraints(table_name)
                ),
            ),
            "indexes": tuple(
                sorted(
                    (
                        index["name"],
                        index["unique"],
                        tuple(index["column_names"]),
                        tuple(index.get("expressions", ())),
                        str(index.get("dialect_options", {})),
                    )
                    for index in inspector.get_indexes(table_name)
                ),
            ),
        }
        for table_name in REMOVED_TABLES
    }


async def seed_removed_domain_data(engine: AsyncEngine) -> str:
    person_one_id = "18000000000000000000000000000001"
    person_two_id = "18000000000000000000000000000002"
    date_id = "18000000000000000000000000000003"
    tag_id = "18000000000000000000000000000004"
    relationship_type_id = "18000000000000000000000000000005"
    async with engine.begin() as connection:
        author_username = cast(
            "str",
            (await connection.execute(sa.select(users.c.username).limit(1))).scalar_one(),
        )
        await connection.execute(
            resumes.insert().values(
                title="Migration 0018 resume",
                language="EN",
                author_username=author_username,
                content={},
            ),
        )
        await connection.execute(
            items.insert(),
            [
                {
                    "id": person_one_id,
                    "kind": "PERSON",
                    "author_username": author_username,
                    "display_name": "First Person",
                    "description": "First representative person",
                },
                {
                    "id": person_two_id,
                    "kind": "PERSON",
                    "author_username": author_username,
                    "display_name": "Second Person",
                    "description": "Second representative person",
                },
                {
                    "id": date_id,
                    "kind": "DATE",
                    "author_username": author_username,
                    "display_name": "Representative Date",
                    "description": "Representative date",
                },
            ],
        )
        await connection.execute(
            tags.insert().values(id=tag_id, author_username=author_username, name="Migration 0018"),
        )
        await connection.execute(
            relationship_types.insert().values(
                id=relationship_type_id,
                author_username=author_username,
                is_symmetric=False,
                forward_name="Mentor",
                reverse_name="Mentee",
            ),
        )
        await connection.execute(
            person_details.insert(),
            [
                {
                    "item_id": person_one_id,
                    "author_username": author_username,
                    "last_name": "One",
                    "first_name": "Person",
                    "middle_name": "",
                    "email": "one@example.com",
                    "phone": "",
                    "telegram": "",
                    "birthday_day": 1,
                    "birthday_month": 1,
                    "birthday_year": 2000,
                },
                {
                    "item_id": person_two_id,
                    "author_username": author_username,
                    "last_name": "Two",
                    "first_name": "Person",
                    "middle_name": "",
                    "email": "two@example.com",
                    "phone": "",
                    "telegram": "",
                    "birthday_day": None,
                    "birthday_month": None,
                    "birthday_year": None,
                },
            ],
        )
        await connection.execute(
            date_details.insert().values(
                item_id=date_id,
                author_username=author_username,
                day=14,
                month=8,
                year=2026,
            ),
        )
        await connection.execute(
            item_tags.insert().values(
                item_id=person_one_id,
                tag_id=tag_id,
                author_username=author_username,
            ),
        )
        await connection.execute(
            files.insert().values(
                id="18000000000000000000000000000006",
                item_id=person_one_id,
                author_username=author_username,
                kind="PERSON_PHOTO",
                relative_path="migration-0018/person.png",
                mime_type="image/png",
                size_bytes=1,
                name="Person photo",
                original_name="person.png",
                original_sha256="1" * 64,
            ),
        )
        await connection.execute(
            relationships.insert().values(
                id="18000000000000000000000000000007",
                author_username=author_username,
                source_person_id=person_one_id,
                target_person_id=person_two_id,
                relationship_type_id=relationship_type_id,
                note="Representative relationship",
            ),
        )
        await connection.execute(
            date_people.insert().values(
                date_item_id=date_id,
                person_item_id=person_one_id,
                author_username=author_username,
            ),
        )
    return author_username


class TestMigration0018:
    async def test_upgrade_removes_populated_domains_and_downgrade_restores_empty_legacy_schema(
        self,
        engine: AsyncEngine,
        migrated_to_0017: None,
    ) -> None:
        _ = migrated_to_0017
        async with engine.connect() as connection:
            schema_before = await connection.run_sync(legacy_schema)
        author_username = await seed_removed_domain_data(engine)

        migrate(revision="0018")

        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names()),
            )
            enum_names = await connection.run_sync(database_enum_names)
            preserved_author = (
                await connection.execute(
                    sa.select(users.c.username).where(users.c.username == author_username),
                )
            ).scalar_one()
        assert not set(REMOVED_TABLES) & table_names
        assert not REMOVED_ENUMS & enum_names
        assert "language_enum" in enum_names
        assert preserved_author == author_username

        downgrade(revision="0017")

        async with engine.connect() as connection:
            schema_after = await connection.run_sync(legacy_schema)
            enum_names = await connection.run_sync(database_enum_names)
            row_counts = {
                table_name: (
                    await connection.execute(
                        sa.select(sa.func.count()).select_from(sa.table(table_name)),
                    )
                ).scalar_one()
                for table_name in REMOVED_TABLES
            }
        assert schema_after == schema_before
        assert enum_names >= REMOVED_ENUMS
        assert "language_enum" in enum_names
        assert row_counts == dict.fromkeys(REMOVED_TABLES, 0)
