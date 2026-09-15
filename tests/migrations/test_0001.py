import sqlalchemy as sa
from argon2 import PasswordHasher
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.config.settings import Settings
from infra.postgresql.utils import downgrade

user_table = sa.table(
    "auth__user_model",
    sa.column("username", sa.String()),
    sa.column("password_hash", sa.String()),
    sa.column("role"),
    sa.column("is_active", sa.Boolean()),
)
pg_class_table = sa.table(
    "pg_class",
    sa.column("relname", sa.String()),
    sa.column("relnamespace", sa.Integer()),
)
pg_namespace_table = sa.table(
    "pg_namespace",
    sa.column("oid", sa.Integer()),
    sa.column("nspname", sa.String()),
)
pg_type_table = sa.table(
    "pg_type",
    sa.column("typname", sa.String()),
    sa.column("typnamespace", sa.Integer()),
)


class TestMigration0001:
    async def test_upgrade_creates_configured_owner(
        self,
        engine: AsyncEngine,
        test_settings: Settings,
        migrated_to_0001: None,
    ) -> None:
        _ = migrated_to_0001
        owner_settings = test_settings.owner
        async with engine.connect() as connection:
            result = await connection.execute(
                sa.select(
                    user_table.c.username,
                    user_table.c.password_hash,
                    sa.cast(user_table.c.role, sa.String()).label("role"),
                    user_table.c.is_active,
                ).where(user_table.c.username == owner_settings.init_login),
            )
            owner = result.mappings().one()

        assert owner["username"] == owner_settings.init_login
        assert owner["role"] == "OWNER"
        assert owner["is_active"] is True
        assert PasswordHasher().verify(
            owner["password_hash"],
            owner_settings.init_password.get_secret_value(),
        )

    async def test_downgrade_removes_initial_auth_schema(
        self,
        engine: AsyncEngine,
        migrated_to_0001: None,
    ) -> None:
        _ = migrated_to_0001
        downgrade(revision="base")

        async with engine.connect() as connection:
            user_table_result = await connection.execute(
                sa.select(pg_class_table.c.relname)
                .select_from(
                    pg_class_table.join(
                        pg_namespace_table,
                        pg_class_table.c.relnamespace == pg_namespace_table.c.oid,
                    ),
                )
                .where(
                    pg_class_table.c.relname == "auth__user_model",
                    pg_namespace_table.c.nspname == "public",
                ),
            )
            role_type_result = await connection.execute(
                sa.select(pg_type_table.c.typname)
                .select_from(
                    pg_type_table.join(
                        pg_namespace_table,
                        pg_type_table.c.typnamespace == pg_namespace_table.c.oid,
                    ),
                )
                .where(
                    pg_type_table.c.typname == "role_enum",
                    pg_namespace_table.c.nspname == "public",
                ),
            )

        assert user_table_result.scalar_one_or_none() is None
        assert role_type_result.scalar_one_or_none() is None
