from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.engine.interfaces import ExecutionContext
from sqlalchemy.ext.asyncio import AsyncEngine

from performance.query_plans.models import CapturedQuery, DatabaseParams, PlanExpectation

_QUERY_CAPTURE_START_TIMES_KEY = "query_plan_capture_started_at_ns"


@dataclass(frozen=True, slots=True)
class ActiveCaptureContext:
    storage_class: str
    method_name: str
    scenario_name: str
    expectation: PlanExpectation


class RuntimeQueryCapture:
    def __init__(self, *, clock: Callable[[], int]) -> None:
        self.clock = clock
        self._captured_queries: list[CapturedQuery] = []
        self._active_context: ActiveCaptureContext | None = None
        self._suspend_depth = 0

    @property
    def captured_queries(self) -> tuple[CapturedQuery, ...]:
        return tuple(self._captured_queries)

    def install(self, *, engine: AsyncEngine) -> None:
        @event.listens_for(engine.sync_engine, "before_cursor_execute")
        def before_cursor_execute(  # noqa: PLR0913
            conn: Connection,
            cursor: object,
            statement: str,
            parameters: object,
            context: ExecutionContext | None,
            executemany: object,
        ) -> None:
            self.before_cursor_execute(conn, cursor, statement, parameters, context, executemany)

        @event.listens_for(engine.sync_engine, "after_cursor_execute")
        def after_cursor_execute(  # noqa: PLR0913
            conn: Connection,
            cursor: object,
            statement: str,
            parameters: object,
            context: ExecutionContext | None,
            executemany: object,
        ) -> None:
            self.after_cursor_execute(conn, cursor, statement, parameters, context, executemany)

    def start_scenario(
        self,
        *,
        storage_class: str,
        method_name: str,
        scenario_name: str,
        expectation: PlanExpectation,
    ) -> None:
        self._active_context = ActiveCaptureContext(
            storage_class=storage_class,
            method_name=method_name,
            scenario_name=scenario_name,
            expectation=expectation,
        )

    def stop_scenario(self) -> None:
        self._active_context = None

    @contextmanager
    def suspended(self) -> Iterator[None]:
        self._suspend_depth += 1
        try:
            yield
        finally:
            self._suspend_depth -= 1

    def before_cursor_execute(
        self,
        conn: Connection,
        _cursor: object,
        _statement: str,
        _parameters: object,
        _context: ExecutionContext | None,
        _executemany: object,
    ) -> None:
        if self._active_context is None or self._suspend_depth > 0:
            return
        get_query_start_times(conn=conn).append(self.clock())

    def after_cursor_execute(
        self,
        conn: Connection,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: ExecutionContext | None,
        executemany: object,
    ) -> None:
        active_context = self._active_context
        if active_context is None or self._suspend_depth > 0:
            return
        started_at_ns = pop_query_start_time(conn=conn)
        if started_at_ns is None:
            return
        elapsed_ms = (self.clock() - started_at_ns) / 1_000_000
        ordinal = next_query_ordinal(
            queries=self._captured_queries,
            scenario_name=active_context.scenario_name,
        )
        self._captured_queries.append(
            CapturedQuery(
                name=f"{active_context.scenario_name}__{ordinal:03d}",
                storage_class=active_context.storage_class,
                method_name=active_context.method_name,
                scenario_name=active_context.scenario_name,
                ordinal=ordinal,
                sql=statement,
                normalized_sql=normalize_captured_sql(statement),
                params=representative_parameters(parameters),
                elapsed_ms=elapsed_ms,
                executemany=executemany is True,
                expectation=active_context.expectation,
            ),
        )


def next_query_ordinal(*, queries: Sequence[CapturedQuery], scenario_name: str) -> int:
    return sum(query.scenario_name == scenario_name for query in queries) + 1


def normalize_captured_sql(statement: str) -> str:
    return " ".join(statement.split())


def representative_parameters(parameters: object) -> DatabaseParams:
    if isinstance(parameters, Mapping):
        return {str(key): normalize_database_param(value) for key, value in parameters.items()}
    if isinstance(parameters, Sequence) and not isinstance(parameters, str | bytes | bytearray):
        if len(parameters) == 0:
            return ()
        first_value = parameters[0]
        if isinstance(first_value, Mapping):
            return {str(key): normalize_database_param(value) for key, value in first_value.items()}
        if isinstance(first_value, Sequence) and not isinstance(
            first_value,
            str | bytes | bytearray,
        ):
            return tuple(normalize_database_param(value) for value in first_value)
        return tuple(normalize_database_param(value) for value in parameters)
    return ()


def normalize_database_param(value: object) -> object:
    if isinstance(value, Enum):
        return value.name
    return value


def get_query_start_times(*, conn: Connection) -> list[int]:
    return conn.info.setdefault(_QUERY_CAPTURE_START_TIMES_KEY, [])


def pop_query_start_time(*, conn: Connection) -> int | None:
    query_start_times = get_query_start_times(conn=conn)
    if not query_start_times:
        return None
    return query_start_times.pop()
