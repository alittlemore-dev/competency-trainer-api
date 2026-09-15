from datetime import UTC, datetime
from hashlib import sha256

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

publish_status_enum = postgresql.ENUM(
    "DRAFT",
    "PUBLISHED",
    name="publish_status_enum",
    create_type=False,
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
items = sa.table(
    "competency_matrix__competency_matrix_item_model",
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
queued_questions = sa.table(
    "competency_matrix__queued_question_model",
    sa.column("id", sa.String()),
    sa.column("question", sa.String()),
    sa.column("question_fingerprint", sa.LargeBinary(length=32)),
    sa.column("suggested_by_username", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


class TestMigration0010:
    async def test_upgrade_indexes_existing_matrix_and_queue_questions(
        self,
        engine: AsyncEngine,
        migrated_to_0009: None,
    ) -> None:
        _ = migrated_to_0009
        sheet_id = "10000000000040008000000000000001"
        section_id = "10000000000040008000000000000002"
        subsection_id = "10000000000040008000000000000003"
        async with engine.begin() as connection:
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
                items.insert().values(
                    id="10000000000040008000000000000004",
                    slug="what-is-pep-8",
                    question_ru="Что такое PEP 8?",
                    question_en="What is PEP 8?",
                    answer_ru="Ответ",
                    answer_en="Answer",
                    interview_expected_answer_ru="Ожидаемый ответ",
                    interview_expected_answer_en="Expected answer",
                    subsection_id=subsection_id,
                    publish_status="DRAFT",
                    suggested_by_username="owner",
                ),
            )
            await connection.execute(
                queued_questions.insert().values(
                    id="10000000000040008000000000000005",
                    question="How does asyncio work?",
                    suggested_by_username="anon",
                    created_at=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
                ),
            )

        migrate(revision="0010")

        async with engine.begin() as connection:
            item_fingerprints = await connection.execute(
                sa.select(
                    items.c.question_ru_fingerprint,
                    items.c.question_en_fingerprint,
                ),
            )
            queue_fingerprint = await connection.scalar(
                sa.select(queued_questions.c.question_fingerprint),
            )
            item_indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]
                    for index in sa.inspect(sync_connection).get_indexes(
                        "competency_matrix__competency_matrix_item_model",
                    )
                },
            )
            queue_indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]
                    for index in sa.inspect(sync_connection).get_indexes(
                        "competency_matrix__queued_question_model",
                    )
                },
            )

        assert "cmi_question_ru_fingerprint_idx" in item_indexes
        assert "cmi_question_en_fingerprint_idx" in item_indexes
        assert "cm_queued_question_fingerprint_idx" in queue_indexes
        assert item_fingerprints.one() == (
            sha256(bytes("что такое pep 8?", "utf-8")).digest(),
            sha256(b"what is pep 8?").digest(),
        )
        assert queue_fingerprint == sha256(b"how does asyncio work?").digest()

    async def test_downgrade_removes_question_fingerprint_indexes(
        self,
        engine: AsyncEngine,
        migrated_to_0009: None,
    ) -> None:
        _ = migrated_to_0009
        migrate(revision="0010")
        downgrade(revision="0009")

        async with engine.begin() as connection:
            item_indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]
                    for index in sa.inspect(sync_connection).get_indexes(
                        "competency_matrix__competency_matrix_item_model",
                    )
                },
            )
            queue_indexes = await connection.run_sync(
                lambda sync_connection: {
                    index["name"]
                    for index in sa.inspect(sync_connection).get_indexes(
                        "competency_matrix__queued_question_model",
                    )
                },
            )
            item_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "competency_matrix__competency_matrix_item_model",
                    )
                },
            )
            queue_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "competency_matrix__queued_question_model",
                    )
                },
            )

        assert "cmi_question_ru_fingerprint_idx" not in item_indexes
        assert "cmi_question_en_fingerprint_idx" not in item_indexes
        assert "cm_queued_question_fingerprint_idx" not in queue_indexes
        assert "question_ru_fingerprint" not in item_columns
        assert "question_en_fingerprint" not in item_columns
        assert "question_fingerprint" not in queue_columns
