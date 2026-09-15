from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import replace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from performance.query_plans import (
    PlanExpectation,
    analyze_explain_result,
    compile_captured_query,
    generate_series_subquery,
)
from performance.query_plans import models as query_plan_models
from performance.query_plans import runner as query_plan_runner
from performance.query_plans import seed as query_plan_seed
from performance.query_plans.discovery import discover_storage_methods
from performance.query_plans.expectations import (
    QueryThresholdPolicy,
    scenario_plan_expectation,
)
from performance.query_plans.models import (
    BenchmarkResult,
    CapturedQuery,
    CoverageReport,
    PlanAnalysis,
    QueryThresholdGroup,
    StorageMethod,
)
from performance.query_plans.reports import serialize_summary
from performance.query_plans.runner import (
    apply_query_threshold_overrides,
    configure_explain_session,
)
from performance.query_plans.runtime_capture import RuntimeQueryCapture
from performance.query_plans.scenarios import (
    STORAGE_SCENARIOS,
    article_id,
    evaluate_storage_method_coverage,
    hex_id,
    write_article_for_existing_article,
)
from performance.query_plans.sql import group_queries_by_scenario


class TestQueryPlanAnalysis:
    def test_analyze_explain_result_accepts_expected_index_scan(self) -> None:
        analysis = analyze_explain_result(
            name="articles_list_en",
            explain_json=[
                {
                    "Planning Time": 1.5,
                    "Execution Time": 42.0,
                    "Plan": {
                        "Node Type": "Limit",
                        "Actual Rows": 20,
                        "Plans": [
                            {
                                "Node Type": "Bitmap Heap Scan",
                                "Relation Name": "articles__article_model",
                                "Actual Rows": 120,
                                "Plans": [
                                    {
                                        "Node Type": "Bitmap Index Scan",
                                        "Index Name": "articles_article_search_vector_en_gin_idx",
                                        "Actual Rows": 120,
                                    },
                                ],
                            },
                        ],
                    },
                },
            ],
            expectation=PlanExpectation(
                max_execution_ms=150.0,
                threshold_source="group:search",
                expected_indexes=(
                    query_plan_models.ExpectedIndex(
                        name="articles_article_search_vector_en_gin_idx",
                        relation_name="articles__article_model",
                    ),
                ),
                forbidden_seq_scan_relations=("articles__article_model",),
                allow_seq_scan_reason=None,
            ),
            relation_cardinalities={"articles__article_model": 5_000},
            minimum_blocking_cardinality=1_000,
            timing_mode=query_plan_models.TimingMode.ENFORCE,
            effective_execution_threshold_ms=150.0,
        )

        assert analysis.execution_time_ms == 42.0
        assert analysis.index_names == ("articles_article_search_vector_en_gin_idx",)
        assert analysis.blocking_findings == ()
        assert analysis.observations == ()

    def test_analyze_explain_result_flags_missing_index_and_large_seq_scan(self) -> None:
        analysis = analyze_explain_result(
            name="articles_list_en",
            explain_json=[
                {
                    "Planning Time": 2.0,
                    "Execution Time": 312.0,
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Relation Name": "articles__article_model",
                        "Actual Rows": 200_000,
                    },
                },
            ],
            expectation=PlanExpectation(
                max_execution_ms=150.0,
                threshold_source="group:search",
                expected_indexes=(
                    query_plan_models.ExpectedIndex(
                        name="articles_article_search_vector_en_gin_idx",
                        relation_name="articles__article_model",
                    ),
                ),
                forbidden_seq_scan_relations=("articles__article_model",),
                allow_seq_scan_reason=None,
            ),
            relation_cardinalities={"articles__article_model": 200_000},
            minimum_blocking_cardinality=1_000,
            timing_mode=query_plan_models.TimingMode.ENFORCE,
            effective_execution_threshold_ms=150.0,
        )

        assert "articles_article_search_vector_en_gin_idx" in analysis.blocking_findings[0]
        assert (
            "Seq Scan on 200000-row relation articles__article_model"
            in analysis.blocking_findings[1]
        )
        assert "312.00 ms exceeded 150.00 ms" in analysis.blocking_findings[2]
        assert analysis.observations == ()


class TestQueryCapture:
    def test_generate_series_subquery_exposes_value_column(self) -> None:
        series = generate_series_subquery(end=3, name="sample_series")

        compiled = str(
            series.select().compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            ),
        )

        assert "generate_series(1, 3) AS value" in compiled
        assert "sample_series.value" in compiled

    async def test_seed_bulk_selects_cast_native_enum_values(self) -> None:
        profile = make_query_plan_profile()
        expectations: tuple[
            tuple[Callable[..., Awaitable[None]], Mapping[str, object], tuple[str, ...]],
            ...,
        ] = (
            (query_plan_seed.insert_users, {"profile": profile}, ("role_enum",)),
            (
                query_plan_seed.insert_auth_sessions,
                {"profile": profile},
                ("auth_session_auth_method_enum", "auth_session_device_type_enum"),
            ),
            (query_plan_seed.insert_article_folders, {"profile": profile}, ()),
            (query_plan_seed.insert_articles, {"profile": profile}, ("publish_status_enum",)),
            (
                query_plan_seed.insert_article_reactions,
                {"profile": profile},
                ("article_reaction_kind_enum",),
            ),
            (
                query_plan_seed.insert_competency_matrix_items,
                {"profile": profile},
                ("grade_enum", "interview_frequency_enum", "publish_status_enum"),
            ),
        )

        for seed_function, kwargs, enum_type_names in expectations:
            connection = AsyncMock()

            await seed_function(connection=connection, **kwargs)

            statement = connection.execute.await_args_list[0].args[0]
            compiled = str(statement.compile(dialect=postgresql.dialect()))
            for enum_type_name in enum_type_names:
                assert f"AS {enum_type_name}" in compiled

    async def test_article_seed_uses_normalized_folder_id(self) -> None:
        profile = make_query_plan_profile()
        connection = AsyncMock()

        await query_plan_seed.insert_articles(connection=connection, profile=profile)

        statement = connection.execute.await_args.args[0]
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        assert "folder_id" in compiled
        assert "folder_ru" not in compiled
        assert "folder_en" not in compiled

    async def test_query_plan_profile_cleanup_removes_seeded_dataset(self) -> None:
        engine = MagicMock()
        connection = AsyncMock()
        engine.begin.return_value.__aenter__.return_value = connection

        await query_plan_runner.cleanup_seeded_profile(engine=engine)

        statement = connection.execute.await_args.args[0]
        sql = " ".join(statement.text.split())
        assert sql.startswith("TRUNCATE TABLE ")
        assert "articles__article_model" in sql
        assert "competency_matrix__competency_matrix_item_model" in sql
        assert "competency_matrix__external_resource_model" in sql
        assert "auth__user_model" in sql
        assert sql.endswith(" RESTART IDENTITY CASCADE")

    async def test_explain_session_uses_profile_work_mem_budget(self) -> None:
        connection = AsyncMock()

        await configure_explain_session(
            connection=connection,
            profile=query_plan_models.STRESS_PROFILE,
        )

        statement = connection.execute.await_args.args[0]
        parameters = connection.execute.await_args.args[1]
        assert "set_config('work_mem'" in statement.text
        assert parameters == {"work_mem": "64MB"}
        connection.commit.assert_awaited_once_with()

    def test_discover_storage_methods_finds_public_async_methods_only(self) -> None:
        methods = discover_storage_methods()
        identifiers = {(method.storage_class, method.method_name) for method in methods}

        assert ("ArticlesDatabaseStorage", "get_article_by_slug") in identifiers
        assert ("ArticlesDatabaseStorage", "list_articles") in identifiers
        assert ("ArticleAnalyticsDatabaseStorage", "get_reaction_counts") in identifiers
        assert ("CompetencyMatrixDatabaseStorage", "search_competency_matrix_resources") in (
            identifiers
        )
        assert ("AuthDatabaseStorage", "update_user_password_hash") in identifiers
        assert ("UserAccountDatabaseStorage", "get_user_by_username") in identifiers
        assert ("ContactMeDatabaseStorage", "create_contact_me_request") in identifiers
        assert ("ArticlesDatabaseStorage", "_get_article_model") not in identifiers

    def test_storage_scenarios_cover_every_discovered_storage_method(self) -> None:
        coverage = evaluate_storage_method_coverage(
            discovered_methods=discover_storage_methods(),
            scenarios=STORAGE_SCENARIOS,
        )

        assert coverage.missing_methods == ()
        assert coverage.unexpected_methods == ()
        assert ("ArticlesDatabaseStorage", "list_articles") in {
            (method.storage_class, method.method_name) for method in coverage.covered_methods
        }

    def test_update_article_scenario_reuses_seeded_article_tags(self) -> None:
        article = write_article_for_existing_article()

        assert article.id == article_id(99)
        assert {tag.id for tag in article.tags} == {hex_id(91), hex_id(97), hex_id(103)}

    def test_runtime_capture_records_statement_without_touching_cursor(self) -> None:
        capture = RuntimeQueryCapture(clock=FakeClock(1_000_000, 26_000_000))
        connection = FakeConnection()
        capture.start_scenario(
            storage_class="ArticlesDatabaseStorage",
            method_name="list_articles",
            scenario_name="articles_list_en_full_text_tag_date",
            expectation=PlanExpectation(
                max_execution_ms=150.0,
                threshold_source="group:search",
                expected_indexes=(
                    query_plan_models.ExpectedIndex(
                        name="articles_article_search_vector_en_gin_idx",
                        relation_name="articles__article_model",
                    ),
                ),
                forbidden_seq_scan_relations=("articles__article_model",),
                allow_seq_scan_reason=None,
            ),
        )

        typed_connection = cast("Connection", connection)
        capture.before_cursor_execute(
            typed_connection,
            object(),
            "SELECT  *\nFROM articles__article_model WHERE id = %(id)s",
            {"id": 1},
            None,
            False,
        )
        capture.after_cursor_execute(
            typed_connection,
            ExplodingCursor(),
            "SELECT  *\nFROM articles__article_model WHERE id = %(id)s",
            {"id": 1},
            None,
            False,
        )
        capture.stop_scenario()

        assert capture.captured_queries == (
            CapturedQuery(
                name="articles_list_en_full_text_tag_date__001",
                storage_class="ArticlesDatabaseStorage",
                method_name="list_articles",
                scenario_name="articles_list_en_full_text_tag_date",
                ordinal=1,
                sql="SELECT  *\nFROM articles__article_model WHERE id = %(id)s",
                normalized_sql="SELECT * FROM articles__article_model WHERE id = %(id)s",
                params={"id": 1},
                elapsed_ms=25.0,
                executemany=False,
                expectation=PlanExpectation(
                    max_execution_ms=150.0,
                    threshold_source="group:search",
                    expected_indexes=(
                        query_plan_models.ExpectedIndex(
                            name="articles_article_search_vector_en_gin_idx",
                            relation_name="articles__article_model",
                        ),
                    ),
                    forbidden_seq_scan_relations=("articles__article_model",),
                    allow_seq_scan_reason=None,
                ),
            ),
        )

    def test_compile_captured_query_keeps_sql_and_params_separate(self) -> None:
        query = CapturedQuery(
            name="tags_fuzzy_en__001",
            storage_class="ArticlesDatabaseStorage",
            method_name="search_tags",
            scenario_name="tags_fuzzy_en",
            ordinal=1,
            sql="SELECT * FROM articles__tag_model WHERE lower(name_en) %% %(tag_search_query)s",
            normalized_sql=(
                "SELECT * FROM articles__tag_model WHERE lower(name_en) %% %(tag_search_query)s"
            ),
            params={"tag_search_query": "pythno"},
            elapsed_ms=10.0,
            executemany=False,
            expectation=PlanExpectation(
                max_execution_ms=100.0,
                threshold_source="override:tags_fuzzy_en",
                expected_indexes=(
                    query_plan_models.ExpectedIndex(
                        name="articles_tag_name_en_trgm_idx",
                        relation_name="articles__tag_model",
                    ),
                ),
                forbidden_seq_scan_relations=("articles__tag_model",),
                allow_seq_scan_reason=None,
            ),
        )

        compiled = compile_captured_query(query=query, dialect=postgresql.dialect())

        assert "FROM articles__tag_model" in compiled.sql
        compiled_params = cast("Mapping[str, object]", compiled.params)
        assert "tag_search_query" in compiled_params
        assert compiled_params["tag_search_query"] == "pythno"

    def test_compile_captured_query_normalizes_sqlalchemy_insertmanyvalues_sort_alias(
        self,
    ) -> None:
        query = CapturedQuery(
            name="articles_create__002",
            storage_class="ArticlesDatabaseStorage",
            method_name="create_article",
            scenario_name="articles_create",
            ordinal=2,
            sql=(
                "INSERT INTO articles__article_to_tag_secondary_model (article_id, tag_id) "
                "SELECT p0::VARCHAR, p1::VARCHAR FROM "
                "(VALUES (%(article_id)s::VARCHAR, %(tag_id)s::VARCHAR)) "
                "AS imp_sen(p0, p1, sen_counter) ORDER BY sen_counter "
                "RETURNING articles__article_to_tag_secondary_model.id"
            ),
            normalized_sql="",
            params={"article_id": article_id(1), "tag_id": hex_id(1)},
            elapsed_ms=10.0,
            executemany=False,
            expectation=PlanExpectation(
                max_execution_ms=100.0,
                threshold_source="group:small_write",
                expected_indexes=(),
                forbidden_seq_scan_relations=(),
                allow_seq_scan_reason=None,
            ),
        )

        compiled = compile_captured_query(query=query, dialect=postgresql.dialect())

        assert "AS imp_sen(p0, p1) RETURNING" in compiled.sql
        assert "sen_counter" not in compiled.sql

    def test_group_queries_by_scenario_preserves_contiguous_scenario_order(self) -> None:
        first = make_captured_query(
            name="articles_create__001",
            scenario_name="articles_create",
            ordinal=1,
        )
        second = make_captured_query(
            name="articles_create__002",
            scenario_name="articles_create",
            ordinal=2,
        )
        third = make_captured_query(
            name="articles_update__001",
            scenario_name="articles_update",
            ordinal=1,
        )

        groups = group_queries_by_scenario((first, second, third))

        assert groups == ((first, second), (third,))

    def test_threshold_policy_applies_group_thresholds_and_scenario_overrides(self) -> None:
        policy = QueryThresholdPolicy(
            group_max_execution_ms={
                QueryThresholdGroup.POINT_READ: 25.0,
                QueryThresholdGroup.SEARCH: 150.0,
            },
            scenario_max_execution_ms={"tags_short_en": 250.0},
            query_max_execution_ms={"tags_short_en__001": 300.0},
            query_expected_indexes={
                "tags_short_en__001": (
                    query_plan_models.ExpectedIndex(
                        name="articles_tag_slug_trgm_idx",
                        relation_name="articles__tag_model",
                    ),
                ),
            },
        )

        search_expectation = scenario_plan_expectation(
            scenario_name="tags_fuzzy_en",
            group=QueryThresholdGroup.SEARCH,
            policy=policy,
            query_name=None,
            expected_indexes=(
                query_plan_models.ExpectedIndex(
                    name="articles_tag_name_en_trgm_idx",
                    relation_name="articles__tag_model",
                ),
            ),
            forbidden_seq_scan_relations=("articles__tag_model",),
            allow_seq_scan_reason=None,
        )
        override_expectation = scenario_plan_expectation(
            scenario_name="tags_short_en",
            group=QueryThresholdGroup.SEARCH,
            policy=policy,
            query_name=None,
            expected_indexes=(),
            forbidden_seq_scan_relations=(),
            allow_seq_scan_reason="short search string is intentionally non-selective",
        )
        statement_override_expectation = scenario_plan_expectation(
            scenario_name="tags_short_en",
            group=QueryThresholdGroup.SEARCH,
            policy=policy,
            query_name="tags_short_en__001",
            expected_indexes=(),
            forbidden_seq_scan_relations=(),
            allow_seq_scan_reason="short search string is intentionally non-selective",
        )

        assert search_expectation.max_execution_ms == 150.0
        assert search_expectation.threshold_source == "group:search"
        assert override_expectation.max_execution_ms == 250.0
        assert override_expectation.threshold_source == "override:tags_short_en"
        assert statement_override_expectation.max_execution_ms == 300.0
        assert statement_override_expectation.threshold_source == "override:tags_short_en__001"
        assert statement_override_expectation.expected_indexes == (
            query_plan_models.ExpectedIndex(
                name="articles_tag_slug_trgm_idx",
                relation_name="articles__tag_model",
            ),
        )

    def test_runner_applies_statement_threshold_overrides_to_captured_queries(self) -> None:
        query = make_captured_query(
            name="articles_list_en_full_text_tag_date__002",
            scenario_name="articles_list_en_full_text_tag_date",
            ordinal=2,
        )

        captured_queries = apply_query_threshold_overrides(
            queries=(query,),
            scenarios=STORAGE_SCENARIOS,
            profile=query_plan_models.REALISTIC_PROFILE,
        )

        assert captured_queries[0].expectation.max_execution_ms == 250.0
        assert captured_queries[0].expectation.threshold_source == (
            "override:articles_list_en_full_text_tag_date__002"
        )

    def test_coverage_evaluator_reports_missing_and_unexpected_methods(self) -> None:
        discovered = (
            StorageMethod(
                storage_class="ExampleDatabaseStorage",
                method_name="covered",
                module_name="infra.postgresql.storages.example",
            ),
            StorageMethod(
                storage_class="ExampleDatabaseStorage",
                method_name="missing",
                module_name="infra.postgresql.storages.example",
            ),
        )
        scenario = replace(
            STORAGE_SCENARIOS[0],
            storage_class="ExampleDatabaseStorage",
            method_name="covered",
        )
        unexpected_scenario = replace(
            STORAGE_SCENARIOS[0],
            name="unexpected",
            storage_class="ExampleDatabaseStorage",
            method_name="unexpected",
        )

        coverage = evaluate_storage_method_coverage(
            discovered_methods=discovered,
            scenarios=(scenario, unexpected_scenario),
        )

        assert coverage.missing_methods == (discovered[1],)
        assert coverage.unexpected_methods == (
            StorageMethod(
                storage_class="ExampleDatabaseStorage",
                method_name="unexpected",
                module_name="",
            ),
        )

    def test_report_summary_includes_coverage_and_query_metadata(self) -> None:
        query = CapturedQuery(
            name="articles_by_slug__001",
            storage_class="ArticlesDatabaseStorage",
            method_name="get_article_by_slug",
            scenario_name="articles_by_slug",
            ordinal=1,
            sql="SELECT * FROM articles__article_model WHERE slug = %(slug)s",
            normalized_sql="SELECT * FROM articles__article_model WHERE slug = %(slug)s",
            params={"slug": "article-100"},
            elapsed_ms=2.5,
            executemany=False,
            expectation=PlanExpectation(
                max_execution_ms=25.0,
                threshold_source="group:point_read",
                expected_indexes=(
                    query_plan_models.ExpectedIndex(
                        name="ix_articles__article_model_slug",
                        relation_name="articles__article_model",
                    ),
                ),
                forbidden_seq_scan_relations=("articles__article_model",),
                allow_seq_scan_reason=None,
            ),
        )
        result = BenchmarkResult(
            query=query,
            compiled_query=compile_captured_query(query=query, dialect=postgresql.dialect()),
            explain_json_runs=({},),
            analyses=(
                PlanAnalysis(
                    name=query.name,
                    planning_time_ms=1.0,
                    execution_time_ms=2.0,
                    node_types=("Index Scan",),
                    index_names=("ix_articles__article_model_slug",),
                    seq_scan_relations=(),
                    temp_blocks=0,
                    blocking_findings=(),
                    observations=(),
                ),
            ),
            warm_execution_ms=2.0,
            baseline_execution_ms=1.0,
            effective_execution_threshold_ms=21.0,
            execution_time_exceeded=False,
            blocking_findings=(),
            observations=("planner chose an alternative equivalent index",),
        )

        summary = serialize_summary(
            profile=query_plan_models.REALISTIC_PROFILE,
            baseline=query_plan_models.QueryPlanBaseline(
                profile_name="realistic",
                source_sha="abc123",
                sample_count=5,
                query_warm_execution_ms={"articles_by_slug__001": 1.0},
            ),
            coverage=CoverageReport(
                discovered_methods=(
                    StorageMethod(
                        storage_class="ArticlesDatabaseStorage",
                        method_name="get_article_by_slug",
                        module_name="infra.postgresql.storages.articles",
                    ),
                ),
                covered_methods=(
                    StorageMethod(
                        storage_class="ArticlesDatabaseStorage",
                        method_name="get_article_by_slug",
                        module_name="infra.postgresql.storages.articles",
                    ),
                ),
                missing_methods=(),
                unexpected_methods=(),
            ),
            results=(result,),
        )

        assert summary["coverage"] == {
            "discoveredMethodCount": 1,
            "coveredMethodCount": 1,
            "missingMethods": [],
            "unexpectedMethods": [],
        }
        assert summary["profile"] == {
            "name": "realistic",
            "timingMode": "enforce",
            "explainRuns": 3,
            "explainWorkMemMb": 16,
            "cardinalities": {
                "auth": {"users": 100, "sessions": 500},
                "articles": {
                    "folders": 20,
                    "articles": 5_000,
                    "publishedPercentage": 80,
                    "ftsMatchPercentage": 1,
                    "tags": 500,
                    "articleTagLinks": 20_000,
                    "dailyAnalytics": 100_000,
                    "reactions": 10_000,
                },
                "matrix": {
                    "sheets": 20,
                    "sectionsPerSheet": 8,
                    "subsectionsPerSection": 12,
                    "items": 10_000,
                    "resources": 5_000,
                    "resourceLinks": 25_000,
                    "queuedQuestions": 5_000,
                },
                "agentAccess": {"auditEvents": 10_000},
            },
            "relationCardinalities": query_plan_models.REALISTIC_PROFILE.relation_cardinalities,
        }
        assert summary["baseline"] == {
            "profile": "realistic",
            "sourceSha": "abc123",
            "sampleCount": 5,
            "queries": {"articles_by_slug__001": 1.0},
        }
        summary_results = cast("Sequence[Mapping[str, object]]", summary["results"])
        assert summary_results[0] == {
            "name": "articles_by_slug__001",
            "storageClass": "ArticlesDatabaseStorage",
            "methodName": "get_article_by_slug",
            "scenarioName": "articles_by_slug",
            "ordinal": 1,
            "executemany": False,
            "runtimeElapsedMs": 2.5,
            "warmExecutionMs": 2.0,
            "thresholdSource": "group:point_read",
            "timingMode": "enforce",
            "slaExecutionMs": 25.0,
            "baselineExecutionMs": 1.0,
            "effectiveExecutionThresholdMs": 21.0,
            "executionTimeExceeded": False,
            "indexes": ("ix_articles__article_model_slug",),
            "seqScans": (),
            "nodeTypes": ("Index Scan",),
            "blockingFindings": (),
            "observations": ("planner chose an alternative equivalent index",),
        }


class FakeConnection:
    def __init__(self) -> None:
        self.info: dict[str, Any] = {}


class FakeClock:
    def __init__(self, *values: int) -> None:
        self.values = list(values)

    def __call__(self) -> int:
        return self.values.pop(0)


class ExplodingCursor:
    def __getattribute__(self, name: str) -> object:
        msg = f"cursor attribute must not be read: {name}"
        raise AssertionError(msg)


def make_captured_query(*, name: str, scenario_name: str, ordinal: int) -> CapturedQuery:
    return CapturedQuery(
        name=name,
        storage_class="ArticlesDatabaseStorage",
        method_name="create_article",
        scenario_name=scenario_name,
        ordinal=ordinal,
        sql="SELECT 1",
        normalized_sql="SELECT 1",
        params={},
        elapsed_ms=1.0,
        executemany=False,
        expectation=PlanExpectation(
            max_execution_ms=25.0,
            threshold_source="group:point_read",
            expected_indexes=(),
            forbidden_seq_scan_relations=(),
            allow_seq_scan_reason=None,
        ),
    )


def make_query_plan_profile() -> query_plan_models.QueryPlanProfile:
    return query_plan_models.QueryPlanProfile(
        name="unit",
        cardinalities=query_plan_models.ProfileCardinalities(
            auth=query_plan_models.AuthCardinalities(users=10, sessions=10),
            articles=query_plan_models.ArticleCardinalities(
                folders=1,
                articles=10,
                published_percentage=80,
                fts_match_percentage=1,
                tags=10,
                article_tag_links=10,
                daily_analytics=10,
                reactions=10,
            ),
            matrix=query_plan_models.MatrixCardinalities(
                sheets=1,
                sections_per_sheet=1,
                subsections_per_section=1,
                items=101,
                resources=101,
                resource_links=10,
                queued_questions=101,
            ),
            agent_access=query_plan_models.AgentAccessCardinalities(audit_events=10),
        ),
        timing_mode=query_plan_models.TimingMode.ENFORCE,
        explain_runs=1,
        explain_work_mem_mb=16,
        scenario_plan_shape_overrides={},
    )
