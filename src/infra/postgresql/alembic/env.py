from logging.config import fileConfig
from typing import TYPE_CHECKING, TypeAlias

from alembic import context
from sqlalchemy import pool, engine_from_config

from infra.config.settings import settings
from infra.postgresql.models import BaseModel

if TYPE_CHECKING:
    from collections.abc import Iterable

    from alembic.operations.ops import MigrationScript
    from alembic.runtime.migration import MigrationContext

    RevisionType: TypeAlias = str | Iterable[str | None] | Iterable[str]

config = context.config
config.set_main_option("sqlalchemy.url", settings.database.url.get_secret_value())
target_metadata = BaseModel.metadata

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def process_revision_directives(
    context: "MigrationContext",
    revision: "RevisionType",
    directives: list["MigrationScript"],
) -> None:
    migration_script = directives[0]
    head_revision = context.get_current_revision()
    new_rev_id = int(head_revision) + 1 if head_revision else 1
    migration_script.rev_id = f"{new_rev_id:04}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
