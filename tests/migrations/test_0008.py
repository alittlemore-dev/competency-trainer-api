from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.config.settings import Settings
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
stored_hash_value = "not-a-real-password-hash"

users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
    sa.column("password_hash", sa.String()),
    sa.column("role", role_enum),
    sa.column("is_active", sa.Boolean()),
)

auth_sessions_0007 = sa.table(
    "auth__auth_session_model",
    sa.column("id", sa.String()),
    sa.column("username", sa.String()),
    sa.column("secret_hash", sa.String()),
    sa.column("expires_at", sa.DateTime(timezone=True)),
    sa.column("is_revoked", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("last_used_at", sa.DateTime(timezone=True)),
    sa.column("auth_method", auth_method_enum),
    sa.column("user_agent_display", sa.String()),
    sa.column("user_agent_browser", sa.String()),
    sa.column("user_agent_os", sa.String()),
    sa.column("user_agent_device", device_type_enum),
)

auth_sessions_0008 = sa.table(
    "auth__auth_session_model",
    sa.column("id", sa.String()),
    sa.column("absolute_expires_at", sa.DateTime(timezone=True)),
)


class TestMigration0008:
    async def test_upgrade_backfills_absolute_expiry_and_requires_column(
        self,
        engine: AsyncEngine,
        migrated_to_0007: None,
        monkeypatch: pytest.MonkeyPatch,
        test_settings: Settings,
    ) -> None:
        _ = migrated_to_0007
        absolute_ttl_seconds = 7_200
        monkeypatch.setattr(
            test_settings.auth,
            "session_absolute_expire_seconds",
            absolute_ttl_seconds,
        )
        created_at = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
        async with engine.begin() as connection:
            await connection.execute(
                users.insert().values(
                    username="admin",
                    password_hash=stored_hash_value,
                    role="ADMIN",
                    is_active=True,
                ),
            )
            await connection.execute(
                auth_sessions_0007.insert().values(
                    id="10000000000040008000000000000001",
                    username="admin",
                    secret_hash="a" * 64,
                    expires_at=created_at + timedelta(days=30),
                    is_revoked=False,
                    created_at=created_at,
                    last_used_at=created_at,
                    auth_method="PASSWORD",
                    user_agent_display="Firefox on Linux",
                    user_agent_browser="Firefox",
                    user_agent_os="Linux",
                    user_agent_device="DESKTOP",
                ),
            )

        migrate(revision="0008")

        async with engine.begin() as connection:
            stored_absolute_expires_at = await connection.scalar(
                sa.select(auth_sessions_0008.c.absolute_expires_at).where(
                    auth_sessions_0008.c.id == "10000000000040008000000000000001",
                ),
            )
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]: column["nullable"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "auth__auth_session_model",
                    )
                },
            )

        assert stored_absolute_expires_at == created_at + timedelta(seconds=absolute_ttl_seconds)
        assert columns["absolute_expires_at"] is False

    async def test_downgrade_removes_absolute_expiry_column(
        self,
        engine: AsyncEngine,
        migrated_to_0007: None,
    ) -> None:
        _ = migrated_to_0007
        migrate(revision="0008")
        downgrade(revision="0007")

        async with engine.begin() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "auth__auth_session_model",
                    )
                },
            )

        assert "absolute_expires_at" not in columns
