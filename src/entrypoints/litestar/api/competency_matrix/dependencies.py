from datetime import UTC, datetime

from litestar import Request
from litestar.datastructures import State

from core.auth.schemas import JwtUser
from core.auth.types import Token
from core.competency_matrix.schemas import (
    CompetencyMatrixItemBySlugGetParams,
    CompetencyMatrixItemGetParams,
    CompetencyMatrixItemPublishStatusSwitchParams,
    CompetencyMatrixResourceSearchParams,
    CompetencyMatrixWorkspaceFilters,
    QuestionSuggestionLimitParams,
)
from core.enums import PublishStatusEnum
from core.types import SearchName
from entrypoints.litestar.api.parameters import (
    EntityPkPath,
    HasMissingFieldsQuery,
    LanguageQuery,
    MatrixGradesQuery,
    MatrixInterviewFrequenciesQuery,
    MatrixItemSlugPath,
    MatrixSectionIdsQuery,
    MatrixSectionsQuery,
    MatrixSheetKeysQuery,
    MatrixSubsectionIdsQuery,
    MatrixSubsectionsQuery,
    MatrixWorkspaceSortQuery,
    OnlyPublishedQuery,
    PageQuery,
    PageSizeQuery,
    PublishedFromQuery,
    PublishedToQuery,
    PublishStatusesQuery,
    SearchLimitQuery,
    SearchNameQuery,
    SearchQueryFilter,
)


def provide_competency_matrix_resource_search_params(
    search_name: SearchNameQuery,
    limit: SearchLimitQuery,
    language: LanguageQuery,
) -> CompetencyMatrixResourceSearchParams:
    return CompetencyMatrixResourceSearchParams(
        search_name=SearchName(search_name),
        limit=limit,
        language=language,
    )


def provide_competency_matrix_item_get_params(
    pk: EntityPkPath,
    only_published: OnlyPublishedQuery,
) -> CompetencyMatrixItemGetParams:
    return CompetencyMatrixItemGetParams(
        item_id=pk,
        only_published=only_published,
    )


def provide_competency_matrix_public_item_get_params(
    slug: MatrixItemSlugPath,
) -> CompetencyMatrixItemBySlugGetParams:
    return CompetencyMatrixItemBySlugGetParams(
        slug=slug,
        only_published=True,
    )


def provide_competency_matrix_item_draft_status_params(
    pk: EntityPkPath,
) -> CompetencyMatrixItemPublishStatusSwitchParams:
    return CompetencyMatrixItemPublishStatusSwitchParams(
        item_id=pk,
        publish_status=PublishStatusEnum.DRAFT,
    )


def provide_competency_matrix_item_published_status_params(
    pk: EntityPkPath,
) -> CompetencyMatrixItemPublishStatusSwitchParams:
    return CompetencyMatrixItemPublishStatusSwitchParams(
        item_id=pk,
        publish_status=PublishStatusEnum.PUBLISHED,
    )


def provide_competency_matrix_workspace_filters(  # noqa: PLR0913
    page: PageQuery,
    page_size: PageSizeQuery,
    language: LanguageQuery,
    sort: MatrixWorkspaceSortQuery,
    search_query: SearchQueryFilter = None,
    sheet_keys: MatrixSheetKeysQuery = None,
    grades: MatrixGradesQuery = None,
    interview_frequencies: MatrixInterviewFrequenciesQuery = None,
    section_ids: MatrixSectionIdsQuery = None,
    subsection_ids: MatrixSubsectionIdsQuery = None,
    sections: MatrixSectionsQuery = None,
    subsections: MatrixSubsectionsQuery = None,
    publish_statuses: PublishStatusesQuery = None,
    published_from: PublishedFromQuery = None,
    published_to: PublishedToQuery = None,
    has_missing_fields: HasMissingFieldsQuery = None,
) -> CompetencyMatrixWorkspaceFilters:
    normalized_search_query = (
        search_query.strip() if search_query is not None and search_query.strip() else None
    )
    return CompetencyMatrixWorkspaceFilters(
        page=page,
        page_size=page_size,
        language=language,
        sort=sort,
        search_query=normalized_search_query,
        sheet_keys=tuple(sheet_keys or ()),
        grades=tuple(grades or ()),
        interview_frequencies=tuple(interview_frequencies or ()),
        section_ids=tuple(section_ids or ()),
        subsection_ids=tuple(subsection_ids or ()),
        sections=tuple(sections or ()),
        subsections=tuple(subsections or ()),
        publish_statuses=tuple(publish_statuses or ()),
        published_from=published_from,
        published_to=published_to,
        has_missing_fields=has_missing_fields,
    )


def provide_question_suggestion_limit_params(
    request: Request[JwtUser, Token | None, State],
) -> QuestionSuggestionLimitParams:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for is not None:
        forwarded_client = forwarded_for.split(",", maxsplit=1)[0].strip()
        if forwarded_client:
            return QuestionSuggestionLimitParams(
                client_identifier=forwarded_client,
                now=datetime.now(tz=UTC),
            )
    real_ip = request.headers.get("x-real-ip")
    if real_ip is not None:
        real_client = real_ip.strip()
        if real_client:
            return QuestionSuggestionLimitParams(
                client_identifier=real_client,
                now=datetime.now(tz=UTC),
            )
    return QuestionSuggestionLimitParams(
        client_identifier=request.client.host if request.client is not None else "",
        now=datetime.now(tz=UTC),
    )


def provide_suggested_by_username(
    request: Request[JwtUser, Token | None, State],
) -> str:
    return request.user.role.value if request.user.is_anon else request.user.username
