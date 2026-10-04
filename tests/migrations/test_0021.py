from datetime import UTC, datetime, timedelta
from typing import cast

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql.base import PGInspector
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from infra.postgresql.utils import downgrade, migrate

AGENT_TABLES = {
    "agent_access__agent_client_model",
    "agent_access__agent_certificate_model",
    "agent_access__agent_certificate_rotation_model",
    "agent_access__matrix_question_claim_model",
    "agent_access__matrix_question_draft_completion_model",
    "agent_access__agent_audit_event_model",
}
AGENT_ENUMS = {
    "agent_client_status_enum",
    "agent_scope_enum",
    "agent_action_enum",
    "agent_audit_result_enum",
}
QUEUE_TABLE = "competency_matrix__queued_question_model"
ITEM_TABLE = "competency_matrix__competency_matrix_item_model"
ID = f"{1:032x}"
NOW = datetime(2026, 10, 4, 12, 0, tzinfo=UTC)


def seed_retirement_records(connection: Connection) -> None:
    metadata = sa.MetaData()
    metadata.reflect(connection)
    tables = metadata.tables
    connection.execute(
        tables["competency_matrix__competency_matrix_sheet_model"]
        .insert()
        .values(
            id=ID,
            key="python",
            name_ru="Питон",
            name_en="Python",
            priority=1,
        ),
    )
    connection.execute(
        tables["competency_matrix__competency_matrix_section_model"]
        .insert()
        .values(
            id=ID,
            sheet_id=ID,
            name_ru="Основы",
            name_en="Basics",
            priority=1,
        ),
    )
    connection.execute(
        tables["competency_matrix__competency_matrix_subsection_model"]
        .insert()
        .values(
            id=ID,
            section_id=ID,
            name_ru="Синтаксис",
            name_en="Syntax",
            priority=1,
        ),
    )
    connection.execute(
        tables[QUEUE_TABLE]
        .insert()
        .values(
            id=ID,
            question="Queued question survives",
            question_fingerprint=b"q" * 32,
            suggested_by_username="editor",
            sheet="python",
            created_at=NOW,
        ),
    )
    connection.execute(
        tables[ITEM_TABLE]
        .insert()
        .values(
            id=ID,
            sheet_id=ID,
            subsection_id=ID,
            slug="retained-agent-draft",
            question_ru="Сохранённый черновик",
            question_en="Retained draft",
            question_ru_fingerprint=b"r" * 32,
            question_en_fingerprint=b"e" * 32,
            answer_ru="Ответ",
            answer_en="Answer",
            interview_answer_explanation_ru="",
            interview_answer_explanation_en="",
            suggested_by_username="legacy-machine",
            publish_status="DRAFT",
        ),
    )
    connection.execute(
        tables["agent_access__agent_client_model"]
        .insert()
        .values(
            id=ID,
            name="retired-machine",
            status="ACTIVE",
            scopes=["MATRIX_DRAFT_CREATE"],
            created_at=NOW,
            revoked_at=None,
        ),
    )
    for number in (1, 2):
        connection.execute(
            tables["agent_access__agent_certificate_model"]
            .insert()
            .values(
                id=f"{number:032x}",
                agent_client_id=ID,
                fingerprint_sha256=str(number) * 64,
                serial_number=str(number),
                certificate_pem="non-secret-test-certificate",
                valid_from=NOW,
                expires_at=NOW + timedelta(days=90),
                created_at=NOW,
                revoked_at=None,
            ),
        )
    connection.execute(
        tables["agent_access__agent_certificate_rotation_model"]
        .insert()
        .values(
            rotation_id="pending-rotation",
            agent_client_id=ID,
            current_certificate_id=ID,
            replacement_certificate_id=f"{2:032x}",
            csr_digest="a" * 64,
            created_at=NOW,
            normal_access_until=NOW + timedelta(minutes=15),
            confirmed_at=None,
        ),
    )
    connection.execute(
        tables["agent_access__matrix_question_claim_model"]
        .insert()
        .values(
            id=ID,
            agent_client_id=ID,
            queue_item_id=ID,
            claimed_at=NOW,
            expires_at=NOW + timedelta(hours=2),
        ),
    )
    connection.execute(
        tables["agent_access__matrix_question_draft_completion_model"]
        .insert()
        .values(
            claim_id=f"{3:032x}",
            agent_client_id=ID,
            queue_item_id=f"{4:032x}",
            matrix_item_id=ID,
            input_digest="b" * 64,
            completed_at=NOW,
        ),
    )
    connection.execute(
        tables["agent_access__agent_audit_event_model"]
        .insert()
        .values(
            id=ID,
            agent_client_id=ID,
            certificate_id=ID,
            action="SAVE_MATRIX_QUESTION_DRAFT",
            queue_item_id=f"{4:032x}",
            matrix_item_id=ID,
            request_id="retired-request",
            result="SUCCESS",
            input_digest="b" * 64,
            created_at=NOW,
        ),
    )


async def retained_records(connection: AsyncConnection) -> tuple[object, object]:
    metadata = sa.MetaData()
    await connection.run_sync(metadata.reflect)
    return (
        (await connection.execute(sa.select(metadata.tables[QUEUE_TABLE]))).mappings().one(),
        (await connection.execute(sa.select(metadata.tables[ITEM_TABLE]))).mappings().one(),
    )


class TestMigration0021:
    async def test_retirement_preserves_queue_and_drafts_and_downgrade_restores_empty_schema(
        self,
        engine: AsyncEngine,
        migrated_to_0020: None,
    ) -> None:
        _ = migrated_to_0020
        async with engine.begin() as connection:
            await connection.run_sync(seed_retirement_records)
            records_before = await retained_records(connection)
            tables_before = set(
                await connection.run_sync(lambda conn: sa.inspect(conn).get_table_names())
            )
            enums_before = set(
                await connection.run_sync(
                    lambda conn: [
                        enum["name"] for enum in cast("PGInspector", sa.inspect(conn)).get_enums()
                    ]
                )
            )

        migrate(revision="0021")

        async with engine.connect() as connection:
            tables_after = set(
                await connection.run_sync(lambda conn: sa.inspect(conn).get_table_names())
            )
            enums_after = set(
                await connection.run_sync(
                    lambda conn: [
                        enum["name"] for enum in cast("PGInspector", sa.inspect(conn)).get_enums()
                    ]
                )
            )
            assert tables_before - tables_after == AGENT_TABLES
            assert tables_after - tables_before == set()
            assert enums_before - enums_after == AGENT_ENUMS
            assert enums_after - enums_before == set()
            assert await retained_records(connection) == records_before

        downgrade(revision="0020")

        async with engine.connect() as connection:
            assert (
                set(await connection.run_sync(lambda conn: sa.inspect(conn).get_table_names()))
                == tables_before
            )
            assert (
                set(
                    await connection.run_sync(
                        lambda conn: [
                            enum["name"]
                            for enum in cast("PGInspector", sa.inspect(conn)).get_enums()
                        ]
                    )
                )
                == enums_before
            )
            metadata = sa.MetaData()
            await connection.run_sync(metadata.reflect)
            for table_name in AGENT_TABLES:
                assert (
                    await connection.execute(
                        sa.select(sa.func.count()).select_from(metadata.tables[table_name])
                    )
                ).scalar_one() == 0
            assert await retained_records(connection) == records_before

        migrate(revision="0021")
        async with engine.connect() as connection:
            assert await retained_records(connection) == records_before
