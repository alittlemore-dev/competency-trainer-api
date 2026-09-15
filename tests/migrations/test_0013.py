from hashlib import sha256

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

ITEM_TABLE = "competency_matrix__competency_matrix_item_model"
MISSING_FIELDS_INDEX = "cmi_workspace_missing_fields_idx"

role_enum = postgresql.ENUM(
    "ANON",
    "USER",
    "MODERATOR",
    "ADMIN",
    "OWNER",
    name="role_enum",
    create_type=False,
)
publish_status_enum = postgresql.ENUM(
    "DRAFT",
    "PUBLISHED",
    name="publish_status_enum",
    create_type=False,
)

users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
    sa.column("role", role_enum),
)
sheets = sa.table(
    "competency_matrix__competency_matrix_sheet_model",
    sa.column("id", sa.String()),
    sa.column("key", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
sections = sa.table(
    "competency_matrix__competency_matrix_section_model",
    sa.column("id", sa.String()),
    sa.column("sheet_id", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
subsections = sa.table(
    "competency_matrix__competency_matrix_subsection_model",
    sa.column("id", sa.String()),
    sa.column("section_id", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
items_0012 = sa.table(
    ITEM_TABLE,
    sa.column("id", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("question_ru", sa.String()),
    sa.column("question_en", sa.String()),
    sa.column("question_ru_fingerprint", sa.LargeBinary(length=32)),
    sa.column("question_en_fingerprint", sa.LargeBinary(length=32)),
    sa.column("answer_ru", sa.String()),
    sa.column("answer_en", sa.String()),
    sa.column("interview_expected_answer_ru", sa.String()),
    sa.column("interview_expected_answer_en", sa.String()),
    sa.column("subsection_id", sa.String()),
    sa.column("publish_status", publish_status_enum),
    sa.column("suggested_by_username", sa.String()),
)
items_0013 = sa.table(
    ITEM_TABLE,
    sa.column("id", sa.String()),
    sa.column("interview_answer_explanation_ru", sa.String()),
    sa.column("interview_answer_explanation_en", sa.String()),
)


async def insert_matrix_item(engine: AsyncEngine) -> str:
    sheet_id = "10000000000040008000000000000001"
    section_id = "10000000000040008000000000000002"
    subsection_id = "10000000000040008000000000000003"
    item_id = "10000000000040008000000000000004"
    async with engine.begin() as connection:
        owner_username = await connection.scalar(
            sa.select(users.c.username).where(users.c.role == "OWNER"),
        )
        assert owner_username is not None
        await connection.execute(
            sheets.insert().values(
                id=sheet_id,
                key="python",
                name_ru="Питон",
                name_en="Python",
                priority=1,
            ),
        )
        await connection.execute(
            sections.insert().values(
                id=section_id,
                sheet_id=sheet_id,
                name_ru="Основы",
                name_en="Basics",
                priority=1,
            ),
        )
        await connection.execute(
            subsections.insert().values(
                id=subsection_id,
                section_id=section_id,
                name_ru="Функции",
                name_en="Functions",
                priority=1,
            ),
        )
        await connection.execute(
            items_0012.insert().values(
                id=item_id,
                slug="function-answer-explanation",
                question_ru="Что делает функция?",
                question_en="What does the function do?",
                question_ru_fingerprint=sha256("что делает функция?".encode()).digest(),
                question_en_fingerprint=sha256(b"what does the function do?").digest(),
                answer_ru="Подробный ответ",
                answer_en="Detailed answer",
                interview_expected_answer_ru="Кратко объяснить ход решения",
                interview_expected_answer_en="Briefly explain the reasoning",
                subsection_id=subsection_id,
                publish_status="DRAFT",
                suggested_by_username=owner_username,
            ),
        )
    return item_id


class TestMigration0013:
    async def test_upgrade_renames_columns_and_preserves_data_and_index(
        self,
        engine: AsyncEngine,
        migrated_to_0012: None,
    ) -> None:
        _ = migrated_to_0012
        item_id = await insert_matrix_item(engine)

        migrate(revision="0013")

        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"] for column in sa.inspect(sync_connection).get_columns(ITEM_TABLE)
                },
            )
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]: index
                    for index in sa.inspect(sync_connection).get_indexes(ITEM_TABLE)
                },
            )
            row = (
                await connection.execute(
                    sa.select(
                        items_0013.c.interview_answer_explanation_ru,
                        items_0013.c.interview_answer_explanation_en,
                    ).where(items_0013.c.id == item_id),
                )
            ).one()

        assert "interview_answer_explanation_ru" in columns
        assert "interview_answer_explanation_en" in columns
        assert "interview_expected_answer_ru" not in columns
        assert "interview_expected_answer_en" not in columns
        assert MISSING_FIELDS_INDEX in indexes
        missing_fields_index = str(indexes[MISSING_FIELDS_INDEX])
        assert "interview_answer_explanation_ru" in missing_fields_index
        assert "interview_answer_explanation_en" in missing_fields_index
        assert "interview_expected_answer_ru" not in missing_fields_index
        assert "interview_expected_answer_en" not in missing_fields_index
        assert row == ("Кратко объяснить ход решения", "Briefly explain the reasoning")

    async def test_downgrade_restores_column_names_and_preserves_data(
        self,
        engine: AsyncEngine,
        migrated_to_0012: None,
    ) -> None:
        _ = migrated_to_0012
        item_id = await insert_matrix_item(engine)
        migrate(revision="0013")

        downgrade(revision="0012")

        async with engine.connect() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"] for column in sa.inspect(sync_connection).get_columns(ITEM_TABLE)
                },
            )
            row = (
                await connection.execute(
                    sa.select(
                        items_0012.c.interview_expected_answer_ru,
                        items_0012.c.interview_expected_answer_en,
                    ).where(items_0012.c.id == item_id),
                )
            ).one()

        assert "interview_expected_answer_ru" in columns
        assert "interview_expected_answer_en" in columns
        assert "interview_answer_explanation_ru" not in columns
        assert "interview_answer_explanation_en" not in columns
        assert row == ("Кратко объяснить ход решения", "Briefly explain the reasoning")
