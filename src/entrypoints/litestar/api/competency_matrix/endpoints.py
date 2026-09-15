from datetime import datetime
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, Request, delete, get, post, put, status_codes
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide

from core.auth.schemas import JwtUser
from core.auth.types import Token
from core.competency_matrix.parsers import QuestionQueueImportParser
from core.competency_matrix.schemas import (
    CompetencyMatrixItemBySlugGetParams,
    CompetencyMatrixItemFilters,
    CompetencyMatrixItemGetParams,
    CompetencyMatrixItemPublishStatusSwitchParams,
    CompetencyMatrixResourceSearchParams,
    CompetencyMatrixWorkspaceFilters,
    QuestionQueueImportFile,
    QuestionSuggestionLimitParams,
)
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.generators import HexUuidIdGenerator
from entrypoints.litestar.api.competency_matrix.dependencies import (
    provide_competency_matrix_item_draft_status_params,
    provide_competency_matrix_item_get_params,
    provide_competency_matrix_item_published_status_params,
    provide_competency_matrix_public_item_get_params,
    provide_competency_matrix_resource_search_params,
    provide_competency_matrix_workspace_filters,
    provide_question_suggestion_limit_params,
    provide_suggested_by_username,
)
from entrypoints.litestar.api.competency_matrix.schemas import (
    CompetencyMatrixFilterOptionsResponseSchema,
    CompetencyMatrixItemDetailResponseSchema,
    CompetencyMatrixItemRequestSchema,
    CompetencyMatrixItemsListResponseSchema,
    CompetencyMatrixResourcesResponseSchema,
    CompetencyMatrixSheetsListResponseSchema,
    CompetencyMatrixWorkspaceResponseSchema,
    MatrixSectionCreateRequestSchema,
    MatrixSheetCreateRequestSchema,
    MatrixStructurePriorityUpdateRequestSchema,
    MatrixStructureResponseSchema,
    MatrixStructureSectionResponseSchema,
    MatrixStructureSheetResponseSchema,
    MatrixStructureSubsectionResponseSchema,
    MatrixSubsectionCreateRequestSchema,
    PublicCompetencyMatrixItemDetailResponseSchema,
    PublicCompetencyMatrixItemsListResponseSchema,
    PublicQuestionSuggestionRequestSchema,
    QuestionSuggestionRequestSchema,
    QueuedQuestionResponseSchema,
    QueuedQuestionsImportConfirmationRequestSchema,
    QueuedQuestionsImportPreviewRequestSchema,
    QueuedQuestionsImportPreviewResponseSchema,
    QueuedQuestionsResponseSchema,
)
from entrypoints.litestar.api.parameters import (
    EntityPkPath,
    LanguageQuery,
    OnlyPublishedQuery,
    SectionIdPath,
    SheetIdPath,
    SheetKeyQuery,
    api_json_body,
    api_multipart_body,
)
from entrypoints.litestar.guards import content_manager_guard
from entrypoints.litestar.response_cache import (
    ResponseCacheDomain,
    invalidate_response_cache_domain_for_mutation,
)
from infra.config.constants import constants
from infra.config.settings import settings
from infra.post_commit_actions import PostCommitActions


class PublicCompetencyMatrixApiController(Controller):
    path = "/competency-matrix"
    tags = ["public competency matrix"]

    @get(
        "/sheets",
        description="Get the public competency matrix sheet list.",
        name="public-competency-matrix-sheets-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.COMPETENCY_MATRIX.cache_key_builder,
    )
    async def list_competency_matrix_sheet(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> CompetencyMatrixSheetsListResponseSchema:
        sheets = await use_case.list_sheets()
        return CompetencyMatrixSheetsListResponseSchema.from_domain_schema(
            schema=sheets,
            language=language,
        )

    @get(
        "/items",
        description="Get the public competency matrix question list.",
        name="public-competency-matrix-items-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.COMPETENCY_MATRIX.cache_key_builder,
    )
    async def list_competency_matrix_items(
        self,
        sheet_key: SheetKeyQuery,
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> PublicCompetencyMatrixItemsListResponseSchema:
        filters = CompetencyMatrixItemFilters(sheet_key=sheet_key, only_published=True)
        items = await use_case.list_items(filters=filters)
        return PublicCompetencyMatrixItemsListResponseSchema.from_domain_schema(
            sheet_key=sheet_key,
            schema=items,
            language=language,
        )

    @get(
        "/items/public/{slug:str}",
        description="Get public competency matrix question details by slug.",
        name="public-competency-matrix-public-item-detail-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.COMPETENCY_MATRIX.cache_key_builder,
        dependencies={
            "params": Provide(
                provide_competency_matrix_public_item_get_params,
                sync_to_thread=False,
            ),
        },
    )
    async def get_public_competency_matrix_item(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        params: NamedDependency[CompetencyMatrixItemBySlugGetParams],
        language: LanguageQuery,
    ) -> PublicCompetencyMatrixItemDetailResponseSchema:
        item = await use_case.get_item_by_slug(params=params)
        return PublicCompetencyMatrixItemDetailResponseSchema.from_domain_schema(
            schema=item,
            language=language,
        )

    @post(
        "/question-suggestions",
        description="Suggest a competency matrix question.",
        name="public-competency-matrix-question-suggestion-create-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
        dependencies={
            "limit": Provide(
                provide_question_suggestion_limit_params,
                sync_to_thread=False,
            ),
            "suggested_by_username": Provide(
                provide_suggested_by_username,
                sync_to_thread=False,
            ),
        },
    )
    async def suggest_competency_matrix_question(
        self,
        data: Annotated[
            PublicQuestionSuggestionRequestSchema,
            api_json_body(
                title="Question suggestion request",
                description="Competency matrix question suggestion.",
                examples=(
                    {"question": "How does asyncio.gather handle errors?", "sheet": "python"},
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        limit: NamedDependency[QuestionSuggestionLimitParams],
        suggested_by_username: NamedDependency[str],
    ) -> None:
        await use_case.suggest_question(
            params=data.to_schema(
                limit=limit,
                suggested_by_username=suggested_by_username,
                reject_duplicates=True,
                validate_public_sheet=True,
            ),
        )


class AdminCompetencyMatrixApiController(Controller):
    path = "/competency-matrix"
    tags = ["admin competency matrix"]
    guards = [content_manager_guard]

    @get(
        "/sheets",
        description="Get the admin competency matrix sheet list.",
        name="admin-competency-matrix-sheets-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_competency_matrix_sheet(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> CompetencyMatrixSheetsListResponseSchema:
        sheets = await use_case.list_sheets()
        return CompetencyMatrixSheetsListResponseSchema.from_domain_schema(
            schema=sheets,
            language=language,
        )

    @get(
        "/structure",
        description="Get the admin competency matrix structure tree.",
        name="admin-competency-matrix-structure-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_competency_matrix_structure(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> MatrixStructureResponseSchema:
        structure = await use_case.list_structure()
        return MatrixStructureResponseSchema.from_domain_schema(
            schema=structure,
            language=language,
        )

    @post(
        "/sheets",
        description="Create a competency matrix sheet.",
        name="admin-competency-matrix-sheet-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_competency_matrix_sheet(
        self,
        data: Annotated[
            MatrixSheetCreateRequestSchema,
            api_json_body(
                title="Competency matrix sheet request",
                description="Language-neutral sheet key plus localized names.",
                examples=(
                    {
                        "key": "python",
                        "translations": {
                            "ru": {"name": "Python"},
                            "en": {"name": "Python"},
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> MatrixStructureSheetResponseSchema:
        sheet = await use_case.create_sheet(params=data.to_schema())
        return MatrixStructureSheetResponseSchema.from_domain_schema(
            schema=sheet,
            language=language,
        )

    @post(
        "/sheets/{sheet_id:str}/sections",
        description="Create a competency matrix section.",
        name="admin-competency-matrix-section-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_competency_matrix_section(
        self,
        sheet_id: SheetIdPath,
        data: Annotated[
            MatrixSectionCreateRequestSchema,
            api_json_body(
                title="Competency matrix section request",
                description="Localized section names for one sheet.",
                examples=(
                    {
                        "translations": {
                            "ru": {"name": "Асинхронность"},
                            "en": {"name": "Async"},
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> MatrixStructureSectionResponseSchema:
        section = await use_case.create_section(
            params=data.to_schema(sheet_id=sheet_id),
        )
        return MatrixStructureSectionResponseSchema.from_domain_schema(
            schema=section,
            language=language,
        )

    @post(
        "/sections/{section_id:str}/subsections",
        description="Create a competency matrix subsection.",
        name="admin-competency-matrix-subsection-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_competency_matrix_subsection(
        self,
        section_id: SectionIdPath,
        data: Annotated[
            MatrixSubsectionCreateRequestSchema,
            api_json_body(
                title="Competency matrix subsection request",
                description="Localized subsection names for one section.",
                examples=(
                    {
                        "translations": {
                            "ru": {"name": "Event loop"},
                            "en": {"name": "Event loop"},
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> MatrixStructureSubsectionResponseSchema:
        subsection = await use_case.create_subsection(
            params=data.to_schema(section_id=section_id),
        )
        return MatrixStructureSubsectionResponseSchema.from_domain_schema(
            schema=subsection,
            language=language,
        )

    @put(
        "/sheets/priorities",
        description="Update competency matrix sheet priority order.",
        name="admin-competency-matrix-sheet-priorities-update-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def update_competency_matrix_sheet_priorities(
        self,
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            MatrixStructurePriorityUpdateRequestSchema,
            api_json_body(
                title="Competency matrix priority request",
                description="Full ordered list of structure identifiers.",
                examples=({"orderedIds": ["00000000000000000000000000000001"]},),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.update_sheet_priorities(params=data.to_sheet_schema())
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )

    @put(
        "/sheets/{sheet_id:str}/sections/priorities",
        description="Update competency matrix section priority order for one sheet.",
        name="admin-competency-matrix-section-priorities-update-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def update_competency_matrix_section_priorities(
        self,
        sheet_id: SheetIdPath,
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            MatrixStructurePriorityUpdateRequestSchema,
            api_json_body(
                title="Competency matrix priority request",
                description="Full ordered list of structure identifiers.",
                examples=({"orderedIds": ["00000000000000000000000000000002"]},),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.update_section_priorities(
            params=data.to_section_schema(sheet_id=sheet_id),
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )

    @put(
        "/sections/{section_id:str}/subsections/priorities",
        description="Update competency matrix subsection priority order for one section.",
        name="admin-competency-matrix-subsection-priorities-update-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def update_competency_matrix_subsection_priorities(
        self,
        section_id: SectionIdPath,
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            MatrixStructurePriorityUpdateRequestSchema,
            api_json_body(
                title="Competency matrix priority request",
                description="Full ordered list of structure identifiers.",
                examples=({"orderedIds": ["00000000000000000000000000000003"]},),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.update_subsection_priorities(
            params=data.to_subsection_schema(section_id=section_id),
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )

    @get(
        "/resources/search",
        description="Search admin competency matrix resources by name and URL.",
        name="admin-competency-matrix-resources-search-api-handler",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "params": Provide(
                provide_competency_matrix_resource_search_params,
                sync_to_thread=False,
            ),
        },
    )
    async def search_competency_matrix_resources(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        params: NamedDependency[CompetencyMatrixResourceSearchParams],
    ) -> CompetencyMatrixResourcesResponseSchema:
        items = await use_case.find_resources(params=params)
        return CompetencyMatrixResourcesResponseSchema.from_domain_schema(
            schema=items,
            language=params.language,
        )

    @get(
        "/queued-questions",
        description="Get the queued competency matrix question list.",
        name="admin-competency-matrix-queued-questions-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_queued_competency_matrix_questions(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        current_datetime: FromDishka[datetime],
    ) -> QueuedQuestionsResponseSchema:
        questions = await use_case.list_queued_questions(current_datetime=current_datetime)
        return QueuedQuestionsResponseSchema.from_domain_schema(schema=questions)

    @post(
        "/queued-questions",
        description="Manually add a competency matrix question to the queue.",
        name="admin-competency-matrix-queued-question-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
        dependencies={
            "suggested_by_username": Provide(
                provide_suggested_by_username,
                sync_to_thread=False,
            ),
        },
    )
    async def create_queued_competency_matrix_question(
        self,
        data: Annotated[
            QuestionSuggestionRequestSchema,
            api_json_body(
                title="Queued question request",
                description="Manual competency matrix question queue payload.",
                examples=(
                    {"question": "How does asyncio.gather handle errors?", "sheet": "python"},
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        suggested_by_username: NamedDependency[str],
    ) -> QueuedQuestionResponseSchema:
        question = await use_case.suggest_question(
            params=data.to_schema(
                limit=None,
                suggested_by_username=suggested_by_username,
                reject_duplicates=False,
                validate_public_sheet=False,
            ),
        )
        return QueuedQuestionResponseSchema.from_domain_schema(schema=question)

    @post(
        "/queued-questions/import/preview",
        description="Preview queued competency matrix questions from a file.",
        name="admin-competency-matrix-queued-questions-import-preview-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def preview_queued_competency_matrix_questions_import(
        self,
        data: Annotated[
            QueuedQuestionsImportPreviewRequestSchema,
            api_multipart_body(
                title="Queued question import preview request",
                description="Multipart file upload for queued question import preview.",
                examples=({"file": "questions.xlsx"},),
            ),
        ],
        parser: FromDishka[QuestionQueueImportParser],
        use_case: FromDishka[CompetencyMatrixUseCase],
    ) -> QueuedQuestionsImportPreviewResponseSchema:
        parsed_preview = parser.preview(
            file=QuestionQueueImportFile(
                filename=data.file.filename,
                content=await data.file.read(),
            ),
        )
        preview = await use_case.preview_queued_questions_import(preview=parsed_preview)
        return QueuedQuestionsImportPreviewResponseSchema.from_domain_schema(schema=preview)

    @post(
        "/queued-questions/import",
        description="Import confirmed queued competency matrix questions from a file.",
        name="admin-competency-matrix-queued-questions-import-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
        dependencies={
            "suggested_by_username": Provide(
                provide_suggested_by_username,
                sync_to_thread=False,
            ),
        },
    )
    async def import_queued_competency_matrix_questions(
        self,
        data: Annotated[
            QueuedQuestionsImportConfirmationRequestSchema,
            api_multipart_body(
                title="Queued question import request",
                description="Multipart file upload with selected queued question rows.",
                examples=({"file": "questions.xlsx", "selectedRowNumbers": [2, 3]},),
            ),
        ],
        parser: FromDishka[QuestionQueueImportParser],
        use_case: FromDishka[CompetencyMatrixUseCase],
        suggested_by_username: NamedDependency[str],
    ) -> QueuedQuestionsResponseSchema:
        params = parser.parse_selected(
            file=QuestionQueueImportFile(
                filename=data.file.filename,
                content=await data.file.read(),
            ),
            selected_row_numbers=data.selected_row_numbers,
        )
        questions = await use_case.import_queued_questions(
            params=params,
            suggested_by_username=suggested_by_username,
        )
        return QueuedQuestionsResponseSchema.from_domain_schema(schema=questions)

    @delete(
        "/queued-questions/{pk:str}",
        description="Reject a queued competency matrix question.",
        name="admin-competency-matrix-queued-question-delete-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def delete_queued_competency_matrix_question(
        self,
        pk: EntityPkPath,
        use_case: FromDishka[CompetencyMatrixUseCase],
        current_datetime: FromDishka[datetime],
    ) -> None:
        await use_case.delete_queued_question(
            question_id=pk,
            current_datetime=current_datetime,
        )

    @post(
        "/queued-questions/{pk:str}/release-agent-claim",
        description="Explicitly release an agent claim on a queued matrix question.",
        name="admin-competency-matrix-queued-question-release-agent-claim-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def release_queued_competency_matrix_question_agent_claim(
        self,
        pk: EntityPkPath,
        use_case: FromDishka[CompetencyMatrixUseCase],
    ) -> None:
        await use_case.release_queued_question_agent_claim(question_id=pk)

    @post(
        "/queued-questions/{pk:str}/create-item",
        description="Create a competency matrix question from the queue.",
        name="admin-competency-matrix-queued-question-create-item-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_competency_matrix_item_from_queue(  # noqa: PLR0913
        self,
        pk: EntityPkPath,
        id_generator: FromDishka[HexUuidIdGenerator],
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            CompetencyMatrixItemRequestSchema,
            api_json_body(
                title="Competency matrix question request",
                description=(
                    "Competency matrix question payload with structure, translations and resources."
                ),
                examples=(
                    {
                        "slug": "python-asyncio-gather-errors",
                        "subsectionId": "00000000000000000000000000000001",
                        "grade": "Middle",
                        "interviewFrequency": "often",
                        "publishStatus": "Draft",
                        "translations": {
                            "ru": {
                                "question": "Как asyncio.gather обрабатывает ошибки?",
                                "answer": "Ответ",
                                "interviewAnswerExplanation": "Объяснение ответа",
                            },
                            "en": {
                                "question": "How does asyncio.gather handle errors?",
                                "answer": "Answer",
                                "interviewAnswerExplanation": "Answer explanation",
                            },
                        },
                        "resources": [],
                    },
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
        current_datetime: FromDishka[datetime],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> CompetencyMatrixItemDetailResponseSchema:
        item = await use_case.create_item_from_queue(
            params=data.to_create_from_queue_schema(
                queued_question_id=pk,
                item_id_generator=id_generator,
                resource_id_generator=id_generator,
            ),
            current_datetime=current_datetime,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )
        return CompetencyMatrixItemDetailResponseSchema.from_domain_schema(
            schema=item,
            language=language,
        )

    @get(
        "/items/workspace",
        description="Get the admin competency matrix question workspace list.",
        name="admin-competency-matrix-items-workspace-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "filters": Provide(
                provide_competency_matrix_workspace_filters,
                sync_to_thread=False,
            ),
        },
    )
    async def list_competency_matrix_workspace_items(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        filters: NamedDependency[CompetencyMatrixWorkspaceFilters],
    ) -> CompetencyMatrixWorkspaceResponseSchema:
        workspace = await use_case.list_workspace_items(filters=filters)
        return CompetencyMatrixWorkspaceResponseSchema.from_domain_schema(schema=workspace)

    @get(
        "/items/filter-options",
        description="Get competency matrix workspace filter values.",
        name="admin-competency-matrix-items-filter-options-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_competency_matrix_workspace_filter_options(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
    ) -> CompetencyMatrixFilterOptionsResponseSchema:
        options = await use_case.list_workspace_filter_options(language=language)
        return CompetencyMatrixFilterOptionsResponseSchema.from_domain_schema(schema=options)

    @get(
        "/items",
        description="Get the admin competency matrix question list.",
        name="admin-competency-matrix-items-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_competency_matrix_items(
        self,
        sheet_key: SheetKeyQuery,
        use_case: FromDishka[CompetencyMatrixUseCase],
        only_published: OnlyPublishedQuery,
        language: LanguageQuery,
    ) -> CompetencyMatrixItemsListResponseSchema:
        filters = CompetencyMatrixItemFilters(
            sheet_key=sheet_key,
            only_published=only_published,
        )
        items = await use_case.list_items(filters=filters)
        return CompetencyMatrixItemsListResponseSchema.from_domain_schema(
            sheet_key=sheet_key,
            schema=items,
            language=language,
        )

    @post(
        "/items",
        description="Create a competency matrix question.",
        name="admin-competency-matrix-item-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
        dependencies={
            "suggested_by_username": Provide(
                provide_suggested_by_username,
                sync_to_thread=False,
            ),
        },
    )
    async def create_competency_matrix_item(  # noqa: PLR0913
        self,
        id_generator: FromDishka[HexUuidIdGenerator],
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            CompetencyMatrixItemRequestSchema,
            api_json_body(
                title="Competency matrix question request",
                description=(
                    "Competency matrix question payload with structure, translations and resources."
                ),
                examples=(
                    {
                        "slug": "python-asyncio-gather-errors",
                        "subsectionId": "00000000000000000000000000000001",
                        "grade": "Middle",
                        "interviewFrequency": "often",
                        "publishStatus": "Draft",
                        "translations": {
                            "ru": {
                                "question": "Как asyncio.gather обрабатывает ошибки?",
                                "answer": "Ответ",
                                "interviewAnswerExplanation": "Объяснение ответа",
                            },
                            "en": {
                                "question": "How does asyncio.gather handle errors?",
                                "answer": "Answer",
                                "interviewAnswerExplanation": "Answer explanation",
                            },
                        },
                        "resources": [],
                    },
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
        suggested_by_username: NamedDependency[str],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> CompetencyMatrixItemDetailResponseSchema:
        item = await use_case.create_item(
            params=data.to_create_schema(
                item_id_generator=id_generator,
                resource_id_generator=id_generator,
            ),
            suggested_by_username=suggested_by_username,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )
        return CompetencyMatrixItemDetailResponseSchema.from_domain_schema(
            schema=item,
            language=language,
        )

    @get(
        "/items/detail/{pk:str}",
        description="Get admin competency matrix question details.",
        name="admin-competency-matrix-item-detail-api-handler",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "params": Provide(
                provide_competency_matrix_item_get_params,
                sync_to_thread=False,
            ),
        },
    )
    async def get_competency_matrix_item(
        self,
        use_case: FromDishka[CompetencyMatrixUseCase],
        params: NamedDependency[CompetencyMatrixItemGetParams],
        language: LanguageQuery,
    ) -> CompetencyMatrixItemDetailResponseSchema:
        item = await use_case.get_item(params=params)
        return CompetencyMatrixItemDetailResponseSchema.from_domain_schema(
            schema=item,
            language=language,
        )

    @put(
        "/items/detail/{pk:str}",
        description="Update a competency matrix question.",
        name="admin-competency-matrix-item-update-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def update_competency_matrix_item(  # noqa: PLR0913
        self,
        pk: EntityPkPath,
        id_generator: FromDishka[HexUuidIdGenerator],
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            CompetencyMatrixItemRequestSchema,
            api_json_body(
                title="Competency matrix question request",
                description=(
                    "Competency matrix question payload with structure, translations and resources."
                ),
                examples=(
                    {
                        "slug": "python-asyncio-gather-errors",
                        "subsectionId": "00000000000000000000000000000001",
                        "grade": "Middle",
                        "interviewFrequency": "often",
                        "publishStatus": "Draft",
                        "translations": {
                            "ru": {
                                "question": "Как asyncio.gather обрабатывает ошибки?",
                                "answer": "Ответ",
                                "interviewAnswerExplanation": "Объяснение ответа",
                            },
                            "en": {
                                "question": "How does asyncio.gather handle errors?",
                                "answer": "Answer",
                                "interviewAnswerExplanation": "Answer explanation",
                            },
                        },
                        "resources": [],
                    },
                ),
            ),
        ],
        use_case: FromDishka[CompetencyMatrixUseCase],
        language: LanguageQuery,
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> CompetencyMatrixItemDetailResponseSchema:
        item = await use_case.update_item(
            params=data.to_update_schema(
                item_id=pk,
                resource_id_generator=id_generator,
            ),
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )
        return CompetencyMatrixItemDetailResponseSchema.from_domain_schema(
            schema=item,
            language=language,
        )

    @delete(
        "/items/detail/{pk:str}",
        description="Delete a competency matrix question.",
        name="admin-competency-matrix-item-delete-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def delete_competency_matrix_item(
        self,
        pk: EntityPkPath,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[CompetencyMatrixUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.delete_item(item_id=pk)
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )

    @post(
        "/items/detail/{pk:str}/set-draft",
        description='Set competency matrix question status to "Draft".',
        name="admin-competency-matrix-item-set-draft-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
        dependencies={
            "params": Provide(
                provide_competency_matrix_item_draft_status_params,
                sync_to_thread=False,
            ),
        },
    )
    async def set_draft_status_to_competency_matrix_item(
        self,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[CompetencyMatrixUseCase],
        params: NamedDependency[CompetencyMatrixItemPublishStatusSwitchParams],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.switch_item_publish_status(params=params)
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )

    @post(
        "/items/detail/{pk:str}/set-published",
        description='Set competency matrix question status to "Published".',
        name="admin-competency-matrix-item-set-published-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
        dependencies={
            "params": Provide(
                provide_competency_matrix_item_published_status_params,
                sync_to_thread=False,
            ),
        },
    )
    async def set_published_status_to_competency_matrix_item(
        self,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[CompetencyMatrixUseCase],
        params: NamedDependency[CompetencyMatrixItemPublishStatusSwitchParams],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.switch_item_publish_status(params=params)
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            post_commit_actions=post_commit_actions,
        )


api_router = DishkaRouter("", route_handlers=[PublicCompetencyMatrixApiController])
admin_router = DishkaRouter("", route_handlers=[AdminCompetencyMatrixApiController])
