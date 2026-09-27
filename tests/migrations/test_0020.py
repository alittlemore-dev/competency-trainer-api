import pytest
import sqlalchemy as sa
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

SHEET_TABLE = "competency_matrix__competency_matrix_sheet_model"
SECTION_TABLE = "competency_matrix__competency_matrix_section_model"
SUBSECTION_TABLE = "competency_matrix__competency_matrix_subsection_model"
ITEM_TABLE = "competency_matrix__competency_matrix_item_model"


def seed_existing_question(connection: Connection) -> None:
    metadata = sa.MetaData()
    sheet = sa.Table(SHEET_TABLE, metadata, autoload_with=connection)
    section = sa.Table(SECTION_TABLE, metadata, autoload_with=connection)
    subsection = sa.Table(SUBSECTION_TABLE, metadata, autoload_with=connection)
    item = sa.Table(ITEM_TABLE, metadata, autoload_with=connection)
    for number, key in ((1, "python"), (2, "javascript")):
        identifier = f"{number:032x}"
        connection.execute(
            sheet.insert().values(
                id=identifier,
                key=key,
                name_ru=key,
                name_en=key,
                priority=number,
            )
        )
        connection.execute(
            section.insert().values(
                id=identifier,
                sheet_id=identifier,
                name_ru="Basics",
                name_en="Basics",
                priority=number,
            )
        )
        connection.execute(
            subsection.insert().values(
                id=identifier,
                section_id=identifier,
                name_ru="Syntax",
                name_en="Syntax",
                priority=number,
            )
        )
    connection.execute(
        item.insert().values(
            id=f"{1:032x}",
            slug="shared-question",
            subsection_id=f"{1:032x}",
            question_ru="Вопрос",
            question_en="Question",
            question_ru_fingerprint=b"r" * 32,
            question_en_fingerprint=b"e" * 32,
            answer_ru="Ответ",
            answer_en="Answer",
            interview_answer_explanation_ru="Пояснение",
            interview_answer_explanation_en="Explanation",
            suggested_by_username="tester",
            publish_status="PUBLISHED",
        )
    )


class TestMigration0020:
    async def test_scopes_slugs(
        self,
        engine: AsyncEngine,
        migrated_to_0019: None,
    ) -> None:
        _ = migrated_to_0019
        async with engine.begin() as connection:
            await connection.run_sync(seed_existing_question)

        migrate(revision="0020")

        async with engine.begin() as connection:
            metadata = sa.MetaData()
            item = await connection.run_sync(
                lambda sync_connection: sa.Table(
                    ITEM_TABLE, metadata, autoload_with=sync_connection
                )
            )
            assert (
                await connection.execute(sa.select(item.c.sheet_id))
            ).scalar_one() == f"{1:032x}"
            existing = (
                (await connection.execute(sa.select(item).where(item.c.id == f"{1:032x}")))
                .mappings()
                .one()
            )
            await connection.execute(
                item.insert().values(
                    **{
                        **existing,
                        "id": f"{3:032x}",
                        "sheet_id": f"{2:032x}",
                        "subsection_id": f"{2:032x}",
                    }
                )
            )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        item.insert().values(**{**existing, "id": f"{4:032x}"})
                    )

        with pytest.raises(RuntimeError, match="global slug uniqueness"):
            downgrade(revision="0019")

        async with engine.begin() as connection:
            await connection.execute(item.delete().where(item.c.id == f"{3:032x}"))

        downgrade(revision="0019")

        async with engine.connect() as connection:
            assert "sheet_id" not in {
                column["name"]
                for column in await connection.run_sync(
                    lambda sync_connection: sa.inspect(sync_connection).get_columns(ITEM_TABLE)
                )
            }
