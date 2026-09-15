from collections.abc import Collection
from datetime import UTC, datetime, timedelta
from typing import Protocol, TypedDict, cast

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.interfaces import ReflectedForeignKeyConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate


class ReflectedEnum(TypedDict):
    name: str
    labels: list[str]


class PostgreSQLInspector(Protocol):
    def get_enums(self) -> list[ReflectedEnum]: ...


CLIENT_TABLE = "agent_access__agent_client_model"
CERTIFICATE_TABLE = "agent_access__agent_certificate_model"
CLAIM_TABLE = "agent_access__matrix_question_claim_model"
AUDIT_TABLE = "agent_access__agent_audit_event_model"
COMPLETION_TABLE = "agent_access__matrix_question_draft_completion_model"
ROTATION_TABLE = "agent_access__agent_certificate_rotation_model"

client_status_enum = postgresql.ENUM(
    "ACTIVE",
    "REVOKED",
    name="agent_client_status_enum",
    create_type=False,
)
agent_scope_enum = postgresql.ENUM(
    "MATRIX_QUEUE_CLAIM",
    "MATRIX_CONTEXT_READ",
    "MATRIX_RESOURCES_READ",
    "MATRIX_DRAFT_CREATE",
    name="agent_scope_enum",
    create_type=False,
)

clients = sa.table(
    CLIENT_TABLE,
    sa.column("id", sa.String(length=32)),
    sa.column("name", sa.String(length=255)),
    sa.column("status", client_status_enum),
    sa.column("scopes", postgresql.ARRAY(agent_scope_enum)),
    sa.column("created_at", postgresql.TIMESTAMP(timezone=True)),
    sa.column("revoked_at", postgresql.TIMESTAMP(timezone=True)),
)
certificates = sa.table(
    CERTIFICATE_TABLE,
    sa.column("id", sa.String(length=32)),
    sa.column("agent_client_id", sa.String(length=32)),
    sa.column("fingerprint_sha256", sa.String(length=64)),
    sa.column("serial_number", sa.String(length=64)),
    sa.column("certificate_pem", sa.Text()),
    sa.column("valid_from", postgresql.TIMESTAMP(timezone=True)),
    sa.column("expires_at", postgresql.TIMESTAMP(timezone=True)),
    sa.column("created_at", postgresql.TIMESTAMP(timezone=True)),
    sa.column("revoked_at", postgresql.TIMESTAMP(timezone=True)),
)
completions = sa.table(
    COMPLETION_TABLE,
    sa.column("claim_id", sa.String(length=32)),
    sa.column("agent_client_id", sa.String(length=32)),
    sa.column("queue_item_id", sa.String(length=32)),
    sa.column("matrix_item_id", sa.String(length=32)),
    sa.column("input_digest", sa.String(length=64)),
    sa.column("completed_at", postgresql.TIMESTAMP(timezone=True)),
)
rotations = sa.table(
    ROTATION_TABLE,
    sa.column("rotation_id", sa.String(length=255)),
    sa.column("agent_client_id", sa.String(length=32)),
    sa.column("current_certificate_id", sa.String(length=32)),
    sa.column("replacement_certificate_id", sa.String(length=32)),
    sa.column("csr_digest", sa.String(length=64)),
    sa.column("created_at", postgresql.TIMESTAMP(timezone=True)),
    sa.column("normal_access_until", postgresql.TIMESTAMP(timezone=True)),
    sa.column("confirmed_at", postgresql.TIMESTAMP(timezone=True)),
)


class TestMigration0012:
    async def test_upgrade_creates_final_agent_access_schema(
        self,
        engine: AsyncEngine,
        migrated_to_0011: None,
    ) -> None:
        _ = migrated_to_0011

        migrate(revision="0012")

        async with engine.begin() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: set(
                    sa.inspect(sync_connection).get_table_names(),
                ),
            )
            reflected_enums = await connection.run_sync(
                lambda sync_connection: {
                    enum["name"]: enum["labels"]
                    for enum in cast(
                        "PostgreSQLInspector",
                        sa.inspect(sync_connection),
                    ).get_enums()
                },
            )
            audit_columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column
                    for column in sa.inspect(sync_connection).get_columns(AUDIT_TABLE)
                },
            )
            completion_foreign_keys = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_foreign_keys(
                    COMPLETION_TABLE,
                ),
            )
            completion_primary_key = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_pk_constraint(
                    COMPLETION_TABLE,
                ),
            )
            rotation_foreign_keys = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_foreign_keys(
                    ROTATION_TABLE,
                ),
            )
            rotation_indexes = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_indexes(
                    ROTATION_TABLE,
                ),
            )

        assert {
            CLIENT_TABLE,
            CERTIFICATE_TABLE,
            CLAIM_TABLE,
            AUDIT_TABLE,
            COMPLETION_TABLE,
            ROTATION_TABLE,
        } <= tables
        assert {
            "agent_client_status_enum",
            "agent_scope_enum",
            "agent_action_enum",
            "agent_audit_result_enum",
        } <= reflected_enums.keys()
        assert "agent_tool_enum" not in reflected_enums
        assert set(reflected_enums["agent_action_enum"]) == {
            "CLAIM_NEXT_MATRIX_QUESTION",
            "GET_MATRIX_AUTHORING_CONTEXT",
            "SEARCH_MATRIX_RESOURCES",
            "SAVE_MATRIX_QUESTION_DRAFT",
            "RELEASE_MATRIX_QUESTION_CLAIM",
            "ROTATE_AGENT_CERTIFICATE",
            "CONFIRM_AGENT_CERTIFICATE_ROTATION",
        }
        assert "action" in audit_columns
        assert "tool" not in audit_columns
        assert audit_columns["certificate_id"]["nullable"] is False
        assert completion_primary_key["constrained_columns"] == ["claim_id"]
        assert self._foreign_key_targets(completion_foreign_keys) == {
            ("agent_client_id", CLIENT_TABLE, "id"),
        }
        assert self._foreign_key_targets(rotation_foreign_keys) == {
            ("agent_client_id", CLIENT_TABLE, "id"),
            ("current_certificate_id", CERTIFICATE_TABLE, "id"),
            ("replacement_certificate_id", CERTIFICATE_TABLE, "id"),
        }
        pending_index = next(
            index
            for index in rotation_indexes
            if index["name"] == "agent_certificate_rotation_pending_current_uniq"
        )
        assert pending_index["unique"] is True
        assert pending_index["column_names"] == ["current_certificate_id"]
        assert "confirmed_at IS NULL" in str(
            pending_index["dialect_options"]["postgresql_where"],
        )

    async def test_completion_and_rotation_constraints_preserve_idempotency_state(
        self,
        engine: AsyncEngine,
        migrated_to_0011: None,
    ) -> None:
        _ = migrated_to_0011
        migrate(revision="0012")
        client_id = "1" * 32
        current_certificate_id = "2" * 32
        first_replacement_id = "3" * 32
        second_replacement_id = "4" * 32
        created_at = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)

        async with engine.begin() as connection:
            await connection.execute(
                sa.insert(clients).values(
                    id=client_id,
                    name="desktop-codex",
                    status="ACTIVE",
                    scopes=["MATRIX_DRAFT_CREATE"],
                    created_at=created_at,
                    revoked_at=None,
                ),
            )
            await connection.execute(
                sa.insert(certificates),
                [
                    {
                        "id": current_certificate_id,
                        "agent_client_id": client_id,
                        "fingerprint_sha256": "a" * 64,
                        "serial_number": "01",
                        "certificate_pem": "current-public-certificate",
                        "valid_from": created_at,
                        "expires_at": created_at + timedelta(days=1),
                        "created_at": created_at,
                        "revoked_at": None,
                    },
                    {
                        "id": first_replacement_id,
                        "agent_client_id": client_id,
                        "fingerprint_sha256": "b" * 64,
                        "serial_number": "02",
                        "certificate_pem": "first-replacement-public-certificate",
                        "valid_from": created_at,
                        "expires_at": created_at + timedelta(days=1),
                        "created_at": created_at,
                        "revoked_at": None,
                    },
                    {
                        "id": second_replacement_id,
                        "agent_client_id": client_id,
                        "fingerprint_sha256": "c" * 64,
                        "serial_number": "03",
                        "certificate_pem": "second-replacement-public-certificate",
                        "valid_from": created_at,
                        "expires_at": created_at + timedelta(days=1),
                        "created_at": created_at,
                        "revoked_at": None,
                    },
                ],
            )
            await connection.execute(
                sa.insert(completions).values(
                    claim_id="5" * 32,
                    agent_client_id=client_id,
                    queue_item_id="6" * 32,
                    matrix_item_id="7" * 32,
                    input_digest="d" * 64,
                    completed_at=created_at,
                ),
            )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        sa.insert(completions).values(
                            claim_id="5" * 32,
                            agent_client_id=client_id,
                            queue_item_id="8" * 32,
                            matrix_item_id="9" * 32,
                            input_digest="e" * 64,
                            completed_at=created_at,
                        ),
                    )
            await connection.execute(
                sa.insert(rotations).values(
                    rotation_id="rotation-1",
                    agent_client_id=client_id,
                    current_certificate_id=current_certificate_id,
                    replacement_certificate_id=first_replacement_id,
                    csr_digest="f" * 64,
                    created_at=created_at,
                    normal_access_until=created_at + timedelta(minutes=15),
                    confirmed_at=None,
                ),
            )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        sa.insert(rotations).values(
                            rotation_id="rotation-2",
                            agent_client_id=client_id,
                            current_certificate_id=current_certificate_id,
                            replacement_certificate_id=second_replacement_id,
                            csr_digest="0" * 64,
                            created_at=created_at,
                            normal_access_until=created_at + timedelta(minutes=15),
                            confirmed_at=None,
                        ),
                    )
            await connection.execute(
                sa.update(rotations)
                .where(rotations.c.rotation_id == "rotation-1")
                .values(confirmed_at=created_at + timedelta(minutes=1)),
            )
            await connection.execute(
                sa.insert(rotations).values(
                    rotation_id="rotation-2",
                    agent_client_id=client_id,
                    current_certificate_id=current_certificate_id,
                    replacement_certificate_id=second_replacement_id,
                    csr_digest="0" * 64,
                    created_at=created_at,
                    normal_access_until=created_at + timedelta(minutes=15),
                    confirmed_at=None,
                ),
            )

    async def test_downgrade_removes_agent_schema_and_native_enums(
        self,
        engine: AsyncEngine,
        migrated_to_0011: None,
    ) -> None:
        _ = migrated_to_0011
        migrate(revision="0012")

        downgrade(revision="0011")

        async with engine.begin() as connection:
            tables = await connection.run_sync(
                lambda sync_connection: set(
                    sa.inspect(sync_connection).get_table_names(),
                ),
            )
            enums = await connection.run_sync(
                lambda sync_connection: {
                    enum["name"]
                    for enum in cast(
                        "PostgreSQLInspector",
                        sa.inspect(sync_connection),
                    ).get_enums()
                },
            )

        assert (
            not {
                CLIENT_TABLE,
                CERTIFICATE_TABLE,
                CLAIM_TABLE,
                AUDIT_TABLE,
                COMPLETION_TABLE,
                ROTATION_TABLE,
            }
            & tables
        )
        assert (
            not {
                "agent_client_status_enum",
                "agent_scope_enum",
                "agent_action_enum",
                "agent_audit_result_enum",
            }
            & enums
        )

    def _foreign_key_targets(
        self,
        foreign_keys: Collection[ReflectedForeignKeyConstraint],
    ) -> set[tuple[str, str, str]]:
        return {
            (
                foreign_key["constrained_columns"][0],
                foreign_key["referred_table"],
                foreign_key["referred_columns"][0],
            )
            for foreign_key in foreign_keys
        }
