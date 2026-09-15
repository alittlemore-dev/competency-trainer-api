from performance.query_plans import analyze_explain_result
from performance.query_plans import models as query_plan_models


class TestQueryPlanAnalysisPolicy:
    def test_small_relation_plan_shape_is_observed_but_temp_blocks_still_block(self) -> None:
        analysis = analyze_explain_result(
            name="tags_list_public__001",
            explain_json=[
                {
                    "Execution Time": 20.0,
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Relation Name": "articles__tag_model",
                        "Temp Written Blocks": 2,
                    },
                },
            ],
            expectation=make_expectation(),
            relation_cardinalities={"articles__tag_model": 999},
            minimum_blocking_cardinality=1_000,
            timing_mode=query_plan_models.TimingMode.ENFORCE,
            effective_execution_threshold_ms=250.0,
        )

        assert analysis.blocking_findings == ("query used 2 temp blocks",)
        assert analysis.observations == (
            "missing expected index articles_tag_slug_idx on 999-row relation articles__tag_model",
            "Seq Scan on 999-row relation articles__tag_model",
        )

    def test_plan_shape_blocks_at_cardinality_boundary(self) -> None:
        analysis = analyze_explain_result(
            name="tags_list_public__001",
            explain_json=[
                {
                    "Execution Time": 20.0,
                    "Plan": {
                        "Node Type": "Seq Scan",
                        "Relation Name": "articles__tag_model",
                    },
                },
            ],
            expectation=make_expectation(),
            relation_cardinalities={"articles__tag_model": 1_000},
            minimum_blocking_cardinality=1_000,
            timing_mode=query_plan_models.TimingMode.ENFORCE,
            effective_execution_threshold_ms=250.0,
        )

        assert analysis.blocking_findings == (
            "missing expected index articles_tag_slug_idx on 1000-row relation articles__tag_model",
            "Seq Scan on 1000-row relation articles__tag_model",
        )
        assert analysis.observations == ()

    def test_observe_timing_mode_records_sla_overrun_without_blocking(self) -> None:
        analysis = analyze_explain_result(
            name="tags_list_public__001",
            explain_json=[
                {
                    "Execution Time": 275.0,
                    "Plan": {
                        "Node Type": "Index Scan",
                        "Relation Name": "articles__tag_model",
                        "Index Name": "articles_tag_slug_idx",
                    },
                },
            ],
            expectation=make_expectation(),
            relation_cardinalities={"articles__tag_model": 30_000},
            minimum_blocking_cardinality=1_000,
            timing_mode=query_plan_models.TimingMode.OBSERVE,
            effective_execution_threshold_ms=250.0,
        )

        assert analysis.blocking_findings == ()
        assert analysis.observations == ("execution time 275.00 ms exceeded 250.00 ms",)


def make_expectation() -> query_plan_models.PlanExpectation:
    return query_plan_models.PlanExpectation(
        max_execution_ms=250.0,
        threshold_source="group:list_read",
        expected_indexes=(
            query_plan_models.ExpectedIndex(
                name="articles_tag_slug_idx",
                relation_name="articles__tag_model",
            ),
        ),
        forbidden_seq_scan_relations=("articles__tag_model",),
        allow_seq_scan_reason=None,
    )
