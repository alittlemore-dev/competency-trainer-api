import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import cast

from performance.query_plans.models import QueryPlanBaseline

COMMITTED_REALISTIC_BASELINE_PATH = Path(__file__).with_name("realistic-baseline.json")
BASELINE_SAMPLE_COUNT = 5


def effective_execution_threshold_ms(
    *,
    sla_execution_ms: float,
    baseline_execution_ms: float | None,
) -> float:
    if baseline_execution_ms is None:
        return sla_execution_ms
    relative_threshold = max(
        2 * baseline_execution_ms,
        baseline_execution_ms + 20.0,
    )
    return min(sla_execution_ms, relative_threshold)


def aggregate_baseline_candidate(
    *,
    summaries: Sequence[Mapping[str, object]],
    source_sha: str,
) -> QueryPlanBaseline:
    if len(summaries) != BASELINE_SAMPLE_COUNT:
        msg = "baseline candidate requires exactly five summaries"
        raise ValueError(msg)

    samples = tuple(read_summary(summary=summary) for summary in summaries)
    profile_name, first_queries = samples[0]
    if profile_name != "realistic":
        msg = f"baseline candidate requires realistic profile, got {profile_name!r}"
        raise ValueError(msg)
    expected_query_names = set(first_queries)
    values_by_query = {query_name: [value] for query_name, value in first_queries.items()}

    for sample_profile_name, query_values in samples[1:]:
        if sample_profile_name != profile_name:
            msg = (
                f"baseline profile mismatch: expected {profile_name!r}, got {sample_profile_name!r}"
            )
            raise ValueError(msg)
        if set(query_values) != expected_query_names:
            msg = "baseline query set mismatch"
            raise ValueError(msg)
        for query_name, value in query_values.items():
            values_by_query[query_name].append(value)

    return QueryPlanBaseline(
        profile_name=profile_name,
        source_sha=source_sha,
        sample_count=len(samples),
        query_warm_execution_ms={
            query_name: median(values) for query_name, values in values_by_query.items()
        },
    )


def validate_baseline_query_coverage(
    *,
    baseline: QueryPlanBaseline | None,
    query_names: Sequence[str],
) -> None:
    if baseline is None:
        msg = "baseline is required when the relative timing gate is enabled"
        raise ValueError(msg)
    baseline_names = set(baseline.query_warm_execution_ms)
    current_names = set(query_names)
    missing = sorted(current_names - baseline_names)
    stale = sorted(baseline_names - current_names)
    findings: list[str] = []
    if missing:
        findings.append(f"missing baseline queries: {'; '.join(missing)}")
    if stale:
        findings.append(f"stale baseline queries: {'; '.join(stale)}")
    if findings:
        raise ValueError("; ".join(findings))


def load_optional_baseline(
    *,
    path: Path,
    expected_profile_name: str,
) -> QueryPlanBaseline | None:
    if not path.exists():
        return None
    raw_baseline = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_baseline, Mapping):
        msg = "query-plan baseline must be a JSON object"
        raise TypeError(msg)
    baseline = deserialize_baseline(raw_baseline=raw_baseline)
    if baseline.profile_name != expected_profile_name:
        msg = f"baseline profile {baseline.profile_name!r} does not match {expected_profile_name!r}"
        raise ValueError(msg)
    return baseline


def deserialize_baseline(*, raw_baseline: Mapping[str, object]) -> QueryPlanBaseline:
    profile_name = require_non_empty_string(
        value=raw_baseline.get("profile"),
        description="query-plan baseline profile",
    )
    source_sha = require_non_empty_string(
        value=raw_baseline.get("sourceSha"),
        description="query-plan baseline sourceSha",
    )
    sample_count = require_baseline_sample_count(value=raw_baseline.get("sampleCount"))
    raw_queries = require_query_mapping(value=raw_baseline.get("queries"))

    query_warm_execution_ms: dict[str, float] = {}
    for raw_query_name, raw_value in raw_queries.items():
        query_name = require_non_empty_string(
            value=raw_query_name,
            description="query-plan baseline query name",
        )
        query_warm_execution_ms[query_name] = require_non_negative_number(
            value=raw_value,
            description=f"query-plan baseline value for {query_name!r}",
        )
    return QueryPlanBaseline(
        profile_name=profile_name,
        source_sha=source_sha,
        sample_count=sample_count,
        query_warm_execution_ms=query_warm_execution_ms,
    )


def require_non_empty_string(*, value: object, description: str) -> str:
    if not isinstance(value, str):
        msg = f"{description} must be a non-empty string"
        raise TypeError(msg)
    if not value:
        msg = f"{description} must be a non-empty string"
        raise ValueError(msg)
    return value


def require_baseline_sample_count(*, value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        msg = "query-plan baseline sampleCount must equal five"
        raise TypeError(msg)
    if value != BASELINE_SAMPLE_COUNT:
        msg = "query-plan baseline sampleCount must equal five"
        raise ValueError(msg)
    return value


def require_query_mapping(*, value: object) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        msg = "query-plan baseline queries must be a non-empty object"
        raise TypeError(msg)
    if not value:
        msg = "query-plan baseline queries must be a non-empty object"
        raise ValueError(msg)
    return value


def require_non_negative_number(*, value: object, description: str) -> float:
    if not isinstance(value, int | float) or isinstance(value, bool):
        msg = f"{description} must be non-negative"
        raise TypeError(msg)
    if value < 0:
        msg = f"{description} must be non-negative"
        raise ValueError(msg)
    return float(value)


def read_summary(*, summary: Mapping[str, object]) -> tuple[str, Mapping[str, float]]:
    raw_profile = summary.get("profile")
    raw_results = summary.get("results")
    if not isinstance(raw_profile, Mapping) or not isinstance(raw_results, Sequence):
        msg = "query-plan summary must contain profile and results"
        raise TypeError(msg)
    profile_name = raw_profile.get("name")
    if not isinstance(profile_name, str):
        msg = "query-plan summary profile name must be a string"
        raise TypeError(msg)

    query_values: dict[str, float] = {}
    for raw_result in raw_results:
        if not isinstance(raw_result, Mapping):
            msg = "query-plan summary result must be an object"
            raise TypeError(msg)
        query_name = raw_result.get("name")
        warm_execution_ms = raw_result.get("warmExecutionMs")
        if not isinstance(query_name, str) or not isinstance(warm_execution_ms, int | float):
            msg = "query-plan summary result must contain name and warmExecutionMs"
            raise TypeError(msg)
        if query_name in query_values:
            msg = f"query-plan summary contains duplicate query {query_name!r}"
            raise ValueError(msg)
        query_values[query_name] = float(warm_execution_ms)
    return profile_name, query_values


def serialize_baseline(*, baseline: QueryPlanBaseline) -> Mapping[str, object]:
    return {
        "profile": baseline.profile_name,
        "sourceSha": baseline.source_sha,
        "sampleCount": baseline.sample_count,
        "queries": baseline.query_warm_execution_ms,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a query-plan baseline candidate from five compatible summaries.",
    )
    parser.add_argument("--summary", action="append", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(argv)


def main() -> None:
    namespace = parse_args()
    summary_paths = tuple(Path(value) for value in cast("list[str]", namespace.summary))
    summaries = tuple(
        cast(
            "Mapping[str, object]",
            json.loads(path.read_text(encoding="utf-8")),
        )
        for path in summary_paths
    )
    baseline = aggregate_baseline_candidate(
        summaries=summaries,
        source_sha=cast("str", namespace.source_sha),
    )
    Path(cast("str", namespace.output)).write_text(
        json.dumps(serialize_baseline(baseline=baseline), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
