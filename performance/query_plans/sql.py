import json
import re
from collections.abc import Sequence
from enum import Enum

from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import AsyncConnection

from performance.query_plans.models import CapturedQuery, CompiledQuery, DatabaseParams

EXPLAIN_PREFIX = "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON) "
INSERTMANYVALUES_SORT_ALIAS_PATTERN = re.compile(
    r"AS (?P<alias>[a-zA-Z_][a-zA-Z0-9_]*)"
    r"\((?P<columns>[^)]*?),\s*sen_counter\)\s+ORDER BY sen_counter",
)


def compile_captured_query(*, query: CapturedQuery, dialect: Dialect) -> CompiledQuery:
    del dialect
    return CompiledQuery(
        name=query.name,
        sql=prepare_explain_sql(query.sql),
        params=normalize_database_params(query.params),
    )


def prepare_explain_sql(sql: str) -> str:
    return INSERTMANYVALUES_SORT_ALIAS_PATTERN.sub(
        lambda match: f"AS {match.group('alias')}({match.group('columns')})",
        sql,
    )


def normalize_database_params(params: DatabaseParams) -> DatabaseParams:
    if isinstance(params, tuple):
        return tuple(normalize_database_param(value) for value in params)
    return {key: normalize_database_param(value) for key, value in params.items()}


def normalize_database_param(value: object) -> object:
    if isinstance(value, Enum):
        return value.name
    return value


async def run_explain(*, connection: AsyncConnection, compiled_query: CompiledQuery) -> object:
    result = await connection.exec_driver_sql(
        f"{EXPLAIN_PREFIX}{compiled_query.sql}",
        compiled_query.params,
    )
    row = result.first()
    if row is None:
        msg = f"EXPLAIN returned no rows for {compiled_query.name}"
        raise RuntimeError(msg)
    raw_plan = row[0]
    return json.loads(raw_plan) if isinstance(raw_plan, str) else raw_plan


def group_queries_by_scenario(
    queries: Sequence[CapturedQuery],
) -> tuple[tuple[CapturedQuery, ...], ...]:
    groups: list[tuple[CapturedQuery, ...]] = []
    current_group: list[CapturedQuery] = []
    current_key: tuple[str, str, str] | None = None
    for query in queries:
        query_key = (query.storage_class, query.method_name, query.scenario_name)
        if current_key is not None and query_key != current_key:
            groups.append(tuple(current_group))
            current_group = []
        current_key = query_key
        current_group.append(query)
    if current_group:
        groups.append(tuple(current_group))
    return tuple(groups)
