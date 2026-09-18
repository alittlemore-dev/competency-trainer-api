import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.postgresql.utils import downgrade, migrate

users = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
)


async def test_initial_schema_does_not_create_owner_from_legacy_environment(
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OWNER_INIT_LOGIN", "legacy-owner")
    monkeypatch.setenv("OWNER_INIT_PASSWORD", "legacy-password")

    try:
        migrate(revision="0001")
        async with engine.connect() as connection:
            usernames = (await connection.execute(sa.select(users.c.username))).scalars().all()
        downgrade(revision="base")
        async with engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: sa.inspect(sync_connection).get_table_names()
            )
    finally:
        downgrade(revision="base")

    assert usernames == []
    assert set(table_names) == {"alembic_version"}
