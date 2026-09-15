from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from performance.query_plans.models import (
    JsonObject,
    PlanAnalysis,
    PlanExpectation,
    TimingMode,
)


@dataclass(frozen=True, slots=True)
class AnalysisFindings:
    blocking: tuple[str, ...]
    observations: tuple[str, ...]


def analyze_explain_result(  # noqa: PLR0913
    *,
    name: str,
    explain_json: Sequence[object],
    expectation: PlanExpectation,
    relation_cardinalities: Mapping[str, int],
    minimum_blocking_cardinality: int,
    timing_mode: TimingMode,
    effective_execution_threshold_ms: float,
) -> PlanAnalysis:
    raw_entry = cast("JsonObject", explain_json[0])
    plan = cast("JsonObject", raw_entry["Plan"])
    analysis = analyze_plan_shape(
        name=name,
        plan=plan,
        planning_time_ms=float(cast("int | float", raw_entry.get("Planning Time", 0.0))),
        execution_time_ms=float(cast("int | float", raw_entry.get("Execution Time", 0.0))),
    )
    findings = evaluate_plan_analysis(
        analysis=analysis,
        expectation=expectation,
        measured_execution_ms=analysis.execution_time_ms,
        relation_cardinalities=relation_cardinalities,
        minimum_blocking_cardinality=minimum_blocking_cardinality,
        timing_mode=timing_mode,
        effective_execution_threshold_ms=effective_execution_threshold_ms,
    )
    return PlanAnalysis(
        name=analysis.name,
        planning_time_ms=analysis.planning_time_ms,
        execution_time_ms=analysis.execution_time_ms,
        node_types=analysis.node_types,
        index_names=analysis.index_names,
        seq_scan_relations=analysis.seq_scan_relations,
        temp_blocks=analysis.temp_blocks,
        blocking_findings=findings.blocking,
        observations=findings.observations,
    )


def analyze_plan_shape(
    *,
    name: str,
    plan: JsonObject,
    planning_time_ms: float,
    execution_time_ms: float,
) -> PlanAnalysis:
    nodes = tuple(iter_plan_nodes(plan))
    return PlanAnalysis(
        name=name,
        planning_time_ms=planning_time_ms,
        execution_time_ms=execution_time_ms,
        node_types=tuple(read_text_value(node=node, key="Node Type") for node in nodes),
        index_names=tuple(
            index_name
            for node in nodes
            if (index_name := read_optional_text_value(node=node, key="Index Name")) is not None
        ),
        seq_scan_relations=tuple(
            relation_name
            for node in nodes
            if read_text_value(node=node, key="Node Type") == "Seq Scan"
            if (relation_name := read_optional_text_value(node=node, key="Relation Name"))
            is not None
        ),
        temp_blocks=sum(read_int_value(node=node, key="Temp Read Blocks") for node in nodes)
        + sum(read_int_value(node=node, key="Temp Written Blocks") for node in nodes),
        blocking_findings=(),
        observations=(),
    )


def evaluate_plan_analysis(  # noqa: PLR0913
    *,
    analysis: PlanAnalysis,
    expectation: PlanExpectation,
    measured_execution_ms: float,
    relation_cardinalities: Mapping[str, int],
    minimum_blocking_cardinality: int,
    timing_mode: TimingMode,
    effective_execution_threshold_ms: float,
) -> AnalysisFindings:
    blocking: list[str] = []
    observations: list[str] = []
    for expected_index in expectation.expected_indexes:
        if expected_index.name in analysis.index_names:
            continue
        finding = cardinality_finding(
            description=f"missing expected index {expected_index.name}",
            relation_name=expected_index.relation_name,
            relation_cardinalities=relation_cardinalities,
        )
        append_plan_shape_finding(
            finding=finding,
            relation_name=expected_index.relation_name,
            relation_cardinalities=relation_cardinalities,
            minimum_blocking_cardinality=minimum_blocking_cardinality,
            blocking=blocking,
            observations=observations,
        )
    if expectation.allow_seq_scan_reason is None:
        for relation_name in expectation.forbidden_seq_scan_relations:
            if relation_name not in analysis.seq_scan_relations:
                continue
            finding = cardinality_finding(
                description="Seq Scan",
                relation_name=relation_name,
                relation_cardinalities=relation_cardinalities,
            )
            append_plan_shape_finding(
                finding=finding,
                relation_name=relation_name,
                relation_cardinalities=relation_cardinalities,
                minimum_blocking_cardinality=minimum_blocking_cardinality,
                blocking=blocking,
                observations=observations,
            )
    if measured_execution_ms > effective_execution_threshold_ms:
        finding = (
            f"execution time {measured_execution_ms:.2f} ms exceeded "
            f"{effective_execution_threshold_ms:.2f} ms"
        )
        if timing_mode is TimingMode.ENFORCE:
            blocking.append(finding)
        else:
            observations.append(finding)
    if analysis.temp_blocks > 0:
        blocking.append(f"query used {analysis.temp_blocks} temp blocks")
    return AnalysisFindings(blocking=tuple(blocking), observations=tuple(observations))


def cardinality_finding(
    *,
    description: str,
    relation_name: str,
    relation_cardinalities: Mapping[str, int],
) -> str:
    cardinality = relation_cardinalities.get(relation_name)
    if cardinality is None:
        return f"{description} on relation {relation_name} with unknown cardinality"
    return f"{description} on {cardinality}-row relation {relation_name}"


def append_plan_shape_finding(  # noqa: PLR0913
    *,
    finding: str,
    relation_name: str,
    relation_cardinalities: Mapping[str, int],
    minimum_blocking_cardinality: int,
    blocking: list[str],
    observations: list[str],
) -> None:
    cardinality = relation_cardinalities.get(relation_name)
    if cardinality is None or cardinality >= minimum_blocking_cardinality:
        blocking.append(finding)
    else:
        observations.append(finding)


def iter_plan_nodes(plan: JsonObject) -> Iterator[JsonObject]:
    yield plan
    raw_children = plan.get("Plans", ())
    if isinstance(raw_children, Sequence) and not isinstance(raw_children, str):
        for child in raw_children:
            if isinstance(child, Mapping):
                yield from iter_plan_nodes(cast("JsonObject", child))


def read_text_value(*, node: JsonObject, key: str) -> str:
    value = read_optional_text_value(node=node, key=key)
    if value is None:
        msg = f"Plan node is missing {key}"
        raise ValueError(msg)
    return value


def read_optional_text_value(*, node: JsonObject, key: str) -> str | None:
    value = node.get(key)
    return value if isinstance(value, str) else None


def read_int_value(*, node: JsonObject, key: str) -> int:
    value = node.get(key)
    return int(cast("int | float", value)) if isinstance(value, int | float) else 0
