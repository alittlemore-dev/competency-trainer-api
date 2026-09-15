from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

JsonObject = Mapping[str, object]
DatabaseParams = Mapping[str, object] | tuple[object, ...]


class QueryThresholdGroup(StrEnum):
    POINT_READ = "point_read"
    LIST_READ = "list_read"
    SEARCH = "search"
    AGGREGATE = "aggregate"
    SMALL_WRITE = "small_write"
    HEAVY = "heavy"


class TimingMode(StrEnum):
    ENFORCE = "enforce"
    OBSERVE = "observe"


@dataclass(frozen=True, slots=True)
class AuthCardinalities:
    users: int
    sessions: int


@dataclass(frozen=True, slots=True)
class ArticleCardinalities:
    folders: int
    articles: int
    published_percentage: int
    fts_match_percentage: int
    tags: int
    article_tag_links: int
    daily_analytics: int
    reactions: int


@dataclass(frozen=True, slots=True)
class MatrixCardinalities:
    sheets: int
    sections_per_sheet: int
    subsections_per_section: int
    items: int
    resources: int
    resource_links: int
    queued_questions: int


@dataclass(frozen=True, slots=True)
class AgentAccessCardinalities:
    audit_events: int


@dataclass(frozen=True, slots=True)
class ProfileCardinalities:
    auth: AuthCardinalities
    articles: ArticleCardinalities
    matrix: MatrixCardinalities
    agent_access: AgentAccessCardinalities


@dataclass(frozen=True, slots=True)
class ExpectedIndex:
    name: str
    relation_name: str


@dataclass(frozen=True, slots=True)
class ScenarioPlanShapeOverride:
    expected_indexes: tuple[ExpectedIndex, ...]
    forbidden_seq_scan_relations: tuple[str, ...]
    allow_seq_scan_reason: str | None


@dataclass(frozen=True, slots=True)
class QueryPlanProfile:
    name: str
    cardinalities: ProfileCardinalities
    timing_mode: TimingMode
    explain_runs: int
    explain_work_mem_mb: int
    scenario_plan_shape_overrides: Mapping[str, ScenarioPlanShapeOverride]

    @property
    def relation_cardinalities(self) -> Mapping[str, int]:
        cardinalities = self.cardinalities
        matrix = cardinalities.matrix
        section_count = matrix.sheets * matrix.sections_per_sheet
        subsection_count = section_count * matrix.subsections_per_section
        return {
            "auth__user_model": cardinalities.auth.users,
            "auth__auth_session_model": cardinalities.auth.sessions,
            "articles__article_folder_model": cardinalities.articles.folders,
            "articles__article_model": cardinalities.articles.articles,
            "articles__tag_model": cardinalities.articles.tags,
            "articles__article_to_tag_secondary_model": (cardinalities.articles.article_tag_links),
            "articles__article_daily_analytics_model": cardinalities.articles.daily_analytics,
            "articles__article_reaction_model": cardinalities.articles.reactions,
            "competency_matrix__competency_matrix_sheet_model": matrix.sheets,
            "competency_matrix__competency_matrix_section_model": section_count,
            "competency_matrix__competency_matrix_subsection_model": subsection_count,
            "competency_matrix__competency_matrix_item_model": matrix.items,
            "competency_matrix__external_resource_model": matrix.resources,
            "competency_matrix__resource_to_item_secondary_model": matrix.resource_links,
            "competency_matrix__queued_question_model": matrix.queued_questions,
            "agent_access__agent_audit_event_model": cardinalities.agent_access.audit_events,
        }


@dataclass(frozen=True, slots=True)
class PlanExpectation:
    max_execution_ms: float
    threshold_source: str
    expected_indexes: tuple[ExpectedIndex, ...]
    forbidden_seq_scan_relations: tuple[str, ...]
    allow_seq_scan_reason: str | None


@dataclass(frozen=True, slots=True)
class CapturedQuery:
    name: str
    storage_class: str
    method_name: str
    scenario_name: str
    ordinal: int
    sql: str
    normalized_sql: str
    params: DatabaseParams
    elapsed_ms: float
    executemany: bool
    expectation: PlanExpectation


@dataclass(frozen=True, slots=True)
class CompiledQuery:
    name: str
    sql: str
    params: DatabaseParams


@dataclass(frozen=True, slots=True)
class PlanAnalysis:
    name: str
    planning_time_ms: float
    execution_time_ms: float
    node_types: tuple[str, ...]
    index_names: tuple[str, ...]
    seq_scan_relations: tuple[str, ...]
    temp_blocks: int
    blocking_findings: tuple[str, ...]
    observations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    query: CapturedQuery
    compiled_query: CompiledQuery
    explain_json_runs: tuple[object, ...]
    analyses: tuple[PlanAnalysis, ...]
    warm_execution_ms: float
    baseline_execution_ms: float | None
    effective_execution_threshold_ms: float
    execution_time_exceeded: bool
    blocking_findings: tuple[str, ...]
    observations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class QueryPlanBaseline:
    profile_name: str
    source_sha: str
    sample_count: int
    query_warm_execution_ms: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class StorageMethod:
    storage_class: str
    method_name: str
    module_name: str


@dataclass(frozen=True, slots=True)
class CoverageReport:
    discovered_methods: tuple[StorageMethod, ...]
    covered_methods: tuple[StorageMethod, ...]
    missing_methods: tuple[StorageMethod, ...]
    unexpected_methods: tuple[StorageMethod, ...]


@dataclass(frozen=True, slots=True)
class CliArgs:
    profile: str
    report_dir: Path
    fail_on_finding: bool
    allow_non_test_db: bool


REALISTIC_PROFILE = QueryPlanProfile(
    name="realistic",
    cardinalities=ProfileCardinalities(
        auth=AuthCardinalities(users=100, sessions=500),
        articles=ArticleCardinalities(
            folders=20,
            articles=5_000,
            published_percentage=80,
            fts_match_percentage=1,
            tags=500,
            article_tag_links=20_000,
            daily_analytics=100_000,
            reactions=10_000,
        ),
        matrix=MatrixCardinalities(
            sheets=20,
            sections_per_sheet=8,
            subsections_per_section=12,
            items=10_000,
            resources=5_000,
            resource_links=25_000,
            queued_questions=5_000,
        ),
        agent_access=AgentAccessCardinalities(audit_events=10_000),
    ),
    timing_mode=TimingMode.ENFORCE,
    explain_runs=3,
    explain_work_mem_mb=16,
    scenario_plan_shape_overrides={},
)

STRESS_PROFILE = QueryPlanProfile(
    name="stress",
    cardinalities=ProfileCardinalities(
        auth=AuthCardinalities(users=10_000, sessions=50_000),
        articles=ArticleCardinalities(
            folders=200,
            articles=200_000,
            published_percentage=80,
            fts_match_percentage=1,
            tags=30_000,
            article_tag_links=500_000,
            daily_analytics=2_000_000,
            reactions=500_000,
        ),
        matrix=MatrixCardinalities(
            sheets=20,
            sections_per_sheet=8,
            subsections_per_section=12,
            items=200_000,
            resources=200_000,
            resource_links=500_000,
            queued_questions=50_000,
        ),
        agent_access=AgentAccessCardinalities(audit_events=250_000),
    ),
    timing_mode=TimingMode.OBSERVE,
    explain_runs=3,
    explain_work_mem_mb=64,
    scenario_plan_shape_overrides={},
)
