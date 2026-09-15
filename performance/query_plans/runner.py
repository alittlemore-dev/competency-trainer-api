from collections.abc import Sequence
from dataclasses import replace
from statistics import median
from sys import stderr, stdout
from time import perf_counter_ns
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from infra.config.settings import settings
from infra.postgresql.utils import migrate
from performance.query_plans.analysis import analyze_explain_result, evaluate_plan_analysis
from performance.query_plans.baseline import (
    COMMITTED_REALISTIC_BASELINE_PATH,
    effective_execution_threshold_ms,
    load_optional_baseline,
    validate_baseline_query_coverage,
)
from performance.query_plans.discovery import discover_storage_methods
from performance.query_plans.expectations import ABSOLUTE_SLA_POLICY
from performance.query_plans.models import (
    REALISTIC_PROFILE,
    STRESS_PROFILE,
    BenchmarkResult,
    CapturedQuery,
    CliArgs,
    QueryPlanBaseline,
    QueryPlanProfile,
)
from performance.query_plans.reports import write_reports
from performance.query_plans.runtime_capture import RuntimeQueryCapture
from performance.query_plans.scenarios import (
    STORAGE_SCENARIOS,
    StorageScenario,
    coverage_findings,
    evaluate_storage_method_coverage,
)
from performance.query_plans.seed import (
    clear_seeded_tables,
    seed_profile,
    vacuum_analyze_seeded_tables,
)
from performance.query_plans.sql import (
    compile_captured_query,
    group_queries_by_scenario,
    run_explain,
)


async def run_query_plan_profile(args: CliArgs) -> int:
    profile = get_profile(name=args.profile)
    baseline = (
        load_optional_baseline(
            path=COMMITTED_REALISTIC_BASELINE_PATH,
            expected_profile_name=profile.name,
        )
        if profile is REALISTIC_PROFILE
        else None
    )
    ensure_safe_database_name(allow_non_test_db=args.allow_non_test_db)
    migrate(revision="heads")
    engine = create_async_engine(settings.database.url.get_secret_value(), poolclass=NullPool)
    coverage = evaluate_storage_method_coverage(
        discovered_methods=discover_storage_methods(),
        scenarios=STORAGE_SCENARIOS,
    )
    capture_findings: tuple[str, ...] = ()
    try:
        async with engine.begin() as connection:
            await seed_profile(connection=connection, profile=profile)
        async with engine.connect() as connection:
            autocommit_connection = await connection.execution_options(
                isolation_level="AUTOCOMMIT",
            )
            await vacuum_analyze_seeded_tables(connection=autocommit_connection)
        queries, capture_findings = await capture_storage_queries(
            engine=engine,
            scenarios=STORAGE_SCENARIOS,
            profile=profile,
        )
        async with engine.connect() as connection:
            await configure_explain_session(connection=connection, profile=profile)
            results = await benchmark_queries(
                connection=connection,
                queries=queries,
                profile=profile,
                baseline=baseline,
            )
        write_reports(
            report_dir=args.report_dir,
            profile=profile,
            baseline=baseline,
            coverage=coverage,
            results=results,
        )
    finally:
        try:
            await cleanup_seeded_profile(engine=engine)
        finally:
            await engine.dispose()

    findings = (
        *coverage_findings(coverage=coverage),
        *capture_findings,
        *(finding for result in results for finding in result.blocking_findings),
    )
    stdout.write(f"Query plan report written to {args.report_dir}\n")
    if findings:
        stderr.write("\n".join(f"- {finding}" for finding in findings))
        stderr.write("\n")
        return 1 if args.fail_on_finding else 0
    return 0


async def cleanup_seeded_profile(*, engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await clear_seeded_tables(connection=connection)


async def configure_explain_session(
    *,
    connection: AsyncConnection,
    profile: QueryPlanProfile,
) -> None:
    await connection.execute(
        text("SELECT set_config('work_mem', :work_mem, false)"),
        {"work_mem": f"{profile.explain_work_mem_mb}MB"},
    )
    await connection.commit()


async def capture_storage_queries(
    *,
    engine: AsyncEngine,
    scenarios: Sequence[StorageScenario],
    profile: QueryPlanProfile,
) -> tuple[tuple[CapturedQuery, ...], tuple[str, ...]]:
    capture = RuntimeQueryCapture(clock=perf_counter_ns)
    capture.install(engine=engine)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    findings: list[str] = []

    for scenario in scenarios:
        stdout.write(f"Capturing SQL for {scenario.storage_class}.{scenario.method_name}\n")
        previous_query_count = len(capture.captured_queries)
        async with session_factory() as session:
            capture.start_scenario(
                storage_class=scenario.storage_class,
                method_name=scenario.method_name,
                scenario_name=scenario.name,
                expectation=scenario.plan_expectation(
                    policy=ABSOLUTE_SLA_POLICY,
                    query_name=None,
                    profile=profile,
                ),
            )
            try:
                await scenario.run(session)
            finally:
                capture.stop_scenario()
                await session.rollback()
        captured_count = len(capture.captured_queries) - previous_query_count
        if captured_count == 0:
            findings.append(f"{scenario.name}: storage scenario captured no SQL statements")

    return (
        apply_query_threshold_overrides(
            queries=capture.captured_queries,
            scenarios=scenarios,
            profile=profile,
        ),
        tuple(findings),
    )


def apply_query_threshold_overrides(
    *,
    queries: Sequence[CapturedQuery],
    scenarios: Sequence[StorageScenario],
    profile: QueryPlanProfile,
) -> tuple[CapturedQuery, ...]:
    scenarios_by_name = {scenario.name: scenario for scenario in scenarios}
    return tuple(
        replace(
            query,
            expectation=scenarios_by_name[query.scenario_name].plan_expectation(
                policy=ABSOLUTE_SLA_POLICY,
                query_name=query.name,
                profile=profile,
            ),
        )
        for query in queries
    )


def get_profile(*, name: str) -> QueryPlanProfile:
    if name == REALISTIC_PROFILE.name:
        return REALISTIC_PROFILE
    if name == STRESS_PROFILE.name:
        return STRESS_PROFILE
    msg = f"Unknown query plan profile: {name}"
    raise ValueError(msg)


def ensure_safe_database_name(*, allow_non_test_db: bool) -> None:
    database_name = settings.database.name
    if allow_non_test_db:
        return
    if database_name.endswith("_test"):
        return
    msg = (
        "query plan seeding clears tables and must run against a test database; "
        f"got DB_NAME={database_name!r}"
    )
    raise RuntimeError(msg)


async def benchmark_queries(
    *,
    connection: AsyncConnection,
    queries: Sequence[CapturedQuery],
    profile: QueryPlanProfile,
    baseline: QueryPlanBaseline | None,
) -> tuple[BenchmarkResult, ...]:
    if baseline is not None:
        if baseline.profile_name != profile.name:
            msg = (
                f"baseline profile {baseline.profile_name!r} does not match "
                f"query-plan profile {profile.name!r}"
            )
            raise ValueError(msg)
        validate_baseline_query_coverage(
            baseline=baseline,
            query_names=tuple(query.name for query in queries),
        )
    compiled_queries = {
        query.name: compile_captured_query(query=query, dialect=connection.dialect)
        for query in queries
    }
    explain_json_runs_by_query = {query.name: [] for query in queries}
    analyses_by_query = {query.name: [] for query in queries}
    for query in queries:
        stdout.write(f"Running EXPLAIN ANALYZE for {query.name}\n")
    query_groups = group_queries_by_scenario(queries)

    for _ in range(profile.explain_runs):
        for query_group in query_groups:
            transaction = await connection.begin()
            try:
                for query in query_group:
                    compiled_query = compiled_queries[query.name]
                    explain_json = await run_explain(
                        connection=connection,
                        compiled_query=compiled_query,
                    )
                    explain_json_runs_by_query[query.name].append(explain_json)
                    analyses_by_query[query.name].append(
                        analyze_explain_result(
                            name=query.name,
                            explain_json=cast("Sequence[object]", explain_json),
                            expectation=query.expectation,
                            relation_cardinalities=profile.relation_cardinalities,
                            minimum_blocking_cardinality=1_000,
                            timing_mode=profile.timing_mode,
                            effective_execution_threshold_ms=(
                                effective_execution_threshold_ms(
                                    sla_execution_ms=query.expectation.max_execution_ms,
                                    baseline_execution_ms=(
                                        None
                                        if baseline is None
                                        else baseline.query_warm_execution_ms[query.name]
                                    ),
                                )
                            ),
                        ),
                    )
            finally:
                await transaction.rollback()

    results: list[BenchmarkResult] = []
    for query in queries:
        analyses = analyses_by_query[query.name]
        warm_execution_ms = median(analysis.execution_time_ms for analysis in analyses[1:])
        baseline_execution_ms = (
            None if baseline is None else baseline.query_warm_execution_ms[query.name]
        )
        effective_threshold_ms = effective_execution_threshold_ms(
            sla_execution_ms=query.expectation.max_execution_ms,
            baseline_execution_ms=baseline_execution_ms,
        )
        findings = evaluate_plan_analysis(
            analysis=analyses[-1],
            expectation=query.expectation,
            measured_execution_ms=warm_execution_ms,
            relation_cardinalities=profile.relation_cardinalities,
            minimum_blocking_cardinality=1_000,
            timing_mode=profile.timing_mode,
            effective_execution_threshold_ms=effective_threshold_ms,
        )
        results.append(
            BenchmarkResult(
                query=query,
                compiled_query=compiled_queries[query.name],
                explain_json_runs=tuple(explain_json_runs_by_query[query.name]),
                analyses=tuple(analyses),
                warm_execution_ms=warm_execution_ms,
                baseline_execution_ms=baseline_execution_ms,
                effective_execution_threshold_ms=effective_threshold_ms,
                execution_time_exceeded=warm_execution_ms > effective_threshold_ms,
                blocking_findings=tuple(
                    f"{query.name}: {finding}" for finding in findings.blocking
                ),
                observations=tuple(
                    f"{query.name}: {observation}" for observation in findings.observations
                ),
            ),
        )
    return tuple(results)
