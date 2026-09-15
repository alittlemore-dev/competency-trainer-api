from time import perf_counter_ns
from typing import cast

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import ExecutionContext
from sqlalchemy.ext.asyncio import AsyncEngine

from infra.config.loggers import logger

_QUERY_START_TIMES_KEY = "query_monitoring_started_at_ns"
MIN_STATEMENT_MAX_LENGTH = 4
type SlowQueryPayload = dict[str, bool | float | int | str]


def install_query_monitoring(
    *,
    engine: AsyncEngine,
    enabled: bool,
    slow_query_log_threshold_ms: int,
    statement_max_length: int,
) -> None:
    if not enabled:
        return

    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Connection,
        _cursor: object,
        _statement: str,
        _parameters: object,
        _context: ExecutionContext,
        _executemany: object,
    ) -> None:
        get_query_start_times(conn=conn).append(perf_counter_ns())

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Connection,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: ExecutionContext,
        executemany: object,
    ) -> None:
        started_at_ns = pop_query_start_time(conn=conn)
        if started_at_ns is None:
            return
        duration_ms = (perf_counter_ns() - started_at_ns) / 1_000_000
        if not is_slow_query(duration_ms=duration_ms, threshold_ms=slow_query_log_threshold_ms):
            return
        logger.warning(
            "Slow database query",
            **build_slow_query_log_payload(
                statement=statement,
                duration_ms=duration_ms,
                threshold_ms=slow_query_log_threshold_ms,
                statement_max_length=statement_max_length,
                executemany=executemany is True,
            ),
        )


def normalize_sql_statement(statement: str, statement_max_length: int) -> str:
    if statement_max_length < MIN_STATEMENT_MAX_LENGTH:
        msg = "statement_max_length must be at least 4"
        raise ValueError(msg)
    normalized = " ".join(statement.split())
    if len(normalized) <= statement_max_length:
        return normalized
    return f"{normalized[: statement_max_length - 3]}..."


def is_slow_query(*, duration_ms: float, threshold_ms: int) -> bool:
    return duration_ms >= threshold_ms


def build_slow_query_log_payload(
    *,
    statement: str,
    duration_ms: float,
    threshold_ms: int,
    statement_max_length: int,
    executemany: bool,
) -> SlowQueryPayload:
    return {
        "duration_ms": round(duration_ms, 2),
        "threshold_ms": threshold_ms,
        "statement": normalize_sql_statement(statement, statement_max_length),
        "executemany": executemany,
    }


def get_query_start_times(*, conn: Connection) -> list[int]:
    query_start_times = conn.info.setdefault(_QUERY_START_TIMES_KEY, [])
    return cast("list[int]", query_start_times)


def pop_query_start_time(*, conn: Connection) -> int | None:
    query_start_times = get_query_start_times(conn=conn)
    if not query_start_times:
        return None
    return query_start_times.pop()
