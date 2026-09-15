from collections.abc import Mapping, Sequence
from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest

from performance.query_plans import models as query_plan_models


class BaselineModule(Protocol):
    def effective_execution_threshold_ms(
        self,
        *,
        sla_execution_ms: float,
        baseline_execution_ms: float | None,
    ) -> float: ...

    def aggregate_baseline_candidate(
        self,
        *,
        summaries: Sequence[Mapping[str, object]],
        source_sha: str,
    ) -> query_plan_models.QueryPlanBaseline: ...

    def validate_baseline_query_coverage(
        self,
        *,
        baseline: query_plan_models.QueryPlanBaseline | None,
        query_names: Sequence[str],
    ) -> None: ...

    def load_optional_baseline(
        self,
        *,
        path: Path,
        expected_profile_name: str,
    ) -> query_plan_models.QueryPlanBaseline | None: ...


class TestQueryPlanBaseline:
    @pytest.mark.parametrize(
        ("sla_execution_ms", "baseline_execution_ms", "expected"),
        [
            (250.0, None, 250.0),
            (250.0, 10.0, 30.0),
            (250.0, 40.0, 80.0),
            (250.0, 200.0, 250.0),
        ],
    )
    def test_effective_execution_threshold_uses_baseline_formula(
        self,
        sla_execution_ms: float,
        baseline_execution_ms: float | None,
        expected: float,
    ) -> None:
        baseline_module = load_baseline_module()

        result = baseline_module.effective_execution_threshold_ms(
            sla_execution_ms=sla_execution_ms,
            baseline_execution_ms=baseline_execution_ms,
        )

        assert result == expected

    def test_candidate_aggregates_exactly_five_compatible_summaries(self) -> None:
        baseline_module = load_baseline_module()

        candidate = baseline_module.aggregate_baseline_candidate(
            summaries=make_summaries(),
            source_sha="abc123",
        )

        assert candidate == query_plan_models.QueryPlanBaseline(
            profile_name="realistic",
            source_sha="abc123",
            sample_count=5,
            query_warm_execution_ms={"query_a": 11.0, "query_b": 20.0},
        )

    def test_candidate_rejects_any_sample_count_other_than_five(self) -> None:
        baseline_module = load_baseline_module()

        with pytest.raises(ValueError, match="exactly five summaries"):
            baseline_module.aggregate_baseline_candidate(
                summaries=make_summaries()[:4],
                source_sha="abc123",
            )

    def test_candidate_rejects_profile_mismatch(self) -> None:
        baseline_module = load_baseline_module()
        summaries = list(make_summaries())
        summaries[-1] = make_summary(profile_name="stress", query_a=11.0, query_b=20.0)

        with pytest.raises(ValueError, match="profile mismatch"):
            baseline_module.aggregate_baseline_candidate(
                summaries=summaries,
                source_sha="abc123",
            )

    def test_candidate_rejects_query_set_mismatch(self) -> None:
        baseline_module = load_baseline_module()
        summaries = list(make_summaries())
        summaries[-1] = {
            "profile": {"name": "realistic"},
            "results": (
                {"name": "query_a", "warmExecutionMs": 11.0},
                {"name": "stale_query", "warmExecutionMs": 20.0},
            ),
        }

        with pytest.raises(ValueError, match="query set mismatch"):
            baseline_module.aggregate_baseline_candidate(
                summaries=summaries,
                source_sha="abc123",
            )

    def test_enabled_baseline_gate_rejects_missing_baseline(self) -> None:
        baseline_module = load_baseline_module()

        with pytest.raises(ValueError, match="baseline is required"):
            baseline_module.validate_baseline_query_coverage(
                baseline=None,
                query_names=("query_a",),
            )

    def test_enabled_baseline_gate_rejects_missing_and_stale_queries(self) -> None:
        baseline_module = load_baseline_module()
        baseline = query_plan_models.QueryPlanBaseline(
            profile_name="realistic",
            source_sha="abc123",
            sample_count=5,
            query_warm_execution_ms={"query_a": 10.0, "stale_query": 20.0},
        )

        with pytest.raises(
            ValueError,
            match=r"missing baseline queries: query_b; stale baseline queries: stale_query",
        ):
            baseline_module.validate_baseline_query_coverage(
                baseline=baseline,
                query_names=("query_a", "query_b"),
            )

    def test_optional_baseline_is_disabled_until_committed(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_module = load_baseline_module()

        assert (
            baseline_module.load_optional_baseline(
                path=tmp_path / "realistic-baseline.json",
                expected_profile_name="realistic",
            )
            is None
        )

    def test_optional_baseline_loads_committed_candidate(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_module = load_baseline_module()
        path = tmp_path / "realistic-baseline.json"
        path.write_text(
            '{"profile":"realistic","sourceSha":"abc123","sampleCount":5,'
            '"queries":{"query_a":11.0,"query_b":20.0}}',
            encoding="utf-8",
        )

        assert baseline_module.load_optional_baseline(
            path=path,
            expected_profile_name="realistic",
        ) == query_plan_models.QueryPlanBaseline(
            profile_name="realistic",
            source_sha="abc123",
            sample_count=5,
            query_warm_execution_ms={"query_a": 11.0, "query_b": 20.0},
        )

    def test_optional_baseline_rejects_wrong_profile(
        self,
        tmp_path: Path,
    ) -> None:
        baseline_module = load_baseline_module()
        path = tmp_path / "realistic-baseline.json"
        path.write_text(
            '{"profile":"stress","sourceSha":"abc123","sampleCount":5,"queries":{"query_a":11.0}}',
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="profile 'stress' does not match 'realistic'"):
            baseline_module.load_optional_baseline(
                path=path,
                expected_profile_name="realistic",
            )


def load_baseline_module() -> BaselineModule:
    return cast("BaselineModule", import_module("performance.query_plans.baseline"))


def make_summaries() -> tuple[Mapping[str, object], ...]:
    return (
        make_summary(profile_name="realistic", query_a=10.0, query_b=20.0),
        make_summary(profile_name="realistic", query_a=12.0, query_b=18.0),
        make_summary(profile_name="realistic", query_a=9.0, query_b=22.0),
        make_summary(profile_name="realistic", query_a=14.0, query_b=19.0),
        make_summary(profile_name="realistic", query_a=11.0, query_b=21.0),
    )


def make_summary(*, profile_name: str, query_a: float, query_b: float) -> Mapping[str, object]:
    return {
        "profile": {"name": profile_name},
        "results": (
            {"name": "query_a", "warmExecutionMs": query_a},
            {"name": "query_b", "warmExecutionMs": query_b},
        ),
    }
