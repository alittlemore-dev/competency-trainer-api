from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

role_enum = postgresql.ENUM(
    "ANON",
    "USER",
    "MODERATOR",
    "ADMIN",
    "OWNER",
    name="role_enum",
    create_type=False,
)
stored_hash_value = "not-a-real-password-hash"
publish_status_enum = postgresql.ENUM(
    "DRAFT",
    "PUBLISHED",
    name="publish_status_enum",
    create_type=False,
)

users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
    sa.column("password_hash", sa.String()),
    sa.column("role", role_enum),
    sa.column("is_active", sa.Boolean()),
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
items_0008 = sa.table(
    "competency_matrix__competency_matrix_item_model",
    sa.column("id", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("question_ru", sa.String()),
    sa.column("question_en", sa.String()),
    sa.column("answer_ru", sa.String()),
    sa.column("answer_en", sa.String()),
    sa.column("interview_expected_answer_ru", sa.String()),
    sa.column("interview_expected_answer_en", sa.String()),
    sa.column("subsection_id", sa.String()),
    sa.column("publish_status", publish_status_enum),
)
items_0009 = sa.table(
    "competency_matrix__competency_matrix_item_model",
    sa.column("id", sa.String()),
    sa.column("suggested_by_username", sa.String()),
)
queued_questions = sa.table(
    "competency_matrix__queued_question_model",
    sa.column("id", sa.String()),
    sa.column("question", sa.String()),
    sa.column("suggested_by_username", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


class TestMigration0009:
    async def test_upgrade_backfills_required_immutable_attribution(
        self,
        engine: AsyncEngine,
        migrated_to_0008: None,
    ) -> None:
        _ = migrated_to_0008
        now = datetime(2026, 7, 12, 12, 0, tzinfo=UTC)
        async with engine.begin() as connection:
            owner_username = await connection.scalar(
                sa.select(users.c.username).where(users.c.role == "OWNER"),
            )
            assert owner_username is not None
            await connection.execute(
                users.insert().values(
                    username="alice",
                    password_hash=stored_hash_value,
                    role="USER",
                    is_active=True,
                ),
            )
            await connection.execute(
                sheets.insert().values(
                    id="10000000000040008000000000000001",
                    key="python",
                    name_ru="Питон",
                    name_en="Python",
                    priority=1,
                ),
            )
            await connection.execute(
                sections.insert().values(
                    id="10000000000040008000000000000002",
                    sheet_id="10000000000040008000000000000001",
                    name_ru="Основы",
                    name_en="Basics",
                    priority=1,
                ),
            )
            await connection.execute(
                subsections.insert().values(
                    id="10000000000040008000000000000003",
                    section_id="10000000000040008000000000000002",
                    name_ru="Функции",
                    name_en="Functions",
                    priority=1,
                ),
            )
            await connection.execute(
                items_0008.insert().values(
                    id="10000000000040008000000000000004",
                    slug="what-is-pep-8",
                    question_ru="Что такое PEP 8?",
                    question_en="What is PEP 8?",
                    answer_ru="Ответ",
                    answer_en="Answer",
                    interview_expected_answer_ru="Ожидаемый ответ",
                    interview_expected_answer_en="Expected answer",
                    subsection_id="10000000000040008000000000000003",
                    publish_status="DRAFT",
                ),
            )
            await connection.execute(
                queued_questions.insert(),
                [
                    {
                        "id": "10000000000040008000000000000005",
                        "question": "Anonymous legacy question",
                        "suggested_by_username": None,
                        "created_at": now,
                    },
                    {
                        "id": "10000000000040008000000000000006",
                        "question": "Known legacy question",
                        "suggested_by_username": "alice",
                        "created_at": now,
                    },
                ],
            )

        migrate(revision="0009")

        async with engine.begin() as connection:
            item_attribution = await connection.scalar(
                sa.select(items_0009.c.suggested_by_username),
            )
            queue_attributions = list(
                await connection.scalars(
                    sa.select(queued_questions.c.suggested_by_username).order_by(
                        queued_questions.c.id,
                    ),
                ),
            )
            await connection.execute(
                queued_questions.insert().values(
                    id="10000000000040008000000000000007",
                    question="Anonymous current question",
                    suggested_by_username="anon",
                    created_at=now,
                ),
            )
            item_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column["nullable"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "competency_matrix__competency_matrix_item_model",
                    )
                },
            )
            queue_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column["nullable"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "competency_matrix__queued_question_model",
                    )
                },
            )
            queue_foreign_keys = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_foreign_keys(
                    "competency_matrix__queued_question_model",
                ),
            )

        assert item_attribution == owner_username
        assert queue_attributions == [owner_username, "alice"]
        assert item_columns["suggested_by_username"] is False
        assert queue_columns["suggested_by_username"] is False
        assert all(
            "suggested_by_username" not in foreign_key["constrained_columns"]
            for foreign_key in queue_foreign_keys
        )

    async def test_downgrade_restores_nullable_user_reference(
        self,
        engine: AsyncEngine,
        migrated_to_0008: None,
    ) -> None:
        _ = migrated_to_0008
        migrate(revision="0009")
        async with engine.begin() as connection:
            await connection.execute(
                queued_questions.insert().values(
                    id="20000000000040008000000000000001",
                    question="Anonymous current question",
                    suggested_by_username="anon",
                    created_at=datetime(2026, 7, 12, 12, 0, tzinfo=UTC),
                ),
            )

        downgrade(revision="0008")

        async with engine.begin() as connection:
            restored_attribution = await connection.scalar(
                sa.select(queued_questions.c.suggested_by_username).where(
                    queued_questions.c.id == "20000000000040008000000000000001",
                ),
            )
            item_column_names = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "competency_matrix__competency_matrix_item_model",
                    )
                },
            )
            queue_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column["nullable"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "competency_matrix__queued_question_model",
                    )
                },
            )
            queue_foreign_keys = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_foreign_keys(
                    "competency_matrix__queued_question_model",
                ),
            )

        assert restored_attribution is None
        assert "suggested_by_username" not in item_column_names
        assert queue_columns["suggested_by_username"] is True
        assert any(
            foreign_key["constrained_columns"] == ["suggested_by_username"]
            for foreign_key in queue_foreign_keys
        )
