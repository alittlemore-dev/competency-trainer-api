from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from performance.query_plans.models import ExpectedIndex, PlanExpectation, QueryThresholdGroup


@dataclass(frozen=True, slots=True)
class QueryThresholdPolicy:
    group_max_execution_ms: Mapping[QueryThresholdGroup, float]
    scenario_max_execution_ms: Mapping[str, float]
    query_max_execution_ms: Mapping[str, float]
    query_expected_indexes: Mapping[str, tuple[ExpectedIndex, ...]]


def scenario_plan_expectation(  # noqa: PLR0913
    *,
    scenario_name: str,
    group: QueryThresholdGroup,
    policy: QueryThresholdPolicy,
    query_name: str | None,
    expected_indexes: tuple[ExpectedIndex, ...],
    forbidden_seq_scan_relations: tuple[str, ...],
    allow_seq_scan_reason: str | None,
) -> PlanExpectation:
    effective_expected_indexes = (
        expected_indexes
        if query_name is None
        else policy.query_expected_indexes.get(query_name, expected_indexes)
    )
    if query_name is not None:
        query_override = policy.query_max_execution_ms.get(query_name)
        if query_override is not None:
            return PlanExpectation(
                max_execution_ms=query_override,
                threshold_source=f"override:{query_name}",
                expected_indexes=effective_expected_indexes,
                forbidden_seq_scan_relations=forbidden_seq_scan_relations,
                allow_seq_scan_reason=allow_seq_scan_reason,
            )
    scenario_override = policy.scenario_max_execution_ms.get(scenario_name)
    if scenario_override is not None:
        return PlanExpectation(
            max_execution_ms=scenario_override,
            threshold_source=f"override:{scenario_name}",
            expected_indexes=effective_expected_indexes,
            forbidden_seq_scan_relations=forbidden_seq_scan_relations,
            allow_seq_scan_reason=allow_seq_scan_reason,
        )
    return PlanExpectation(
        max_execution_ms=policy.group_max_execution_ms[group],
        threshold_source=f"group:{group.value}",
        expected_indexes=effective_expected_indexes,
        forbidden_seq_scan_relations=forbidden_seq_scan_relations,
        allow_seq_scan_reason=allow_seq_scan_reason,
    )


INDEX_RELATION_NAMES: Mapping[str, str] = {
    "articles__article_folder_model_pkey": "articles__article_folder_model",
    "articles__tag_model_pkey": "articles__tag_model",
    "articles_article_publish_status_published_updated_idx": "articles__article_model",
    "articles_article_tree_folder_en_published_idx": "articles__article_model",
    "articles_folder_key_lower_uniq": "articles__article_folder_model",
    "articles_tag_name_en_trgm_idx": "articles__tag_model",
    "articles_tag_name_ru_trgm_idx": "articles__tag_model",
    "articles_tag_slug_trgm_idx": "articles__tag_model",
    "auth__auth_session_model_pkey": "auth__auth_session_model",
    "auth_sessions_expiry_idx": "auth__auth_session_model",
    "auth_sessions_secret_hash_uniq": "auth__auth_session_model",
    "auth_sessions_username_lower_active_expiry_idx": "auth__auth_session_model",
    "auth_sessions_username_lower_active_last_used_idx": "auth__auth_session_model",
    "cm_external_resource_name_en_trgm_idx": "competency_matrix__external_resource_model",
    "cm_external_resource_name_ru_trgm_idx": "competency_matrix__external_resource_model",
    "cm_external_resource_url_trgm_idx": "competency_matrix__external_resource_model",
    "cm_queued_question_fifo_idx": "competency_matrix__queued_question_model",
    "cm_queued_question_fingerprint_idx": "competency_matrix__queued_question_model",
    "cmi_question_en_fingerprint_idx": "competency_matrix__competency_matrix_item_model",
    "cmi_question_ru_fingerprint_idx": "competency_matrix__competency_matrix_item_model",
    "competency_matrix__competency_matrix_subsection_model_pkey": (
        "competency_matrix__competency_matrix_subsection_model"
    ),
    "competency_matrix__external_resource_model_pkey": (
        "competency_matrix__external_resource_model"
    ),
    "competency_matrix__queued_question_model_pkey": ("competency_matrix__queued_question_model"),
    "users_managed_accounts_list_idx": "auth__user_model",
    "users_username_idx": "auth__user_model",
    "users_username_lower_uniq": "auth__user_model",
}


def expected_indexes_from_names(*, names: Iterable[str]) -> tuple[ExpectedIndex, ...]:
    try:
        return tuple(
            ExpectedIndex(name=name, relation_name=INDEX_RELATION_NAMES[name]) for name in names
        )
    except KeyError as error:
        msg = f"Query-plan index {error.args[0]!r} has no owning relation mapping"
        raise ValueError(msg) from error


ABSOLUTE_SLA_POLICY = QueryThresholdPolicy(
    group_max_execution_ms={
        QueryThresholdGroup.POINT_READ: 25.0,
        QueryThresholdGroup.LIST_READ: 250.0,
        QueryThresholdGroup.SEARCH: 150.0,
        QueryThresholdGroup.AGGREGATE: 250.0,
        QueryThresholdGroup.SMALL_WRITE: 100.0,
        QueryThresholdGroup.HEAVY: 300.0,
    },
    scenario_max_execution_ms={
        "articles_published_for_seo_sitemap": 250.0,
        "tags_short_en": 250.0,
        "resources_short_en": 300.0,
    },
    query_max_execution_ms={
        "articles_list_en_full_text_tag_date__002": 250.0,
        "articles_list_ru_full_text__002": 250.0,
    },
    query_expected_indexes={
        "managed_accounts_list__001": expected_indexes_from_names(
            names=("users_username_lower_uniq",),
        ),
        "managed_accounts_list__002": expected_indexes_from_names(
            names=("users_managed_accounts_list_idx",),
        ),
        "managed_accounts_update_role__001": expected_indexes_from_names(
            names=("users_username_lower_uniq",),
        ),
        "managed_accounts_update_role__002": expected_indexes_from_names(
            names=("users_username_idx",),
        ),
        "managed_accounts_update_password__001": expected_indexes_from_names(
            names=("users_username_lower_uniq",),
        ),
        "managed_accounts_update_password__002": expected_indexes_from_names(
            names=("users_username_idx",),
        ),
        "managed_accounts_activate__001": expected_indexes_from_names(
            names=("users_username_lower_uniq",),
        ),
        "managed_accounts_activate__002": expected_indexes_from_names(
            names=("users_username_idx",),
        ),
        "managed_accounts_deactivate__001": expected_indexes_from_names(
            names=("users_username_lower_uniq",),
        ),
        "managed_accounts_deactivate__002": expected_indexes_from_names(
            names=("users_username_idx",),
        ),
        "managed_accounts_delete__001": expected_indexes_from_names(
            names=("users_username_lower_uniq",),
        ),
        "managed_accounts_delete__002": expected_indexes_from_names(
            names=("users_username_idx",),
        ),
    },
)
