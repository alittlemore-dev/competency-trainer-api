from datetime import UTC, datetime, timedelta
from typing import Protocol, TypedDict, cast

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

REMOVED_TABLES = {"auth__auth_session_model", "auth__user_model"}
REMOVED_ENUMS = {
    "auth_session_auth_method_enum",
    "auth_session_device_type_enum",
    "role_enum",
}
LEGACY_STORED_HASH = "legacy-password-hash"

role_enum = postgresql.ENUM(
    "ANON",
    "USER",
    "MODERATOR",
    "ADMIN",
    "OWNER",
    name="role_enum",
    create_type=False,
)
auth_method_enum = postgresql.ENUM(
    "PASSWORD",
    name="auth_session_auth_method_enum",
    create_type=False,
)
device_type_enum = postgresql.ENUM(
    "DESKTOP",
    "MOBILE",
    "TABLET",
    "BOT",
    "UNKNOWN",
    name="auth_session_device_type_enum",
    create_type=False,
)
users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
    sa.column("password_hash", sa.String()),
    sa.column("role", role_enum),
    sa.column("is_active", sa.Boolean()),
)
auth_sessions = sa.table(
    "auth__auth_session_model",
    sa.column("id", sa.String()),
    sa.column("username", sa.String()),
    sa.column("secret_hash", sa.String()),
    sa.column("expires_at", sa.DateTime(timezone=True)),
    sa.column("absolute_expires_at", sa.DateTime(timezone=True)),
    sa.column("is_revoked", sa.Boolean()),
    sa.column("last_used_at", sa.DateTime(timezone=True)),
    sa.column("auth_method", auth_method_enum),
    sa.column("user_agent_display", sa.String()),
    sa.column("user_agent_browser", sa.String()),
    sa.column("user_agent_os", sa.String()),
    sa.column("user_agent_device", device_type_enum),
)


class ReflectedEnum(TypedDict):
    name: str
    labels: list[str]


class PostgreSQLInspector(Protocol):
    def get_enums(self) -> list[ReflectedEnum]: ...


def database_enum_names(connection: Connection) -> set[str]:
    inspector = cast("PostgreSQLInspector", sa.inspect(connection))
    return {enum["name"] for enum in inspector.get_enums()}


def legacy_schema(connection: Connection) -> dict[str, dict[str, object]]:
    inspector = sa.inspect(connection)
    return {
        table_name: {
            "columns": tuple(
                (column["name"], str(column["type"]), column["nullable"])
                for column in inspector.get_columns(table_name)
            ),
            "primary_key": tuple(inspector.get_pk_constraint(table_name)["constrained_columns"]),
            "indexes": tuple(
                sorted(
                    (
                        index["name"],
                        index["unique"],
                        tuple(index["column_names"]),
                        tuple(index.get("expressions", ())),
                    )
                    for index in inspector.get_indexes(table_name)
                ),
            ),
        }
        for table_name in REMOVED_TABLES
    }


async def seed_legacy_auth_data(engine: AsyncEngine) -> None:
    now = datetime(2026, 9, 16, tzinfo=UTC)
    async with engine.begin() as connection:
        await connection.execute(
            users.insert().values(
                username="legacy-owner",
                password_hash=LEGACY_STORED_HASH,
                role="OWNER",
                is_active=True,
            ),
        )
        await connection.execute(
            auth_sessions.insert().values(
                id="19000000000000000000000000000001",
                username="legacy-owner",
                secret_hash="a" * 64,
                expires_at=now + timedelta(days=1),
                absolute_expires_at=now + timedelta(days=30),
                is_revoked=False,
                last_used_at=now,
                auth_method="PASSWORD",
                user_agent_display="Browser on OS",
                user_agent_browser="Browser",
                user_agent_os="OS",
                user_agent_device="DESKTOP",
            ),
        )


class TestMigration0019:
    async def test_upgrade_drops_auth_data_and_downgrade_restores_empty_schema(
        self,
        engine: AsyncEngine,
        migrated_to_0018: None,
    ) -> None:
        _ = migrated_to_0018
        async with engine.connect() as connection:
            schema_before = await connection.run_sync(legacy_schema)
        await seed_legacy_auth_data(engine)

        migrate(revision="0019")

        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: set(sa.inspect(sync_connection).get_table_names()),
            )
            enum_names = await connection.run_sync(database_enum_names)
        assert not REMOVED_TABLES & table_names
        assert not REMOVED_ENUMS & enum_names

        downgrade(revision="0018")

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
        assert row_counts == dict.fromkeys(REMOVED_TABLES, 0)
