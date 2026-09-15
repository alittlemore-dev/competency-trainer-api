from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.pool import NullPool

from infra.config.settings import settings
from scripts.pytest_parallel import build_template_database_name, quote_postgresql_identifier

_TEMPLATE_DATABASE_RUN_ID_ENV = "BACKEND_PYTEST_DB_TEMPLATE_ID"
_RESET_BASE_COMMAND = "reset-base"
_DROP_TEMPLATE_COMMAND = "drop-template"


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {_DROP_TEMPLATE_COMMAND, _RESET_BASE_COMMAND}:
        print("Usage: pytest_databases.py {drop-template|reset-base}", file=sys.stderr)
        return 2

    command = argv[1]
    if command == _DROP_TEMPLATE_COMMAND:
        run_id = os.environ.get(_TEMPLATE_DATABASE_RUN_ID_ENV)
        if run_id is None:
            return 0
        database_name = build_template_database_name(
            base_database_name=settings.database.name,
            run_id=run_id,
        )
    else:
        database_name = settings.database.name

    engine = create_engine(
        _maintenance_database_url(),
        isolation_level="AUTOCOMMIT",
        poolclass=NullPool,
    )
    try:
        if command == _RESET_BASE_COMMAND:
            _reset_database(engine=engine, database_name=database_name)
        else:
            _drop_database(engine=engine, database_name=database_name)
    finally:
        engine.dispose()
    return 0


def _maintenance_database_url() -> URL:
    return URL.create(
        drivername=settings.database.driver,
        username=settings.database.user,
        password=settings.database.password.get_secret_value(),
        host=settings.database.host,
        port=int(settings.database.port),
        database="postgres",
    )


def validate_test_database_name(database_name: str) -> None:
    if not (
        database_name.endswith("_test")
        or "_test_gw" in database_name
        or "_test_template_" in database_name
    ):
        msg = f"Refusing to manage non-test database: {database_name}"
        raise ValueError(msg)


def _reset_database(engine: Engine, database_name: str) -> None:
    validate_test_database_name(database_name)
    with engine.connect() as connection:
        _drop_database_with_connection(connection=connection, database_name=database_name)
        connection.execute(text(f"CREATE DATABASE {quote_postgresql_identifier(database_name)}"))


def _drop_database(engine: Engine, database_name: str) -> None:
    validate_test_database_name(database_name)
    with engine.connect() as connection:
        _drop_database_with_connection(connection=connection, database_name=database_name)


def _drop_database_with_connection(*, connection: Connection, database_name: str) -> None:
    connection.execute(
        text(
            "SELECT pg_terminate_backend(pid) "
            "FROM pg_stat_activity "
            "WHERE datname = :database_name AND pid <> pg_backend_pid()",
        ),
        {"database_name": database_name},
    )
    connection.execute(text(f"DROP DATABASE IF EXISTS {quote_postgresql_identifier(database_name)}"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
