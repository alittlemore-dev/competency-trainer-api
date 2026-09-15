import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from performance.query_plans.baseline import serialize_baseline
from performance.query_plans.models import (
    BenchmarkResult,
    CoverageReport,
    QueryPlanBaseline,
    QueryPlanProfile,
)


def write_reports(
    *,
    report_dir: Path,
    profile: QueryPlanProfile,
    baseline: QueryPlanBaseline | None,
    coverage: CoverageReport,
    results: Sequence[BenchmarkResult],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        result_path = report_dir / result.query.name
        result_path.mkdir(parents=True, exist_ok=True)
        (result_path / "compiled.sql").write_text(result.compiled_query.sql, encoding="utf-8")
        (result_path / "params.json").write_text(
            json.dumps(
                result.compiled_query.params,
                ensure_ascii=False,
                indent=2,
                default=json_default,
            ),
            encoding="utf-8",
        )
        for index, explain_json in enumerate(result.explain_json_runs, start=1):
            (result_path / f"explain-run-{index}.json").write_text(
                json.dumps(explain_json, ensure_ascii=False, indent=2, default=json_default),
                encoding="utf-8",
            )
    (report_dir / "summary.md").write_text(
        render_markdown_summary(
            profile=profile,
            baseline=baseline,
            coverage=coverage,
            results=results,
        ),
        encoding="utf-8",
    )
    (report_dir / "summary.json").write_text(
        json.dumps(
            serialize_summary(
                profile=profile,
                baseline=baseline,
                coverage=coverage,
                results=results,
            ),
            ensure_ascii=False,
            indent=2,
            default=json_default,
        ),
        encoding="utf-8",
    )


def render_markdown_summary(
    *,
    profile: QueryPlanProfile,
    baseline: QueryPlanBaseline | None,
    coverage: CoverageReport,
    results: Sequence[BenchmarkResult],
) -> str:
    lines = [
        "# Query Plan Report",
        "",
        f"- Profile: `{profile.name}`",
        f"- Timing mode: `{profile.timing_mode.value}`",
        f"- EXPLAIN runs per query: `{profile.explain_runs}`",
        f"- EXPLAIN work_mem: `{profile.explain_work_mem_mb}MB`",
        f"- Baseline: `{baseline.source_sha}`" if baseline is not None else "- Baseline: disabled",
        f"- Storage methods discovered: `{len(coverage.discovered_methods)}`",
        f"- Storage methods covered: `{len(coverage.covered_methods)}`",
        f"- Missing storage scenarios: `{len(coverage.missing_methods)}`",
        f"- Unexpected storage scenarios: `{len(coverage.unexpected_methods)}`",
        "",
        "## Relation cardinalities",
        "",
    ]
    lines.extend(
        f"- `{relation_name}`: `{cardinality}`"
        for relation_name, cardinality in profile.relation_cardinalities.items()
    )
    lines.extend(
        (
            "",
            "## Query results",
            "",
            (
                "| Query | Storage method | Runtime ms | Warm median ms | SLA ms | Baseline ms | "
                "Effective ms | Exceeded | Indexes | Seq scans | Blocking findings | Observations |"
            ),
            "|---|---|---:|---:|---:|---:|---:|---|---|---|---|---|",
        ),
    )
    for result in results:
        last_analysis = result.analyses[-1]
        indexes = ", ".join(last_analysis.index_names) or "-"
        seq_scans = ", ".join(last_analysis.seq_scan_relations) or "-"
        blocking_findings = "<br>".join(result.blocking_findings) or "OK"
        observations = "<br>".join(result.observations) or "-"
        baseline_execution_ms = (
            f"{result.baseline_execution_ms:.2f}"
            if result.baseline_execution_ms is not None
            else "-"
        )
        lines.append(
            f"| `{result.query.name}` | "
            f"`{result.query.storage_class}.{result.query.method_name}` | "
            f"{result.query.elapsed_ms:.2f} | {result.warm_execution_ms:.2f} | "
            f"{result.query.expectation.max_execution_ms:.2f} | {baseline_execution_ms} | "
            f"{result.effective_execution_threshold_ms:.2f} | "
            f"{'yes' if result.execution_time_exceeded else 'no'} | "
            f"{indexes} | {seq_scans} | {blocking_findings} | {observations} |",
        )
    lines.append("")
    lines.append(
        "Each query directory contains the compiled SQL, bound params, and every "
        "`EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)` run.",
    )
    lines.append("")
    return "\n".join(lines)


def serialize_summary(
    *,
    profile: QueryPlanProfile,
    baseline: QueryPlanBaseline | None,
    coverage: CoverageReport,
    results: Sequence[BenchmarkResult],
) -> Mapping[str, object]:
    return {
        "profile": serialize_profile(profile=profile),
        "baseline": {} if baseline is None else serialize_baseline(baseline=baseline),
        "coverage": {
            "discoveredMethodCount": len(coverage.discovered_methods),
            "coveredMethodCount": len(coverage.covered_methods),
            "missingMethods": [
                f"{method.storage_class}.{method.method_name}"
                for method in coverage.missing_methods
            ],
            "unexpectedMethods": [
                f"{method.storage_class}.{method.method_name}"
                for method in coverage.unexpected_methods
            ],
        },
        "results": [
            {
                "name": result.query.name,
                "storageClass": result.query.storage_class,
                "methodName": result.query.method_name,
                "scenarioName": result.query.scenario_name,
                "ordinal": result.query.ordinal,
                "executemany": result.query.executemany,
                "runtimeElapsedMs": result.query.elapsed_ms,
                "warmExecutionMs": result.warm_execution_ms,
                "thresholdSource": result.query.expectation.threshold_source,
                "timingMode": profile.timing_mode.value,
                "slaExecutionMs": result.query.expectation.max_execution_ms,
                "baselineExecutionMs": result.baseline_execution_ms,
                "effectiveExecutionThresholdMs": result.effective_execution_threshold_ms,
                "executionTimeExceeded": result.execution_time_exceeded,
                "indexes": result.analyses[-1].index_names,
                "seqScans": result.analyses[-1].seq_scan_relations,
                "nodeTypes": result.analyses[-1].node_types,
                "blockingFindings": result.blocking_findings,
                "observations": result.observations,
            }
            for result in results
        ],
    }


def serialize_profile(*, profile: QueryPlanProfile) -> Mapping[str, object]:
    cardinalities = profile.cardinalities
    return {
        "name": profile.name,
        "timingMode": profile.timing_mode.value,
        "explainRuns": profile.explain_runs,
        "explainWorkMemMb": profile.explain_work_mem_mb,
        "cardinalities": {
            "auth": {
                "users": cardinalities.auth.users,
                "sessions": cardinalities.auth.sessions,
            },
            "articles": {
                "folders": cardinalities.articles.folders,
                "articles": cardinalities.articles.articles,
                "publishedPercentage": cardinalities.articles.published_percentage,
                "ftsMatchPercentage": cardinalities.articles.fts_match_percentage,
                "tags": cardinalities.articles.tags,
                "articleTagLinks": cardinalities.articles.article_tag_links,
                "dailyAnalytics": cardinalities.articles.daily_analytics,
                "reactions": cardinalities.articles.reactions,
            },
            "matrix": {
                "sheets": cardinalities.matrix.sheets,
                "sectionsPerSheet": cardinalities.matrix.sections_per_sheet,
                "subsectionsPerSection": cardinalities.matrix.subsections_per_section,
                "items": cardinalities.matrix.items,
                "resources": cardinalities.matrix.resources,
                "resourceLinks": cardinalities.matrix.resource_links,
                "queuedQuestions": cardinalities.matrix.queued_questions,
            },
            "agentAccess": {"auditEvents": cardinalities.agent_access.audit_events},
        },
        "relationCardinalities": profile.relation_cardinalities,
    }


def json_default(value: object) -> str:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.name
    return str(value)
