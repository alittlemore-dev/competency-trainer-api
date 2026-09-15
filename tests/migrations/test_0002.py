import uuid
from datetime import UTC, date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from infra.postgresql.utils import downgrade, migrate
from tests.helpers.assertions import AssertsHelper

publish_status_enum = postgresql.ENUM(
    "DRAFT",
    "PUBLISHED",
    name="publish_status_enum",
    create_type=False,
)
article_view_source_category_enum = postgresql.ENUM(
    "DIRECT",
    "INTERNAL",
    "SEARCH",
    "SOCIAL",
    "EXTERNAL",
    "UNKNOWN",
    name="article_view_source_category_enum",
    create_type=False,
)
article_reaction_kind_enum = postgresql.ENUM(
    "HEART",
    "FIRE",
    "THINKING",
    "NEUTRAL",
    "POOP",
    name="article_reaction_kind_enum",
    create_type=False,
)
language_enum = postgresql.ENUM("RU", "EN", name="language_enum", create_type=False)
grade_enum = postgresql.ENUM(
    "JUNIOR",
    "JUNIOR_PLUS",
    "MIDDLE",
    "MIDDLE_PLUS",
    "SENIOR",
    name="grade_enum",
    create_type=False,
)
interview_frequency_enum = postgresql.ENUM(
    "CONSTANTLY",
    "OFTEN",
    "RARELY",
    "NEVER_SEEN",
    name="interview_frequency_enum",
    create_type=False,
)

articles = sa.table(
    "articles__article_model",
    sa.column("id", sa.UUID()),
    sa.column("slug", sa.String()),
    sa.column("title_ru", sa.String()),
    sa.column("title_en", sa.String()),
    sa.column("content_ru", sa.String()),
    sa.column("content_en", sa.String()),
    sa.column("folder_ru", sa.String()),
    sa.column("folder_en", sa.String()),
    sa.column("author_username", sa.String()),
    sa.column("publish_status", publish_status_enum),
)
tags = sa.table(
    "articles__tag_model",
    sa.column("id", sa.BigInteger()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("slug", sa.String()),
)
article_tags = sa.table(
    "articles__article_to_tag_secondary_model",
    sa.column("id", sa.BigInteger()),
    sa.column("article_id", sa.UUID()),
    sa.column("tag_id", sa.BigInteger()),
)
article_analytics = sa.table(
    "articles__article_daily_analytics_model",
    sa.column("id", sa.BigInteger()),
    sa.column("article_id", sa.UUID()),
    sa.column("date", sa.Date()),
    sa.column("source_category", article_view_source_category_enum),
    sa.column("view_count", sa.Integer()),
    sa.column("engaged_view_count", sa.Integer()),
)
article_reactions = sa.table(
    "articles__article_reaction_model",
    sa.column("id", sa.BigInteger()),
    sa.column("article_id", sa.UUID()),
    sa.column("article_scoped_voter_hash", sa.String()),
    sa.column("reaction_kind", article_reaction_kind_enum),
)
contacts = sa.table(
    "contacts__contact_me_model",
    sa.column("id", sa.UUID()),
    sa.column("name", sa.String()),
    sa.column("email", sa.String()),
    sa.column("telegram", sa.String()),
    sa.column("message", sa.String()),
)
resumes = sa.table(
    "resumes__resume_model",
    sa.column("id", sa.BigInteger()),
    sa.column("title", sa.String()),
    sa.column("language", language_enum),
    sa.column("author_username", sa.String()),
    sa.column("content", postgresql.JSONB()),
)
matrix_sheets = sa.table(
    "competency_matrix__competency_matrix_sheet_model",
    sa.column("id", sa.BigInteger()),
    sa.column("key", sa.String()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
matrix_sections = sa.table(
    "competency_matrix__competency_matrix_section_model",
    sa.column("id", sa.BigInteger()),
    sa.column("sheet_id", sa.BigInteger()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
matrix_subsections = sa.table(
    "competency_matrix__competency_matrix_subsection_model",
    sa.column("id", sa.BigInteger()),
    sa.column("section_id", sa.BigInteger()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("priority", sa.Integer()),
)
matrix_items = sa.table(
    "competency_matrix__competency_matrix_item_model",
    sa.column("id", sa.BigInteger()),
    sa.column("slug", sa.String()),
    sa.column("question_ru", sa.String()),
    sa.column("question_en", sa.String()),
    sa.column("answer_ru", sa.String()),
    sa.column("answer_en", sa.String()),
    sa.column("interview_expected_answer_ru", sa.String()),
    sa.column("interview_expected_answer_en", sa.String()),
    sa.column("subsection_id", sa.BigInteger()),
    sa.column("grade", grade_enum),
    sa.column("interview_frequency", interview_frequency_enum),
    sa.column("publish_status", publish_status_enum),
)
matrix_resources = sa.table(
    "competency_matrix__external_resource_model",
    sa.column("id", sa.BigInteger()),
    sa.column("name_ru", sa.String()),
    sa.column("name_en", sa.String()),
    sa.column("url", sa.String()),
)
matrix_resource_links = sa.table(
    "competency_matrix__resource_to_item_secondary_model",
    sa.column("id", sa.BigInteger()),
    sa.column("item_id", sa.BigInteger()),
    sa.column("resource_id", sa.BigInteger()),
    sa.column("context_ru", sa.String()),
    sa.column("context_en", sa.String()),
)
queued_questions = sa.table(
    "competency_matrix__queued_question_model",
    sa.column("id", sa.BigInteger()),
    sa.column("question", sa.String()),
    sa.column("grade", grade_enum),
    sa.column("sheet", sa.String()),
    sa.column("section", sa.String()),
    sa.column("subsection", sa.String()),
    sa.column("created_at", sa.DateTime(timezone=True)),
)


class TestMigration0002:
    async def test_upgrade_converts_entity_ids_to_uuid_hex_and_preserves_relationships(
        self,
        engine: AsyncEngine,
        migrated_to_0001: None,
        migration_asserts: AssertsHelper,
    ) -> None:
        _ = migrated_to_0001
        article_id = uuid.UUID("10000000-0000-4000-8000-000000000001")
        contact_id = uuid.UUID("10000000-0000-4000-8000-000000000002")

        async with engine.begin() as connection:
            await insert_0001_rows(
                connection=connection,
                article_id=article_id,
                contact_id=contact_id,
            )

        migrate(revision="0002")

        async with engine.connect() as connection:
            article_row = (
                await connection.execute(
                    sa.select(sa.cast(articles.c.id, sa.String())).where(
                        articles.c.slug == "migration-article",
                    ),
                )
            ).scalar_one()
            tag_row = (
                await connection.execute(
                    sa.select(sa.cast(tags.c.id, sa.String())).where(
                        tags.c.slug == "migration-tag",
                    ),
                )
            ).scalar_one()
            contact_row = (
                await connection.execute(sa.select(sa.cast(contacts.c.id, sa.String())))
            ).scalar_one()
            link_row = (
                (
                    await connection.execute(
                        sa.select(
                            sa.cast(article_tags.c.article_id, sa.String()).label("article_id"),
                            sa.cast(article_tags.c.tag_id, sa.String()).label("tag_id"),
                        ),
                    )
                )
                .mappings()
                .one()
            )
            matrix_link_row = (
                (
                    await connection.execute(
                        sa.select(
                            sa.cast(matrix_resource_links.c.item_id, sa.String()).label("item_id"),
                            sa.cast(matrix_resource_links.c.resource_id, sa.String()).label(
                                "resource_id",
                            ),
                        ),
                    )
                )
                .mappings()
                .one()
            )

        assert article_row == article_id.hex
        assert contact_row == contact_id.hex
        migration_asserts.hex_id(tag_row)
        assert link_row["article_id"] == article_id.hex
        assert link_row["tag_id"] == tag_row
        migration_asserts.hex_id(matrix_link_row["item_id"])
        migration_asserts.hex_id(matrix_link_row["resource_id"])

    async def test_downgrade_restores_previous_id_shapes_and_preserves_relationships(
        self,
        engine: AsyncEngine,
        migrated_to_0001: None,
    ) -> None:
        _ = migrated_to_0001
        article_id = uuid.UUID("10000000-0000-4000-8000-000000000001")
        contact_id = uuid.UUID("10000000-0000-4000-8000-000000000002")

        async with engine.begin() as connection:
            await insert_0001_rows(
                connection=connection,
                article_id=article_id,
                contact_id=contact_id,
            )

        migrate(revision="0002")
        downgrade(revision="0001")

        async with engine.connect() as connection:
            article_row = (
                await connection.execute(
                    sa.select(articles.c.id).where(articles.c.slug == "migration-article"),
                )
            ).scalar_one()
            tag_row = (
                await connection.execute(sa.select(tags.c.id).where(tags.c.slug == "migration-tag"))
            ).scalar_one()
            contact_row = (await connection.execute(sa.select(contacts.c.id))).scalar_one()
            link_row = (
                (
                    await connection.execute(
                        sa.select(article_tags.c.article_id, article_tags.c.tag_id),
                    )
                )
                .mappings()
                .one()
            )
            matrix_link_row = (
                (
                    await connection.execute(
                        sa.select(
                            matrix_resource_links.c.item_id,
                            matrix_resource_links.c.resource_id,
                        ),
                    )
                )
                .mappings()
                .one()
            )

        assert article_row == article_id
        assert contact_row == contact_id
        assert isinstance(tag_row, int)
        assert link_row["article_id"] == article_id
        assert link_row["tag_id"] == tag_row
        assert isinstance(matrix_link_row["item_id"], int)
        assert isinstance(matrix_link_row["resource_id"], int)


async def insert_0001_rows(
    *,
    connection: AsyncConnection,
    article_id: uuid.UUID,
    contact_id: uuid.UUID,
) -> None:
    await connection.execute(
        articles.insert().values(
            id=article_id,
            slug="migration-article",
            title_ru="Миграция",
            title_en="Migration",
            content_ru="Текст",
            content_en="Text",
            folder_ru="База",
            folder_en="Database",
            author_username="admin",
            publish_status="PUBLISHED",
        ),
    )
    await connection.execute(
        tags.insert().values(id=11, name_ru="Тег", name_en="Tag", slug="migration-tag"),
    )
    await connection.execute(
        article_tags.insert().values(id=21, article_id=article_id, tag_id=11),
    )
    await connection.execute(
        article_analytics.insert().values(
            id=31,
            article_id=article_id,
            date=date(2026, 1, 1),
            source_category="DIRECT",
            view_count=3,
            engaged_view_count=2,
        ),
    )
    await connection.execute(
        article_reactions.insert().values(
            id=41,
            article_id=article_id,
            article_scoped_voter_hash="a" * 64,
            reaction_kind="HEART",
        ),
    )
    await connection.execute(
        contacts.insert().values(
            id=contact_id,
            name="Dmitriy",
            email="dmitriy@example.com",
            telegram="@dmitriy",
            message="Hello",
        ),
    )
    await connection.execute(
        resumes.insert().values(
            id=51,
            title="Resume",
            language="RU",
            author_username="admin",
            content={"profile": {"full_name": "Dmitriy"}},
        ),
    )
    await connection.execute(
        matrix_sheets.insert().values(
            id=101,
            key="python",
            name_ru="Питон",
            name_en="Python",
            priority=1,
        ),
    )
    await connection.execute(
        matrix_sections.insert().values(
            id=111,
            sheet_id=101,
            name_ru="Основы",
            name_en="Basics",
            priority=1,
        ),
    )
    await connection.execute(
        matrix_subsections.insert().values(
            id=121,
            section_id=111,
            name_ru="Функции",
            name_en="Functions",
            priority=1,
        ),
    )
    await connection.execute(
        matrix_items.insert().values(
            id=131,
            slug="migration-question",
            question_ru="Вопрос?",
            question_en="Question?",
            answer_ru="Ответ",
            answer_en="Answer",
            interview_expected_answer_ru="Ожидаемый ответ",
            interview_expected_answer_en="Expected answer",
            subsection_id=121,
            grade="JUNIOR",
            interview_frequency="OFTEN",
            publish_status="PUBLISHED",
        ),
    )
    await connection.execute(
        matrix_resources.insert().values(
            id=141,
            name_ru="Документация",
            name_en="Documentation",
            url="https://example.com",
        ),
    )
    await connection.execute(
        matrix_resource_links.insert().values(
            id=151,
            item_id=131,
            resource_id=141,
            context_ru="Контекст",
            context_en="Context",
        ),
    )
    await connection.execute(
        queued_questions.insert().values(
            id=161,
            question="Queued?",
            grade="JUNIOR",
            sheet="Python",
            section="Basics",
            subsection="Functions",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        ),
    )
