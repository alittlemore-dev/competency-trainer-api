from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from hashlib import md5

from sqlalchemy.ext.asyncio import AsyncSession

from core.account.schemas import ManagedAccountFilters
from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.schemas import (
    AgentAuditEventCreateParams,
    AgentAuditEventPageQuery,
    AgentCertificate,
    AgentCertificateRotation,
    AgentClient,
    AgentClientRevokeParams,
    MatrixQuestionDraftCompletion,
)
from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.schemas import Article, ArticleFilters, ArticleFolder, ArticleMetadata, Tag, Tags
from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.schemas import AuthSessionClientMetadata, AuthSessionCreate
from core.auth.types import SessionSecretHash
from core.competency_matrix.enums import (
    CompetencyMatrixWorkspaceSortEnum,
    GradeEnum,
    InterviewFrequencyEnum,
)
from core.competency_matrix.schemas import (
    AttachedExternalResource,
    AttachedExternalResources,
    CompetencyMatrixItem,
    CompetencyMatrixItemFilters,
    CompetencyMatrixItemStructure,
    CompetencyMatrixQuestionFingerprint,
    CompetencyMatrixSectionCreateParams,
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetCreateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixSubsectionCreateParams,
    CompetencyMatrixSubsectionPriorityUpdateParams,
    CompetencyMatrixWorkspaceFilters,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestionsCreateParams,
)
from core.contacts.schemas import ContactMe
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from infra.postgresql.storages.agent_access import AgentAccessDatabaseStorage
from infra.postgresql.storages.articles import (
    ArticleAnalyticsDatabaseStorage,
    ArticlesDatabaseStorage,
)
from infra.postgresql.storages.auth import AuthDatabaseStorage, AuthSessionDatabaseStorage
from infra.postgresql.storages.competency_matrix import CompetencyMatrixDatabaseStorage
from infra.postgresql.storages.contacts import ContactMeDatabaseStorage
from infra.postgresql.storages.users import UserAccountDatabaseStorage
from performance.query_plans.expectations import (
    QueryThresholdPolicy,
    expected_indexes_from_names,
    scenario_plan_expectation,
)
from performance.query_plans.models import (
    CoverageReport,
    ExpectedIndex,
    PlanExpectation,
    QueryPlanProfile,
    QueryThresholdGroup,
    StorageMethod,
)

ScenarioRunner = Callable[[AsyncSession], Awaitable[None]]


def hex_id(value: int) -> str:
    return f"{value:032x}"


SEED_NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
SEED_USERNAME = "benchmark"
NEW_AUTH_HASH = "query-plan-auth-hash"
NEW_MANAGED_ACCOUNT_USERNAME = "query-plan-admin"
NEW_ARTICLE_ID = "10000000000040008000000000000001"
NEW_CONTACT_ID = "10000000000040008000000000000002"
NEW_ARTICLE_ANALYTICS_VOTER = "query-plan-voter-hash"
NEW_ARTICLE_FOLDER_ID = "10000000000040008000000000000003"
EXISTING_ARTICLE_FOLDER_ID = "30000000000040008000000000000001"
EXISTING_ARTICLE_CONTENT_FILE_ID = hex_id(1)
NEW_TAG_ID = hex_id(90_000_001)
NEW_MATRIX_ITEM_ID = hex_id(900_001)
NEW_MATRIX_SHEET_KEY = "query-plan-new-sheet"
PYTHON_TAG_ID = hex_id(1)
POSTGRESQL_TAG_ID = hex_id(2)
PYDANTIC_TAG_ID = hex_id(3)
DELETABLE_TAG_ID = hex_id(4)
PYTHON_RESOURCE_ID = hex_id(1)
POSTGRESQL_RESOURCE_ID = hex_id(2)
PYDANTIC_RESOURCE_ID = hex_id(3)
PYTHON_SHEET_ID = hex_id(1)
POSTGRESQL_SHEET_ID = hex_id(2)
PYDANTIC_SHEET_ID = hex_id(3)
PYTHON_SECTION_ID = hex_id(1)
PYTHON_SUBSECTION_ID = hex_id(1)
EXISTING_MATRIX_ITEM_ID = hex_id(100)
DELETABLE_MATRIX_ITEM_ID = hex_id(101)
EXISTING_QUEUED_QUESTION_ID = hex_id(100)
DELETABLE_QUEUED_QUESTION_ID = hex_id(101)
DELETABLE_MATRIX_QUESTION_CLAIM_ID = hex_id(61_002)
AGENT_CLIENT_ID = hex_id(60_001)
CLAIMABLE_AGENT_CLIENT_ID = hex_id(60_003)
REVOKABLE_AGENT_CLIENT_ID = hex_id(60_004)
AGENT_CERTIFICATE_ID = hex_id(62_001)
CLAIMABLE_AGENT_CERTIFICATE_ID = hex_id(62_003)
AGENT_ROTATION_ID = "query-plan-pending-rotation"
AGENT_COMPLETION_ID = hex_id(63_001)
SHORT_TRIGRAM_ALLOW_REASON = (
    "short search string has too few extractable trigrams for an index-selective search"
)


def seeded_auth_session_hash(value: int) -> SessionSecretHash:
    first = md5(f"session-a-{value}".encode(), usedforsecurity=False).hexdigest()
    second = md5(f"session-b-{value}".encode(), usedforsecurity=False).hexdigest()
    return SessionSecretHash(f"{first}{second}")


@dataclass(frozen=True, slots=True)
class StorageScenario:
    name: str
    storage_class: str
    method_name: str
    group: QueryThresholdGroup
    expected_indexes: tuple[ExpectedIndex, ...]
    forbidden_seq_scan_relations: tuple[str, ...]
    allow_seq_scan_reason: str | None
    run: ScenarioRunner

    def plan_expectation(
        self,
        *,
        policy: QueryThresholdPolicy,
        query_name: str | None,
        profile: QueryPlanProfile,
    ) -> PlanExpectation:
        expectation = scenario_plan_expectation(
            scenario_name=self.name,
            group=self.group,
            policy=policy,
            query_name=query_name,
            expected_indexes=self.expected_indexes,
            forbidden_seq_scan_relations=self.forbidden_seq_scan_relations,
            allow_seq_scan_reason=self.allow_seq_scan_reason,
        )
        override = profile.scenario_plan_shape_overrides.get(self.name)
        if override is None:
            return expectation
        return replace(
            expectation,
            expected_indexes=override.expected_indexes,
            forbidden_seq_scan_relations=override.forbidden_seq_scan_relations,
            allow_seq_scan_reason=override.allow_seq_scan_reason,
        )


def evaluate_storage_method_coverage(
    *,
    discovered_methods: Sequence[StorageMethod],
    scenarios: Sequence[StorageScenario],
) -> CoverageReport:
    discovered_by_key = {
        (method.storage_class, method.method_name): method for method in discovered_methods
    }
    scenario_keys = {(scenario.storage_class, scenario.method_name) for scenario in scenarios}
    covered_methods = tuple(
        method
        for method in discovered_methods
        if (method.storage_class, method.method_name) in scenario_keys
    )
    missing_methods = tuple(
        method
        for method in discovered_methods
        if (method.storage_class, method.method_name) not in scenario_keys
    )
    unexpected_methods = tuple(
        StorageMethod(storage_class=storage_class, method_name=method_name, module_name="")
        for storage_class, method_name in sorted(scenario_keys)
        if (storage_class, method_name) not in discovered_by_key
    )
    return CoverageReport(
        discovered_methods=tuple(discovered_methods),
        covered_methods=covered_methods,
        missing_methods=missing_methods,
        unexpected_methods=unexpected_methods,
    )


def coverage_findings(*, coverage: CoverageReport) -> tuple[str, ...]:
    return (
        *(
            f"missing query-plan storage scenario for {method.storage_class}.{method.method_name}"
            for method in coverage.missing_methods
        ),
        *(
            f"query-plan storage scenario references unknown method "
            f"{method.storage_class}.{method.method_name}"
            for method in coverage.unexpected_methods
        ),
    )


async def run_user_get_by_username(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).get_user_by_username(SEED_USERNAME)


async def run_list_managed_accounts(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).list_managed_accounts(
        filters=ManagedAccountFilters(page=1, page_size=20),
    )


async def run_get_managed_account(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).get_managed_account(username=SEED_USERNAME)


async def run_create_managed_account(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).create_managed_account(
        username=NEW_MANAGED_ACCOUNT_USERNAME,
        role=RoleEnum.ADMIN,
        password_hash=NEW_AUTH_HASH,
        is_active=True,
    )


async def run_update_managed_account_role(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).update_managed_account_role(
        username=SEED_USERNAME,
        role=RoleEnum.MODERATOR,
    )


async def run_update_managed_account_password(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).update_managed_account_password(
        username=SEED_USERNAME,
        password_hash=NEW_AUTH_HASH,
    )


async def run_activate_managed_account(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).activate_managed_account(
        username="benchmark-user-2",
    )


async def run_deactivate_managed_account(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).deactivate_managed_account(
        username=SEED_USERNAME,
    )


async def run_delete_managed_account(session: AsyncSession) -> None:
    await UserAccountDatabaseStorage(session=session).delete_managed_account(
        username="benchmark-user-100",
    )


async def run_update_user_password_hash(session: AsyncSession) -> None:
    await AuthDatabaseStorage(session=session).update_user_password_hash(
        SEED_USERNAME,
        NEW_AUTH_HASH,
    )


async def run_create_auth_session(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).create_session(
        session=AuthSessionCreate(
            username=SEED_USERNAME,
            secret_hash=SessionSecretHash(
                "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            ),
            expires_at=SEED_NOW + timedelta(days=30),
            absolute_expires_at=SEED_NOW + timedelta(days=30),
            is_revoked=False,
            last_used_at=SEED_NOW,
            auth_method=AuthSessionAuthMethodEnum.PASSWORD,
            client_metadata=AuthSessionClientMetadata(
                user_agent_display="Chrome on Linux",
                user_agent_browser="Chrome",
                user_agent_os="Linux",
                user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
            ),
        ),
    )


async def run_get_auth_session_by_secret_hash(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).get_session_by_secret_hash(
        secret_hash=seeded_auth_session_hash(1),
    )


async def run_get_auth_session_by_id(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).get_session_by_id(session_id=hex_id(1))


async def run_list_user_auth_sessions(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).list_user_sessions(
        username=SEED_USERNAME,
        active_at=SEED_NOW,
    )


async def run_extend_auth_session_expiry(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).extend_session_expiry(
        session_id=hex_id(1),
        expires_at=SEED_NOW + timedelta(days=31),
        last_used_at=SEED_NOW + timedelta(minutes=1),
    )


async def run_delete_expired_auth_sessions(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).delete_expired_sessions(
        expires_at=SEED_NOW,
    )


async def run_count_cleanup_auth_sessions(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).count_cleanup_sessions(
        expired_at=SEED_NOW,
        expiring_soon_at=SEED_NOW + timedelta(days=7),
    )


async def run_revoke_auth_session_by_secret_hash(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).revoke_session_by_secret_hash(
        secret_hash=seeded_auth_session_hash(2),
    )


async def run_revoke_user_auth_sessions(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).revoke_user_sessions(username=SEED_USERNAME)


async def run_revoke_user_auth_session(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).revoke_user_session(
        username=SEED_USERNAME,
        session_id=hex_id(1),
    )


async def run_revoke_other_user_auth_sessions(session: AsyncSession) -> None:
    await AuthSessionDatabaseStorage(session=session).revoke_user_sessions_except(
        username=SEED_USERNAME,
        except_session_id=hex_id(1),
    )


async def run_create_contact_me_request(session: AsyncSession) -> None:
    await ContactMeDatabaseStorage(session=session).create_contact_me_request(
        ContactMe(
            id=NEW_CONTACT_ID,
            name="Query Plan",
            email="query-plan@example.test",
            telegram=None,
            message="Please include contact writes in query plan smoke.",
        ),
    )


async def run_get_article_by_slug(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).get_article_by_slug(
        slug="article-100",
        lock=False,
    )


async def run_list_articles_en_full_text_tag_date(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_articles(
        filters=ArticleFilters(
            page=1,
            page_size=20,
            language=LanguageEnum.EN,
            only_published=True,
            tag_slug="postgresql",
            published_from=date(2025, 1, 1),
            published_to=date(2026, 5, 31),
            search_query="full text search",
            include_tags=True,
        ),
    )


async def run_list_articles_ru_full_text(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_articles(
        filters=ArticleFilters(
            page=1,
            page_size=20,
            language=LanguageEnum.RU,
            only_published=False,
            publish_status=PublishStatusEnum.PUBLISHED,
            tag_slug=None,
            published_from=None,
            published_to=None,
            search_query="полнотекстовый поиск",
            include_tags=True,
        ),
    )


async def run_list_articles_for_seo(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_articles(
        filters=ArticleFilters(
            only_published=True,
            include_tags=False,
            include_files=False,
            order_for_seo=True,
        ),
    )


async def run_list_tree_items(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_tree_items(
        only_published=True,
        language=LanguageEnum.EN,
    )


async def run_create_article(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).create_article(article=write_article())


async def run_update_article(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).update_article(
        article=write_article_for_existing_article(),
    )


async def run_delete_article(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).delete_article(slug="article-101")


async def run_update_article_publish_status(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).update_article_publish_status(
        slug="article-102",
        publish_status=PublishStatusEnum.DRAFT,
    )


async def run_get_article_folder_by_id(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).get_folder_by_id(
        folder_id=EXISTING_ARTICLE_FOLDER_ID,
    )


async def run_list_article_folders(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_folders(language=LanguageEnum.EN)


async def run_next_article_folder_priority(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).next_folder_priority()


async def run_article_folder_key_exists(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).folder_key_exists(key="engineering")


async def run_create_article_folder(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).create_folder(folder=write_article_folder())


async def run_update_article_folder_priorities(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).update_folder_priorities(
        ordered_ids=(EXISTING_ARTICLE_FOLDER_ID,),
    )


async def run_get_tags_by_ids(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).get_tags_by_ids(
        tag_ids=[PYTHON_TAG_ID, POSTGRESQL_TAG_ID, PYDANTIC_TAG_ID],
    )


async def run_list_tags(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_tags(
        language=LanguageEnum.EN,
        only_with_published_articles=False,
    )


async def run_list_public_tags(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).list_tags(
        language=LanguageEnum.EN,
        only_with_published_articles=True,
    )


async def run_search_tags_exact(session: AsyncSession) -> None:
    await run_search_tags(session=session, search_name="python")


async def run_search_tags_substring(session: AsyncSession) -> None:
    await run_search_tags(session=session, search_name="thon")


async def run_search_tags_fuzzy(session: AsyncSession) -> None:
    await run_search_tags(session=session, search_name="pythno")


async def run_search_tags_short(session: AsyncSession) -> None:
    await run_search_tags(session=session, search_name="py")


async def run_search_tags(*, session: AsyncSession, search_name: str) -> None:
    await ArticlesDatabaseStorage(session=session).search_tags(
        search_name=search_name,
        limit=10,
        language=LanguageEnum.EN,
    )


async def run_create_tag(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).create_tag(
        tag=Tag(
            id=NEW_TAG_ID,
            name_ru="Новый performance тег",
            name_en="New performance tag",
            slug="query-plan-new-tag",
        ),
    )


async def run_update_tag(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).update_tag(
        tag=Tag(
            id=PYTHON_TAG_ID,
            name_ru="Питон обновленный",
            name_en="Python updated",
            slug="python",
        ),
    )


async def run_delete_tag(session: AsyncSession) -> None:
    await ArticlesDatabaseStorage(session=session).delete_tag(tag_id=DELETABLE_TAG_ID)


async def run_increment_view(session: AsyncSession) -> None:
    await ArticleAnalyticsDatabaseStorage(session=session).increment_view(
        article_id=article_id(100),
        source_category=ArticleViewSourceCategory.DIRECT,
        viewed_on=SEED_NOW.date(),
    )


async def run_increment_engaged_view(session: AsyncSession) -> None:
    await ArticleAnalyticsDatabaseStorage(session=session).increment_engaged_view(
        article_id=article_id(100),
        source_category=ArticleViewSourceCategory.SEARCH,
        viewed_on=SEED_NOW.date(),
    )


async def run_get_public_stats(session: AsyncSession) -> None:
    await ArticleAnalyticsDatabaseStorage(session=session).get_public_stats(
        article_ids=[article_id(100), article_id(200)],
    )


async def run_get_reaction_counts(session: AsyncSession) -> None:
    await ArticleAnalyticsDatabaseStorage(session=session).get_reaction_counts(
        article_ids=[article_id(100), article_id(200)],
    )


async def run_set_reaction(session: AsyncSession) -> None:
    await ArticleAnalyticsDatabaseStorage(session=session).set_reaction(
        article_id=article_id(100),
        article_scoped_voter_hash=NEW_ARTICLE_ANALYTICS_VOTER,
        reaction_kind=ArticleReactionKind.HEART,
    )


async def run_get_daily_stats(session: AsyncSession) -> None:
    await ArticleAnalyticsDatabaseStorage(session=session).get_daily_stats(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        language=LanguageEnum.EN,
    )


async def run_list_sheets(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).list_sheets()


async def run_list_matrix_structure(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).list_structure()


async def run_get_item_structure_by_subsection_id(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).get_item_structure_by_subsection_id(
        subsection_id=PYTHON_SUBSECTION_ID,
    )


async def run_create_matrix_sheet(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).create_sheet(
        params=CompetencyMatrixSheetCreateParams(
            key=NEW_MATRIX_SHEET_KEY,
            name_ru="Новый лист query plan",
            name_en="Query plan new sheet",
        ),
    )


async def run_create_matrix_section(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).create_section(
        params=CompetencyMatrixSectionCreateParams(
            sheet_id=PYTHON_SHEET_ID,
            name_ru="Новый раздел query plan",
            name_en="Query plan new section",
        ),
    )


async def run_create_matrix_subsection(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).create_subsection(
        params=CompetencyMatrixSubsectionCreateParams(
            section_id=PYTHON_SECTION_ID,
            name_ru="Новый подраздел query plan",
            name_en="Query plan new subsection",
        ),
    )


async def run_update_matrix_sheet_priorities(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).update_sheet_priorities(
        params=CompetencyMatrixSheetPriorityUpdateParams(
            ordered_ids=(POSTGRESQL_SHEET_ID, PYTHON_SHEET_ID, PYDANTIC_SHEET_ID),
        ),
    )


async def run_update_matrix_section_priorities(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).update_section_priorities(
        params=CompetencyMatrixSectionPriorityUpdateParams(
            sheet_id=PYTHON_SHEET_ID,
            ordered_ids=(hex_id(2), PYTHON_SECTION_ID, hex_id(3)),
        ),
    )


async def run_update_matrix_subsection_priorities(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).update_subsection_priorities(
        params=CompetencyMatrixSubsectionPriorityUpdateParams(
            section_id=PYTHON_SECTION_ID,
            ordered_ids=(hex_id(2), PYTHON_SUBSECTION_ID, hex_id(3)),
        ),
    )


async def run_list_competency_matrix_items(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).list_competency_matrix_items(
        filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=True),
    )


async def run_list_competency_matrix_workspace_items(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).list_competency_matrix_workspace_items(
        filters=CompetencyMatrixWorkspaceFilters(
            page=1,
            page_size=20,
            language=LanguageEnum.EN,
            sort=CompetencyMatrixWorkspaceSortEnum.INTERVIEW_FREQUENCY,
            search_query=None,
            sheet_keys=("python",),
            grades=(GradeEnum.JUNIOR,),
            interview_frequencies=(InterviewFrequencyEnum.OFTEN,),
            section_ids=(PYTHON_SECTION_ID,),
            subsection_ids=(PYTHON_SUBSECTION_ID,),
            sections=(),
            subsections=(),
            publish_statuses=(PublishStatusEnum.PUBLISHED,),
            published_from=None,
            published_to=None,
            has_missing_fields=None,
        ),
    )


async def run_list_competency_matrix_workspace_filter_options(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(
        session=session,
    ).list_competency_matrix_workspace_filter_options(language=LanguageEnum.EN)


async def run_get_competency_matrix_item(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).get_competency_matrix_item(
        EXISTING_MATRIX_ITEM_ID,
    )


async def run_get_competency_matrix_item_by_slug(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).get_competency_matrix_item_by_slug(
        "matrix-question-100",
    )


async def run_create_competency_matrix_item(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).create_competency_matrix_item(
        write_matrix_item(item_id=NEW_MATRIX_ITEM_ID, slug="query-plan-new-matrix-item"),
    )


async def run_update_competency_matrix_item(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).update_competency_matrix_item(
        write_matrix_item(item_id=EXISTING_MATRIX_ITEM_ID, slug="matrix-question-100"),
    )


async def run_update_competency_matrix_item_publish_status(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(
        session=session,
    ).update_competency_matrix_item_publish_status(
        EXISTING_MATRIX_ITEM_ID,
        PublishStatusEnum.DRAFT,
    )


async def run_list_queued_questions(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).list_queued_questions()


async def run_list_queued_questions_with_active_claims(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(
        session=session,
    ).list_queued_questions_with_active_claims(active_at=SEED_NOW)


async def run_question_suggestion_exists(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).question_suggestion_exists(
        fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
            question="Queued question 100",
        ),
        sheet_key="sheet-1",
    )


async def run_get_queued_question(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).get_queued_question(
        EXISTING_QUEUED_QUESTION_ID,
        lock=False,
    )


async def run_get_queued_question_with_lock(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).get_queued_question(
        EXISTING_QUEUED_QUESTION_ID,
        lock=True,
    )


async def run_create_queued_question(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).create_queued_question(
        params=QueuedCompetencyMatrixQuestionCreateParams(
            question="How should query-plan checks cover the matrix queue?",
            sheet="query-plan-sheet",
            grade=GradeEnum.JUNIOR,
        ),
        suggested_by_username=SEED_USERNAME,
    )


async def run_create_queued_questions(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).create_queued_questions(
        params=QueuedCompetencyMatrixQuestionsCreateParams(
            questions=[
                QueuedCompetencyMatrixQuestionCreateParams(
                    question="How should query-plan checks cover matrix imports?",
                    sheet="query-plan-sheet",
                    grade=None,
                ),
                QueuedCompetencyMatrixQuestionCreateParams(
                    question="How should FIFO ordering behave for imported questions?",
                    sheet="query-plan-sheet",
                    grade=GradeEnum.MIDDLE,
                ),
            ],
        ),
        suggested_by_username=SEED_USERNAME,
    )


async def run_delete_queued_question(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).delete_queued_question(
        DELETABLE_QUEUED_QUESTION_ID,
    )


async def run_delete_question_claim(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).delete_question_claim(
        DELETABLE_MATRIX_QUESTION_CLAIM_ID,
    )


async def run_agent_client_name_exists(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).client_name_exists(
        normalized_name="query-plan-agent-0",
    )


async def run_create_agent_client(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).create_client(
        client=AgentClient(
            id=hex_id(69_001),
            name="query-plan-new-agent",
            status=AgentClientStatusEnum.ACTIVE,
            scopes=frozenset(AgentScopeEnum),
            created_at=SEED_NOW,
            revoked_at=None,
        ),
    )


async def run_list_agent_clients(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).list_clients()


async def run_create_agent_certificate(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).create_certificate(
        certificate=AgentCertificate(
            id=hex_id(69_002),
            agent_client_id=CLAIMABLE_AGENT_CLIENT_ID,
            fingerprint_sha256="a" * 64,
            serial_number="query-plan-new-certificate",
            certificate_pem="query-plan-new-certificate",
            valid_from=SEED_NOW,
            expires_at=SEED_NOW + timedelta(days=90),
            created_at=SEED_NOW,
            revoked_at=None,
        ),
    )


async def run_list_agent_certificates(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).list_certificates(
        agent_client_id=AGENT_CLIENT_ID,
    )


async def run_revoke_agent_client(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).revoke_client(
        params=AgentClientRevokeParams(
            agent_client_id=REVOKABLE_AGENT_CLIENT_ID,
            revoked_at=SEED_NOW,
        ),
    )


async def run_get_agent_credential(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_credential_by_fingerprint(
        fingerprint_sha256=f"{1:064x}",
    )


async def run_get_agent_client_for_rotation(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_client_for_rotation(
        agent_client_id=AGENT_CLIENT_ID,
    )


async def run_get_agent_certificate_for_rotation(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_certificate_for_rotation(
        certificate_id=AGENT_CERTIFICATE_ID,
        agent_client_id=AGENT_CLIENT_ID,
    )


async def run_get_agent_certificate_by_id(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_certificate_by_id(
        certificate_id=AGENT_CERTIFICATE_ID,
        agent_client_id=AGENT_CLIENT_ID,
    )


async def run_get_agent_certificate_rotation(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_certificate_rotation(
        rotation_id=AGENT_ROTATION_ID,
    )


async def run_get_pending_agent_certificate_rotation(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_pending_certificate_rotation(
        current_certificate_id=AGENT_CERTIFICATE_ID,
    )


async def run_create_agent_certificate_rotation(session: AsyncSession) -> None:
    replacement = AgentCertificate(
        id=hex_id(69_003),
        agent_client_id=CLAIMABLE_AGENT_CLIENT_ID,
        fingerprint_sha256="b" * 64,
        serial_number="query-plan-new-replacement",
        certificate_pem="query-plan-new-replacement",
        valid_from=SEED_NOW,
        expires_at=SEED_NOW + timedelta(days=90),
        created_at=SEED_NOW,
        revoked_at=None,
    )
    await AgentAccessDatabaseStorage(session=session).create_certificate_rotation(
        rotation=AgentCertificateRotation(
            rotation_id="query-plan-new-rotation",
            agent_client_id=CLAIMABLE_AGENT_CLIENT_ID,
            current_certificate_id=CLAIMABLE_AGENT_CERTIFICATE_ID,
            replacement_certificate_id=replacement.id,
            csr_digest="e" * 64,
            created_at=SEED_NOW,
            normal_access_until=SEED_NOW + timedelta(minutes=15),
            confirmed_at=None,
        ),
        replacement=replacement,
    )


async def run_confirm_agent_certificate_rotation(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).confirm_certificate_rotation(
        rotation_id=AGENT_ROTATION_ID,
        current_certificate_id=AGENT_CERTIFICATE_ID,
        confirmed_at=SEED_NOW + timedelta(minutes=1),
    )


async def run_create_agent_audit_event(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).create_audit_event(
        params=AgentAuditEventCreateParams(
            agent_client_id=AGENT_CLIENT_ID,
            certificate_id=AGENT_CERTIFICATE_ID,
            action=AgentActionEnum.GET_MATRIX_AUTHORING_CONTEXT,
            queue_item_id=None,
            matrix_item_id=None,
            request_id="query-plan-new-audit",
            result=AgentAuditResultEnum.SUCCESS,
            input_digest="f" * 64,
            created_at=SEED_NOW,
        ),
    )


async def run_prune_agent_audit_events(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).prune_audit_events(
        created_at_before=SEED_NOW - timedelta(days=180),
    )


async def run_list_agent_audit_events(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).list_audit_events(
        params=AgentAuditEventPageQuery(
            agent_client_id=AGENT_CLIENT_ID,
            limit=51,
            cursor=None,
            created_at_from=SEED_NOW - timedelta(days=365),
        ),
    )


async def run_claim_next_agent_matrix_question(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).claim_next_matrix_question(
        agent_client_id=CLAIMABLE_AGENT_CLIENT_ID,
        claimed_at=SEED_NOW,
        expires_at=SEED_NOW + timedelta(hours=2),
    )


async def run_get_matrix_question_draft_completion(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).get_matrix_question_draft_completion(
        claim_id=AGENT_COMPLETION_ID,
        agent_client_id=AGENT_CLIENT_ID,
    )


async def run_lock_agent_matrix_question_claim(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).lock_matrix_question_claim(
        agent_client_id=AGENT_CLIENT_ID,
        claim_id=hex_id(61_001),
    )


async def run_create_matrix_question_draft_completion(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).create_matrix_question_draft_completion(
        completion=MatrixQuestionDraftCompletion(
            claim_id=hex_id(69_004),
            agent_client_id=CLAIMABLE_AGENT_CLIENT_ID,
            queue_item_id=hex_id(1),
            matrix_item_id=hex_id(69_005),
            input_digest="1" * 64,
            completed_at=SEED_NOW,
        ),
    )


async def run_consume_agent_matrix_question_claim(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).consume_matrix_question_claim(
        agent_client_id=AGENT_CLIENT_ID,
        claim_id=hex_id(61_001),
        queue_item_id=hex_id(100),
    )


async def run_release_agent_matrix_question_claim(session: AsyncSession) -> None:
    await AgentAccessDatabaseStorage(session=session).release_matrix_question_claim(
        agent_client_id=hex_id(60_002),
        claim_id=hex_id(61_002),
        released_at=SEED_NOW + timedelta(minutes=1),
    )


async def run_get_resources_by_ids(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).get_resources_by_ids(
        [PYTHON_RESOURCE_ID, POSTGRESQL_RESOURCE_ID, PYDANTIC_RESOURCE_ID],
    )


async def run_delete_competency_matrix_item(session: AsyncSession) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).delete_competency_matrix_item(
        DELETABLE_MATRIX_ITEM_ID,
    )


async def run_search_resources_exact(session: AsyncSession) -> None:
    await run_search_resources(session=session, search_name="pydantic")


async def run_search_resources_url(session: AsyncSession) -> None:
    await run_search_resources(session=session, search_name="python")


async def run_search_resources_fuzzy(session: AsyncSession) -> None:
    await run_search_resources(session=session, search_name="pydntic")


async def run_search_resources_short(session: AsyncSession) -> None:
    await run_search_resources(session=session, search_name="py")


async def run_search_resources(*, session: AsyncSession, search_name: str) -> None:
    await CompetencyMatrixDatabaseStorage(session=session).search_competency_matrix_resources(
        search_name,
        10,
        LanguageEnum.EN,
    )


def article_id(value: int) -> str:
    return md5(str(value).encode(), usedforsecurity=False).hexdigest()


def write_article() -> Article:
    return Article(
        id=NEW_ARTICLE_ID,
        slug="query-plan-new-article",
        title_ru="Новая статья query plan",
        title_en="New query plan article",
        content_ru="Контент для smoke проверки запросов",
        content_en="Content for query smoke checks",
        folder=existing_article_folder(),
        author_username=SEED_USERNAME,
        published_at=SEED_NOW,
        publish_status=PublishStatusEnum.PUBLISHED,
        metadata=empty_article_metadata(),
        created_at=SEED_NOW,
        updated_at=SEED_NOW,
        content_file_ids=frozenset(),
        tags=Tags(values=[seed_tag(1), seed_tag(2)]),
    )


def write_article_for_existing_article() -> Article:
    return Article(
        id=article_id(99),
        slug="article-99-updated",
        title_ru="Обновленная статья query plan",
        title_en="Updated query plan article",
        content_ru="Обновленный контент для smoke проверки",
        content_en="Updated content for query smoke checks",
        folder=existing_article_folder(),
        author_username=SEED_USERNAME,
        published_at=SEED_NOW,
        publish_status=PublishStatusEnum.PUBLISHED,
        metadata=empty_article_metadata(),
        created_at=SEED_NOW,
        updated_at=SEED_NOW,
        content_file_ids=frozenset({EXISTING_ARTICLE_CONTENT_FILE_ID}),
        tags=Tags(values=[seed_tag(103), seed_tag(97), seed_tag(91)]),
    )


def existing_article_folder() -> ArticleFolder:
    return ArticleFolder(
        id=EXISTING_ARTICLE_FOLDER_ID,
        key="engineering",
        name_ru="Инженерия",
        name_en="Engineering",
        priority=1,
    )


def write_article_folder() -> ArticleFolder:
    return ArticleFolder(
        id=NEW_ARTICLE_FOLDER_ID,
        key="query-plan-folder",
        name_ru="Папка query plan",
        name_en="Query plan folder",
        priority=2,
    )


def empty_article_metadata() -> ArticleMetadata:
    return ArticleMetadata(
        seo_title_ru=None,
        seo_title_en=None,
        seo_description_ru=None,
        seo_description_en=None,
        cover_image_file_id=None,
        cover_image_file=None,
        cover_image_url=None,
        cover_image_alt_ru=None,
        cover_image_alt_en=None,
    )


def seed_tag(tag_index: int) -> Tag:
    names = {
        1: ("Питон", "Python", "python"),
        2: ("PostgreSQL", "PostgreSQL", "postgresql"),
        3: ("Pydantic", "Pydantic", "pydantic"),
    }
    if tag_index in names:
        name_ru, name_en, slug = names[tag_index]
    else:
        name_ru = f"Тег {tag_index}"
        name_en = f"Tag {tag_index}"
        slug = f"tag-{tag_index}"
    return Tag(id=hex_id(tag_index), name_ru=name_ru, name_en=name_en, slug=slug)


def write_matrix_item(*, item_id: str, slug: str) -> CompetencyMatrixItem:
    return CompetencyMatrixItem(
        id=item_id,
        slug=slug,
        question_ru="Как smoke проверяет запросы?",
        question_en="How does the smoke check queries?",
        publish_status=PublishStatusEnum.PUBLISHED,
        published_at=SEED_NOW,
        answer_ru="Через deterministic storage сценарии.",
        answer_en="Through deterministic storage scenarios.",
        interview_answer_explanation_ru="Назвать listener, EXPLAIN и thresholds.",
        interview_answer_explanation_en="Name listener, EXPLAIN, and thresholds.",
        structure=CompetencyMatrixItemStructure(
            sheet_id=PYTHON_SHEET_ID,
            sheet_key="python",
            sheet_ru="Питон",
            sheet_en="Python",
            section_id=PYTHON_SECTION_ID,
            section_ru="Основы",
            section_en="Basics",
            subsection_id=PYTHON_SUBSECTION_ID,
            subsection_ru="Функции",
            subsection_en="Functions",
        ),
        grade=GradeEnum.JUNIOR,
        interview_frequency=InterviewFrequencyEnum.OFTEN,
        suggested_by_username=SEED_USERNAME,
        resources=AttachedExternalResources(
            values=[
                AttachedExternalResource(
                    id=PYTHON_RESOURCE_ID,
                    name_ru="Документация Pydantic",
                    name_en="Pydantic validation guide",
                    url="https://docs.pydantic.dev/latest/",
                    context_ru="Контекст для smoke",
                    context_en="Smoke context",
                ),
            ],
        ),
    )


def scenario(  # noqa: PLR0913
    *,
    name: str,
    storage_class: str,
    method_name: str,
    group: QueryThresholdGroup,
    expected_index_names: Iterable[str],
    forbidden_seq_scan_relations: Iterable[str],
    allow_seq_scan_reason: str | None,
    run: ScenarioRunner,
) -> StorageScenario:
    return StorageScenario(
        name=name,
        storage_class=storage_class,
        method_name=method_name,
        group=group,
        expected_indexes=expected_indexes_from_names(names=expected_index_names),
        forbidden_seq_scan_relations=tuple(forbidden_seq_scan_relations),
        allow_seq_scan_reason=allow_seq_scan_reason,
        run=run,
    )


STORAGE_SCENARIOS = (
    *(
        scenario(
            name=name,
            storage_class="AgentAccessDatabaseStorage",
            method_name=method_name,
            group=group,
            expected_index_names=(),
            forbidden_seq_scan_relations=(),
            allow_seq_scan_reason=None,
            run=runner,
        )
        for name, method_name, group, runner in (
            (
                "agent_client_name_exists",
                "client_name_exists",
                QueryThresholdGroup.POINT_READ,
                run_agent_client_name_exists,
            ),
            (
                "agent_client_create",
                "create_client",
                QueryThresholdGroup.SMALL_WRITE,
                run_create_agent_client,
            ),
            (
                "agent_clients_list",
                "list_clients",
                QueryThresholdGroup.LIST_READ,
                run_list_agent_clients,
            ),
            (
                "agent_certificate_create",
                "create_certificate",
                QueryThresholdGroup.SMALL_WRITE,
                run_create_agent_certificate,
            ),
            (
                "agent_certificates_list",
                "list_certificates",
                QueryThresholdGroup.LIST_READ,
                run_list_agent_certificates,
            ),
            (
                "agent_client_revoke",
                "revoke_client",
                QueryThresholdGroup.SMALL_WRITE,
                run_revoke_agent_client,
            ),
            (
                "agent_credential_by_fingerprint",
                "get_credential_by_fingerprint",
                QueryThresholdGroup.POINT_READ,
                run_get_agent_credential,
            ),
            (
                "agent_rotation_client",
                "get_client_for_rotation",
                QueryThresholdGroup.POINT_READ,
                run_get_agent_client_for_rotation,
            ),
            (
                "agent_rotation_current_certificate",
                "get_certificate_for_rotation",
                QueryThresholdGroup.POINT_READ,
                run_get_agent_certificate_for_rotation,
            ),
            (
                "agent_certificate_by_id",
                "get_certificate_by_id",
                QueryThresholdGroup.POINT_READ,
                run_get_agent_certificate_by_id,
            ),
            (
                "agent_rotation_by_id",
                "get_certificate_rotation",
                QueryThresholdGroup.POINT_READ,
                run_get_agent_certificate_rotation,
            ),
            (
                "agent_pending_rotation",
                "get_pending_certificate_rotation",
                QueryThresholdGroup.POINT_READ,
                run_get_pending_agent_certificate_rotation,
            ),
            (
                "agent_rotation_create",
                "create_certificate_rotation",
                QueryThresholdGroup.SMALL_WRITE,
                run_create_agent_certificate_rotation,
            ),
            (
                "agent_rotation_confirm",
                "confirm_certificate_rotation",
                QueryThresholdGroup.SMALL_WRITE,
                run_confirm_agent_certificate_rotation,
            ),
            (
                "agent_audit_create",
                "create_audit_event",
                QueryThresholdGroup.SMALL_WRITE,
                run_create_agent_audit_event,
            ),
            (
                "agent_audit_prune",
                "prune_audit_events",
                QueryThresholdGroup.SMALL_WRITE,
                run_prune_agent_audit_events,
            ),
            (
                "agent_audit_list",
                "list_audit_events",
                QueryThresholdGroup.LIST_READ,
                run_list_agent_audit_events,
            ),
            (
                "agent_matrix_claim_next",
                "claim_next_matrix_question",
                QueryThresholdGroup.SMALL_WRITE,
                run_claim_next_agent_matrix_question,
            ),
            (
                "agent_matrix_completion_by_claim",
                "get_matrix_question_draft_completion",
                QueryThresholdGroup.POINT_READ,
                run_get_matrix_question_draft_completion,
            ),
            (
                "agent_matrix_claim_lock",
                "lock_matrix_question_claim",
                QueryThresholdGroup.POINT_READ,
                run_lock_agent_matrix_question_claim,
            ),
            (
                "agent_matrix_completion_create",
                "create_matrix_question_draft_completion",
                QueryThresholdGroup.SMALL_WRITE,
                run_create_matrix_question_draft_completion,
            ),
            (
                "agent_matrix_claim_consume",
                "consume_matrix_question_claim",
                QueryThresholdGroup.SMALL_WRITE,
                run_consume_agent_matrix_question_claim,
            ),
            (
                "agent_matrix_claim_release",
                "release_matrix_question_claim",
                QueryThresholdGroup.SMALL_WRITE,
                run_release_agent_matrix_question_claim,
            ),
        )
    ),
    scenario(
        name="user_get_by_username",
        storage_class="UserAccountDatabaseStorage",
        method_name="get_user_by_username",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("users_username_lower_uniq",),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_user_get_by_username,
    ),
    scenario(
        name="managed_accounts_list",
        storage_class="UserAccountDatabaseStorage",
        method_name="list_managed_accounts",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_list_managed_accounts,
    ),
    scenario(
        name="managed_accounts_detail",
        storage_class="UserAccountDatabaseStorage",
        method_name="get_managed_account",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("users_username_lower_uniq",),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_get_managed_account,
    ),
    scenario(
        name="managed_accounts_create",
        storage_class="UserAccountDatabaseStorage",
        method_name="create_managed_account",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_managed_account,
    ),
    scenario(
        name="managed_accounts_update_role",
        storage_class="UserAccountDatabaseStorage",
        method_name="update_managed_account_role",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_update_managed_account_role,
    ),
    scenario(
        name="managed_accounts_update_password",
        storage_class="UserAccountDatabaseStorage",
        method_name="update_managed_account_password",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_update_managed_account_password,
    ),
    scenario(
        name="managed_accounts_activate",
        storage_class="UserAccountDatabaseStorage",
        method_name="activate_managed_account",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_activate_managed_account,
    ),
    scenario(
        name="managed_accounts_deactivate",
        storage_class="UserAccountDatabaseStorage",
        method_name="deactivate_managed_account",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_deactivate_managed_account,
    ),
    scenario(
        name="managed_accounts_delete",
        storage_class="UserAccountDatabaseStorage",
        method_name="delete_managed_account",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_delete_managed_account,
    ),
    scenario(
        name="auth_update_user_password_hash",
        storage_class="AuthDatabaseStorage",
        method_name="update_user_password_hash",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("users_username_lower_uniq",),
        forbidden_seq_scan_relations=("auth__user_model",),
        allow_seq_scan_reason=None,
        run=run_update_user_password_hash,
    ),
    scenario(
        name="auth_session_create",
        storage_class="AuthSessionDatabaseStorage",
        method_name="create_session",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_auth_session,
    ),
    scenario(
        name="auth_session_detail_by_secret_hash",
        storage_class="AuthSessionDatabaseStorage",
        method_name="get_session_by_secret_hash",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("auth_sessions_secret_hash_uniq",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_get_auth_session_by_secret_hash,
    ),
    scenario(
        name="auth_session_detail_by_id",
        storage_class="AuthSessionDatabaseStorage",
        method_name="get_session_by_id",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("auth__auth_session_model_pkey",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_get_auth_session_by_id,
    ),
    scenario(
        name="auth_session_list_user_sessions",
        storage_class="AuthSessionDatabaseStorage",
        method_name="list_user_sessions",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=("auth_sessions_username_lower_active_expiry_idx",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_list_user_auth_sessions,
    ),
    scenario(
        name="auth_session_extend_expiry",
        storage_class="AuthSessionDatabaseStorage",
        method_name="extend_session_expiry",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("auth__auth_session_model_pkey",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_extend_auth_session_expiry,
    ),
    scenario(
        name="auth_session_delete_expired",
        storage_class="AuthSessionDatabaseStorage",
        method_name="delete_expired_sessions",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("auth_sessions_expiry_idx",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_delete_expired_auth_sessions,
    ),
    scenario(
        name="auth_session_count_cleanup",
        storage_class="AuthSessionDatabaseStorage",
        method_name="count_cleanup_sessions",
        group=QueryThresholdGroup.AGGREGATE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_count_cleanup_auth_sessions,
    ),
    scenario(
        name="auth_session_revoke_by_secret_hash",
        storage_class="AuthSessionDatabaseStorage",
        method_name="revoke_session_by_secret_hash",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("auth_sessions_secret_hash_uniq",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_revoke_auth_session_by_secret_hash,
    ),
    scenario(
        name="auth_session_revoke_user_session",
        storage_class="AuthSessionDatabaseStorage",
        method_name="revoke_user_session",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("auth__auth_session_model_pkey",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_revoke_user_auth_session,
    ),
    scenario(
        name="auth_session_revoke_user_sessions",
        storage_class="AuthSessionDatabaseStorage",
        method_name="revoke_user_sessions",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("auth_sessions_username_lower_active_expiry_idx",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_revoke_user_auth_sessions,
    ),
    scenario(
        name="auth_session_revoke_user_sessions_except",
        storage_class="AuthSessionDatabaseStorage",
        method_name="revoke_user_sessions_except",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("auth_sessions_username_lower_active_expiry_idx",),
        forbidden_seq_scan_relations=("auth__auth_session_model",),
        allow_seq_scan_reason=None,
        run=run_revoke_other_user_auth_sessions,
    ),
    scenario(
        name="contact_create_request",
        storage_class="ContactMeDatabaseStorage",
        method_name="create_contact_me_request",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_contact_me_request,
    ),
    scenario(
        name="articles_detail_by_slug",
        storage_class="ArticlesDatabaseStorage",
        method_name="get_article_by_slug",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_get_article_by_slug,
    ),
    scenario(
        name="articles_list_en_full_text_tag_date",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_articles",
        group=QueryThresholdGroup.SEARCH,
        expected_index_names=(),
        forbidden_seq_scan_relations=(
            "articles__article_model",
            "articles__article_to_tag_secondary_model",
        ),
        allow_seq_scan_reason=None,
        run=run_list_articles_en_full_text_tag_date,
    ),
    scenario(
        name="articles_list_ru_full_text",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_articles",
        group=QueryThresholdGroup.SEARCH,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_list_articles_ru_full_text,
    ),
    scenario(
        name="articles_published_for_seo_sitemap",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_articles",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=("articles_article_publish_status_published_updated_idx",),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_list_articles_for_seo,
    ),
    scenario(
        name="articles_tree_published",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_tree_items",
        group=QueryThresholdGroup.HEAVY,
        expected_index_names=("articles_article_tree_folder_en_published_idx",),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_list_tree_items,
    ),
    scenario(
        name="articles_create",
        storage_class="ArticlesDatabaseStorage",
        method_name="create_article",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_create_article,
    ),
    scenario(
        name="articles_update",
        storage_class="ArticlesDatabaseStorage",
        method_name="update_article",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_update_article,
    ),
    scenario(
        name="articles_delete",
        storage_class="ArticlesDatabaseStorage",
        method_name="delete_article",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_delete_article,
    ),
    scenario(
        name="articles_update_publish_status",
        storage_class="ArticlesDatabaseStorage",
        method_name="update_article_publish_status",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_model",),
        allow_seq_scan_reason=None,
        run=run_update_article_publish_status,
    ),
    scenario(
        name="article_folders_detail_by_id",
        storage_class="ArticlesDatabaseStorage",
        method_name="get_folder_by_id",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("articles__article_folder_model_pkey",),
        forbidden_seq_scan_relations=("articles__article_folder_model",),
        allow_seq_scan_reason=None,
        run=run_get_article_folder_by_id,
    ),
    scenario(
        name="article_folders_list",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_folders",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_list_article_folders,
    ),
    scenario(
        name="article_folders_next_priority",
        storage_class="ArticlesDatabaseStorage",
        method_name="next_folder_priority",
        group=QueryThresholdGroup.AGGREGATE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_next_article_folder_priority,
    ),
    scenario(
        name="article_folders_key_exists",
        storage_class="ArticlesDatabaseStorage",
        method_name="folder_key_exists",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("articles_folder_key_lower_uniq",),
        forbidden_seq_scan_relations=("articles__article_folder_model",),
        allow_seq_scan_reason=None,
        run=run_article_folder_key_exists,
    ),
    scenario(
        name="article_folders_create",
        storage_class="ArticlesDatabaseStorage",
        method_name="create_folder",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_article_folder,
    ),
    scenario(
        name="article_folders_update_priorities",
        storage_class="ArticlesDatabaseStorage",
        method_name="update_folder_priorities",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("articles__article_folder_model_pkey",),
        forbidden_seq_scan_relations=("articles__article_folder_model",),
        allow_seq_scan_reason=None,
        run=run_update_article_folder_priorities,
    ),
    scenario(
        name="tags_get_by_ids",
        storage_class="ArticlesDatabaseStorage",
        method_name="get_tags_by_ids",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("articles__tag_model_pkey",),
        forbidden_seq_scan_relations=("articles__tag_model",),
        allow_seq_scan_reason=None,
        run=run_get_tags_by_ids,
    ),
    scenario(
        name="tags_list",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_tags",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason="full tag listing is intentionally sorted for authoring UI",
        run=run_list_tags,
    ),
    scenario(
        name="tags_list_public",
        storage_class="ArticlesDatabaseStorage",
        method_name="list_tags",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=(
            "public tag listing scans the tag dictionary and checks published associations"
        ),
        run=run_list_public_tags,
    ),
    *(
        scenario(
            name=name,
            storage_class="ArticlesDatabaseStorage",
            method_name="search_tags",
            group=QueryThresholdGroup.SEARCH,
            expected_index_names=indexes,
            forbidden_seq_scan_relations=forbidden_relations,
            allow_seq_scan_reason=allow_reason,
            run=runner,
        )
        for name, runner, indexes, forbidden_relations, allow_reason in (
            (
                "tags_exact_en",
                run_search_tags_exact,
                (
                    "articles_tag_name_en_trgm_idx",
                    "articles_tag_name_ru_trgm_idx",
                    "articles_tag_slug_trgm_idx",
                ),
                ("articles__tag_model",),
                None,
            ),
            (
                "tags_substring_en",
                run_search_tags_substring,
                (
                    "articles_tag_name_en_trgm_idx",
                    "articles_tag_name_ru_trgm_idx",
                    "articles_tag_slug_trgm_idx",
                ),
                ("articles__tag_model",),
                None,
            ),
            (
                "tags_fuzzy_en",
                run_search_tags_fuzzy,
                (
                    "articles_tag_name_en_trgm_idx",
                    "articles_tag_name_ru_trgm_idx",
                    "articles_tag_slug_trgm_idx",
                ),
                ("articles__tag_model",),
                None,
            ),
            (
                "tags_short_en",
                run_search_tags_short,
                (),
                (),
                SHORT_TRIGRAM_ALLOW_REASON,
            ),
        )
    ),
    scenario(
        name="tags_create",
        storage_class="ArticlesDatabaseStorage",
        method_name="create_tag",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_tag,
    ),
    scenario(
        name="tags_update",
        storage_class="ArticlesDatabaseStorage",
        method_name="update_tag",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("articles__tag_model_pkey",),
        forbidden_seq_scan_relations=("articles__tag_model",),
        allow_seq_scan_reason=None,
        run=run_update_tag,
    ),
    scenario(
        name="tags_delete",
        storage_class="ArticlesDatabaseStorage",
        method_name="delete_tag",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("articles__tag_model_pkey",),
        forbidden_seq_scan_relations=("articles__tag_model",),
        allow_seq_scan_reason=None,
        run=run_delete_tag,
    ),
    scenario(
        name="article_analytics_increment_view",
        storage_class="ArticleAnalyticsDatabaseStorage",
        method_name="increment_view",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_increment_view,
    ),
    scenario(
        name="article_analytics_increment_engaged_view",
        storage_class="ArticleAnalyticsDatabaseStorage",
        method_name="increment_engaged_view",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_increment_engaged_view,
    ),
    scenario(
        name="article_analytics_public_stats",
        storage_class="ArticleAnalyticsDatabaseStorage",
        method_name="get_public_stats",
        group=QueryThresholdGroup.AGGREGATE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_get_public_stats,
    ),
    scenario(
        name="article_analytics_reaction_counts",
        storage_class="ArticleAnalyticsDatabaseStorage",
        method_name="get_reaction_counts",
        group=QueryThresholdGroup.AGGREGATE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_get_reaction_counts,
    ),
    scenario(
        name="article_analytics_set_reaction",
        storage_class="ArticleAnalyticsDatabaseStorage",
        method_name="set_reaction",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("articles__article_reaction_model",),
        allow_seq_scan_reason=None,
        run=run_set_reaction,
    ),
    scenario(
        name="article_analytics_daily_stats",
        storage_class="ArticleAnalyticsDatabaseStorage",
        method_name="get_daily_stats",
        group=QueryThresholdGroup.AGGREGATE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_get_daily_stats,
    ),
    scenario(
        name="matrix_list_sheets",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_sheets",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_list_sheets,
    ),
    scenario(
        name="matrix_list_structure",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_structure",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_list_matrix_structure,
    ),
    scenario(
        name="matrix_get_item_structure_by_subsection",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="get_item_structure_by_subsection_id",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_subsection_model",),
        allow_seq_scan_reason=None,
        run=run_get_item_structure_by_subsection_id,
    ),
    scenario(
        name="matrix_create_sheet",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="create_sheet",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_matrix_sheet,
    ),
    scenario(
        name="matrix_create_section",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="create_section",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_matrix_section,
    ),
    scenario(
        name="matrix_create_subsection",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="create_subsection",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_matrix_subsection,
    ),
    scenario(
        name="matrix_update_sheet_priorities",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="update_sheet_priorities",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_update_matrix_sheet_priorities,
    ),
    scenario(
        name="matrix_update_section_priorities",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="update_section_priorities",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_update_matrix_section_priorities,
    ),
    scenario(
        name="matrix_update_subsection_priorities",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="update_subsection_priorities",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("competency_matrix__competency_matrix_subsection_model_pkey",),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_update_matrix_subsection_priorities,
    ),
    scenario(
        name="matrix_list_items",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_competency_matrix_items",
        group=QueryThresholdGroup.HEAVY,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=(
            "public sheet matrix listing reads a large published slice and sorts by normalized "
            "structure"
        ),
        run=run_list_competency_matrix_items,
    ),
    scenario(
        name="matrix_workspace_list_items",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_competency_matrix_workspace_items",
        group=QueryThresholdGroup.HEAVY,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_list_competency_matrix_workspace_items,
    ),
    scenario(
        name="matrix_workspace_filter_options",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_competency_matrix_workspace_filter_options",
        group=QueryThresholdGroup.HEAVY,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_list_competency_matrix_workspace_filter_options,
    ),
    scenario(
        name="matrix_detail_by_id",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="get_competency_matrix_item",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_item_model",),
        allow_seq_scan_reason=None,
        run=run_get_competency_matrix_item,
    ),
    scenario(
        name="matrix_public_detail_by_slug",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="get_competency_matrix_item_by_slug",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_item_model",),
        allow_seq_scan_reason=None,
        run=run_get_competency_matrix_item_by_slug,
    ),
    scenario(
        name="matrix_create_item",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="create_competency_matrix_item",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_item_model",),
        allow_seq_scan_reason=None,
        run=run_create_competency_matrix_item,
    ),
    scenario(
        name="matrix_update_item",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="update_competency_matrix_item",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_item_model",),
        allow_seq_scan_reason=None,
        run=run_update_competency_matrix_item,
    ),
    scenario(
        name="matrix_update_publish_status",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="update_competency_matrix_item_publish_status",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_item_model",),
        allow_seq_scan_reason=None,
        run=run_update_competency_matrix_item_publish_status,
    ),
    scenario(
        name="matrix_question_suggestion_exists",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="question_suggestion_exists",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=(
            "cm_queued_question_fingerprint_idx",
            "cmi_question_ru_fingerprint_idx",
            "cmi_question_en_fingerprint_idx",
        ),
        forbidden_seq_scan_relations=(
            "competency_matrix__queued_question_model",
            "competency_matrix__competency_matrix_item_model",
        ),
        allow_seq_scan_reason=None,
        run=run_question_suggestion_exists,
    ),
    scenario(
        name="matrix_queue_list_fifo",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_queued_questions",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=("cm_queued_question_fifo_idx",),
        forbidden_seq_scan_relations=("competency_matrix__queued_question_model",),
        allow_seq_scan_reason=None,
        run=run_list_queued_questions,
    ),
    scenario(
        name="matrix_queue_list_fifo_with_agent_claims",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="list_queued_questions_with_active_claims",
        group=QueryThresholdGroup.LIST_READ,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=(
            "joining the complete queue to the intentionally tiny active-claim set makes a "
            "sequential scan and in-memory sort optimal"
        ),
        run=run_list_queued_questions_with_active_claims,
    ),
    scenario(
        name="matrix_queue_detail_by_id",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="get_queued_question",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("competency_matrix__queued_question_model_pkey",),
        forbidden_seq_scan_relations=("competency_matrix__queued_question_model",),
        allow_seq_scan_reason=None,
        run=run_get_queued_question,
    ),
    scenario(
        name="matrix_queue_detail_for_update",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="get_queued_question",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("competency_matrix__queued_question_model_pkey",),
        forbidden_seq_scan_relations=("competency_matrix__queued_question_model",),
        allow_seq_scan_reason=None,
        run=run_get_queued_question_with_lock,
    ),
    scenario(
        name="matrix_queue_create",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="create_queued_question",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_queued_question,
    ),
    scenario(
        name="matrix_queue_batch_create",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="create_queued_questions",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=None,
        run=run_create_queued_questions,
    ),
    scenario(
        name="matrix_queue_delete",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="delete_queued_question",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=("competency_matrix__queued_question_model_pkey",),
        forbidden_seq_scan_relations=("competency_matrix__queued_question_model",),
        allow_seq_scan_reason=None,
        run=run_delete_queued_question,
    ),
    scenario(
        name="matrix_queue_claim_delete",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="delete_question_claim",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=(),
        allow_seq_scan_reason=(
            "one active claim per registered agent keeps this lease table intentionally small"
        ),
        run=run_delete_question_claim,
    ),
    scenario(
        name="matrix_resources_by_ids",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="get_resources_by_ids",
        group=QueryThresholdGroup.POINT_READ,
        expected_index_names=("competency_matrix__external_resource_model_pkey",),
        forbidden_seq_scan_relations=("competency_matrix__external_resource_model",),
        allow_seq_scan_reason=None,
        run=run_get_resources_by_ids,
    ),
    scenario(
        name="matrix_delete_item",
        storage_class="CompetencyMatrixDatabaseStorage",
        method_name="delete_competency_matrix_item",
        group=QueryThresholdGroup.SMALL_WRITE,
        expected_index_names=(),
        forbidden_seq_scan_relations=("competency_matrix__competency_matrix_item_model",),
        allow_seq_scan_reason=None,
        run=run_delete_competency_matrix_item,
    ),
    *(
        scenario(
            name=name,
            storage_class="CompetencyMatrixDatabaseStorage",
            method_name="search_competency_matrix_resources",
            group=QueryThresholdGroup.SEARCH,
            expected_index_names=indexes,
            forbidden_seq_scan_relations=forbidden_relations,
            allow_seq_scan_reason=allow_reason,
            run=runner,
        )
        for name, runner, indexes, forbidden_relations, allow_reason in (
            (
                "resources_exact_en",
                run_search_resources_exact,
                (
                    "cm_external_resource_name_en_trgm_idx",
                    "cm_external_resource_name_ru_trgm_idx",
                    "cm_external_resource_url_trgm_idx",
                ),
                ("competency_matrix__external_resource_model",),
                None,
            ),
            (
                "resources_url_en",
                run_search_resources_url,
                (
                    "cm_external_resource_name_en_trgm_idx",
                    "cm_external_resource_name_ru_trgm_idx",
                    "cm_external_resource_url_trgm_idx",
                ),
                ("competency_matrix__external_resource_model",),
                None,
            ),
            (
                "resources_fuzzy_en",
                run_search_resources_fuzzy,
                (
                    "cm_external_resource_name_en_trgm_idx",
                    "cm_external_resource_name_ru_trgm_idx",
                    "cm_external_resource_url_trgm_idx",
                ),
                ("competency_matrix__external_resource_model",),
                None,
            ),
            (
                "resources_short_en",
                run_search_resources_short,
                (),
                (),
                SHORT_TRIGRAM_ALLOW_REASON,
            ),
        )
    ),
)
