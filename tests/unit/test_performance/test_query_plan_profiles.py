import pytest

from performance.query_plans import models as query_plan_models
from performance.query_plans.expectations import ABSOLUTE_SLA_POLICY
from performance.query_plans.runner import get_profile
from performance.query_plans.scenarios import STORAGE_SCENARIOS


class TestQueryPlanProfiles:
    def test_realistic_profile_has_explicit_representative_cardinalities(self) -> None:
        profile = get_profile(name="realistic")

        assert profile is query_plan_models.REALISTIC_PROFILE
        assert profile.name == "realistic"
        assert profile.timing_mode is query_plan_models.TimingMode.ENFORCE
        assert profile.explain_runs == 3
        assert profile.explain_work_mem_mb == 16
        assert profile.cardinalities == query_plan_models.ProfileCardinalities(
            auth=query_plan_models.AuthCardinalities(users=100, sessions=500),
            articles=query_plan_models.ArticleCardinalities(
                folders=20,
                articles=5_000,
                published_percentage=80,
                fts_match_percentage=1,
                tags=500,
                article_tag_links=20_000,
                daily_analytics=100_000,
                reactions=10_000,
            ),
            matrix=query_plan_models.MatrixCardinalities(
                sheets=20,
                sections_per_sheet=8,
                subsections_per_section=12,
                items=10_000,
                resources=5_000,
                resource_links=25_000,
                queued_questions=5_000,
            ),
            agent_access=query_plan_models.AgentAccessCardinalities(audit_events=10_000),
        )

    def test_stress_profile_has_explicit_large_cardinalities(self) -> None:
        profile = get_profile(name="stress")

        assert profile is query_plan_models.STRESS_PROFILE
        assert profile.name == "stress"
        assert profile.timing_mode is query_plan_models.TimingMode.OBSERVE
        assert profile.explain_runs == 3
        assert profile.explain_work_mem_mb == 64
        assert profile.cardinalities == query_plan_models.ProfileCardinalities(
            auth=query_plan_models.AuthCardinalities(users=10_000, sessions=50_000),
            articles=query_plan_models.ArticleCardinalities(
                folders=200,
                articles=200_000,
                published_percentage=80,
                fts_match_percentage=1,
                tags=30_000,
                article_tag_links=500_000,
                daily_analytics=2_000_000,
                reactions=500_000,
            ),
            matrix=query_plan_models.MatrixCardinalities(
                sheets=20,
                sections_per_sheet=8,
                subsections_per_section=12,
                items=200_000,
                resources=200_000,
                resource_links=500_000,
                queued_questions=50_000,
            ),
            agent_access=query_plan_models.AgentAccessCardinalities(audit_events=250_000),
        )

    def test_profiles_expose_relation_cardinalities_for_plan_classification(self) -> None:
        profile = query_plan_models.REALISTIC_PROFILE

        assert profile.relation_cardinalities == {
            "auth__user_model": 100,
            "auth__auth_session_model": 500,
            "articles__article_folder_model": 20,
            "articles__article_model": 5_000,
            "articles__tag_model": 500,
            "articles__article_to_tag_secondary_model": 20_000,
            "articles__article_daily_analytics_model": 100_000,
            "articles__article_reaction_model": 10_000,
            "competency_matrix__competency_matrix_sheet_model": 20,
            "competency_matrix__competency_matrix_section_model": 160,
            "competency_matrix__competency_matrix_subsection_model": 1_920,
            "competency_matrix__competency_matrix_item_model": 10_000,
            "competency_matrix__external_resource_model": 5_000,
            "competency_matrix__resource_to_item_secondary_model": 25_000,
            "competency_matrix__queued_question_model": 5_000,
            "agent_access__agent_audit_event_model": 10_000,
        }

    def test_balanced_profile_is_not_supported(self) -> None:
        assert not hasattr(query_plan_models, "BALANCED_PROFILE")
        assert not hasattr(query_plan_models, "DatasetProfile")

        with pytest.raises(ValueError, match="Unknown query plan profile: balanced"):
            get_profile(name="balanced")

    def test_resource_search_plan_shape_requires_trigram_indexes_for_scaled_profiles(
        self,
    ) -> None:
        scenario = next(
            scenario for scenario in STORAGE_SCENARIOS if scenario.name == "resources_exact_en"
        )

        realistic_expectation = scenario.plan_expectation(
            policy=ABSOLUTE_SLA_POLICY,
            query_name=None,
            profile=query_plan_models.REALISTIC_PROFILE,
        )
        stress_expectation = scenario.plan_expectation(
            policy=ABSOLUTE_SLA_POLICY,
            query_name=None,
            profile=query_plan_models.STRESS_PROFILE,
        )

        expected_indexes = {
            "cm_external_resource_name_en_trgm_idx",
            "cm_external_resource_name_ru_trgm_idx",
            "cm_external_resource_url_trgm_idx",
        }
        for expectation in (realistic_expectation, stress_expectation):
            assert {index.name for index in expectation.expected_indexes} == expected_indexes
            assert expectation.forbidden_seq_scan_relations == (
                "competency_matrix__external_resource_model",
            )
            assert expectation.allow_seq_scan_reason is None

    @pytest.mark.parametrize(
        "scenario_name",
        [
            "auth_session_list_user_sessions",
            "auth_session_revoke_user_sessions",
            "auth_session_revoke_user_sessions_except",
        ],
    )
    def test_scaled_auth_session_scenarios_require_expiry_index(
        self,
        scenario_name: str,
    ) -> None:
        scenario = next(
            scenario for scenario in STORAGE_SCENARIOS if scenario.name == scenario_name
        )

        expectation = scenario.plan_expectation(
            policy=ABSOLUTE_SLA_POLICY,
            query_name=None,
            profile=query_plan_models.STRESS_PROFILE,
        )

        assert tuple(index.name for index in expectation.expected_indexes) == (
            "auth_sessions_username_lower_active_expiry_idx",
        )
