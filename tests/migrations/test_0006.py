from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
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
    sa.column("is_revoked", sa.Boolean()),
)


class TestMigration0006:
    async def test_upgrade_adds_auth_sessions_with_unique_hash_and_user_cascade(
        self,
        engine: AsyncEngine,
        migrated_to_0005: None,
    ) -> None:
        _ = migrated_to_0005
        expires_at = datetime(2026, 8, 7, tzinfo=UTC)
        async with engine.begin() as connection:
            await connection.execute(
                users.insert().values(
                    username="admin",
                    password_hash=stored_hash_value,
                    role="ADMIN",
                    is_active=True,
                ),
            )

        migrate(revision="0006")

        async with engine.begin() as connection:
            await connection.execute(
                auth_sessions.insert().values(
                    id="10000000000040008000000000000001",
                    username="admin",
                    secret_hash="a" * 64,
                    expires_at=expires_at,
                    is_revoked=False,
                ),
            )
            queried_id = await connection.scalar(
                sa.select(auth_sessions.c.id).where(auth_sessions.c.secret_hash == "a" * 64),
            )
            await connection.execute(sa.delete(users).where(users.c.username == "admin"))
            session_count = await connection.scalar(sa.select(sa.func.count(auth_sessions.c.id)))

        assert queried_id == "10000000000040008000000000000001"
        assert session_count == 0

    async def test_upgrade_rejects_duplicate_session_secret_hashes(
        self,
        engine: AsyncEngine,
        migrated_to_0005: None,
    ) -> None:
        _ = migrated_to_0005
        async with engine.begin() as connection:
            await connection.execute(
                users.insert().values(
                    username="moderator",
                    password_hash=stored_hash_value,
                    role="MODERATOR",
                    is_active=True,
                ),
            )

        migrate(revision="0006")

        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    auth_sessions.insert(),
                    [
                        {
                            "id": "10000000000040008000000000000002",
                            "username": "moderator",
                            "secret_hash": "b" * 64,
                            "expires_at": datetime(2026, 7, 8, tzinfo=UTC) + timedelta(days=30),
                            "is_revoked": False,
                        },
                        {
                            "id": "10000000000040008000000000000003",
                            "username": "moderator",
                            "secret_hash": "b" * 64,
                            "expires_at": datetime(2026, 7, 8, tzinfo=UTC) + timedelta(days=30),
                            "is_revoked": False,
                        },
                    ],
                )

    async def test_downgrade_drops_auth_sessions_table(
        self,
        engine: AsyncEngine,
        migrated_to_0005: None,
    ) -> None:
        _ = migrated_to_0005
        migrate(revision="0006")
        downgrade(revision="0005")

        async with engine.begin() as connection:
            has_table = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).has_table(
                    "auth__auth_session_model",
                ),
            )

        assert not has_table
