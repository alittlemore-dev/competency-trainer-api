from datetime import UTC, datetime, timedelta

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

auth_sessions_0006 = sa.table(
    "auth__auth_session_model",
    sa.column("id", sa.String()),
    sa.column("username", sa.String()),
    sa.column("secret_hash", sa.String()),
    sa.column("expires_at", sa.DateTime(timezone=True)),
    sa.column("is_revoked", sa.Boolean()),
)

auth_sessions_0007 = sa.table(
    "auth__auth_session_model",
    sa.column("id", sa.String()),
    sa.column("username", sa.String()),
    sa.column("secret_hash", sa.String()),
    sa.column("expires_at", sa.DateTime(timezone=True)),
    sa.column("is_revoked", sa.Boolean()),
    sa.column("last_used_at", sa.DateTime(timezone=True)),
    sa.column("auth_method", auth_method_enum),
    sa.column("user_agent_display", sa.String()),
    sa.column("user_agent_browser", sa.String()),
    sa.column("user_agent_os", sa.String()),
    sa.column("user_agent_device", device_type_enum),
)


class TestMigration0007:
    async def test_upgrade_clears_existing_sessions_and_requires_safe_metadata(
        self,
        engine: AsyncEngine,
        migrated_to_0006: None,
    ) -> None:
        _ = migrated_to_0006
        now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
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
                auth_sessions_0006.insert().values(
                    id="10000000000040008000000000000001",
                    username="admin",
                    secret_hash="a" * 64,
                    expires_at=now + timedelta(days=30),
                    is_revoked=False,
                ),
            )

        migrate(revision="0007")

        async with engine.begin() as connection:
            session_count = await connection.scalar(
                sa.select(sa.func.count(auth_sessions_0007.c.id)),
            )
            await connection.execute(
                auth_sessions_0007.insert().values(
                    id="20000000000040008000000000000002",
                    username="admin",
                    secret_hash="b" * 64,
                    expires_at=now + timedelta(days=30),
                    is_revoked=False,
                    last_used_at=now,
                    auth_method="PASSWORD",
                    user_agent_display="Firefox on Linux",
                    user_agent_browser="Firefox",
                    user_agent_os="Linux",
                    user_agent_device="DESKTOP",
                ),
            )
            stored_display = await connection.scalar(
                sa.select(auth_sessions_0007.c.user_agent_display).where(
                    auth_sessions_0007.c.id == "20000000000040008000000000000002",
                ),
            )

        assert session_count == 0
        assert stored_display == "Firefox on Linux"

    async def test_downgrade_removes_session_metadata_columns(
        self,
        engine: AsyncEngine,
        migrated_to_0006: None,
    ) -> None:
        _ = migrated_to_0006
        migrate(revision="0007")
        downgrade(revision="0006")

        async with engine.begin() as connection:
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column["name"]
                    for column in sa.inspect(sync_connection).get_columns(
                        "auth__auth_session_model",
                    )
                },
            )

        assert "last_used_at" not in columns
        assert "auth_method" not in columns
        assert "user_agent_display" not in columns
        assert "user_agent_browser" not in columns
        assert "user_agent_os" not in columns
        assert "user_agent_device" not in columns
