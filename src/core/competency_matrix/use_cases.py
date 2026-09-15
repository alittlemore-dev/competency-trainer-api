from dataclasses import dataclass
from datetime import datetime

from core.competency_matrix.exceptions import (
    CompetencyMatrixItemNotFoundError,
    MatrixQuestionClaimConflictError,
    QuestionSuggestionAlreadyExistsError,
    QuestionSuggestionSheetUnavailableError,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixFilterOptions,
    CompetencyMatrixItem,
    CompetencyMatrixItemBySlugGetParams,
    CompetencyMatrixItemCreateParams,
    CompetencyMatrixItemFilters,
    CompetencyMatrixItemGetParams,
    CompetencyMatrixItemPublishStatusSwitchParams,
    CompetencyMatrixItems,
    CompetencyMatrixItemUpdateParams,
    CompetencyMatrixQuestionFingerprint,
    CompetencyMatrixResourceSearchParams,
    CompetencyMatrixSectionCreateParams,
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetCreateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixStructure,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    CompetencyMatrixSubsectionCreateParams,
    CompetencyMatrixSubsectionPriorityUpdateParams,
    CompetencyMatrixWorkspace,
    CompetencyMatrixWorkspaceFilters,
    ExternalResources,
    PublishedCompetencyMatrixItemsForSeo,
    QuestionQueueImportPreview,
    QuestionSuggestionCreateParams,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateItemParams,
    QueuedCompetencyMatrixQuestions,
    QueuedCompetencyMatrixQuestionsCreateParams,
    Sheets,
)
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum


@dataclass(kw_only=True, slots=True, frozen=True)
class CompetencyMatrixUseCase:
    storage: CompetencyMatrixStorage
    question_suggestion_limiter: QuestionSuggestionLimiter

    async def list_sheets(self) -> Sheets:
        return await self.storage.list_sheets()

    async def list_structure(self) -> CompetencyMatrixStructure:
        return await self.storage.list_structure()

    async def create_sheet(
        self,
        *,
        params: CompetencyMatrixSheetCreateParams,
    ) -> CompetencyMatrixStructureSheet:
        return await self.storage.create_sheet(params=params)

    async def create_section(
        self,
        *,
        params: CompetencyMatrixSectionCreateParams,
    ) -> CompetencyMatrixStructureSection:
        return await self.storage.create_section(params=params)

    async def create_subsection(
        self,
        *,
        params: CompetencyMatrixSubsectionCreateParams,
    ) -> CompetencyMatrixStructureSubsection:
        return await self.storage.create_subsection(params=params)

    async def update_sheet_priorities(
        self,
        *,
        params: CompetencyMatrixSheetPriorityUpdateParams,
    ) -> None:
        structure = await self.storage.list_structure()
        structure.ensure_sheet_priority_order_matches(ordered_ids=params.ordered_ids)
        await self.storage.update_sheet_priorities(params=params)

    async def update_section_priorities(
        self,
        *,
        params: CompetencyMatrixSectionPriorityUpdateParams,
    ) -> None:
        structure = await self.storage.list_structure()
        sheet = structure.require_sheet(sheet_id=params.sheet_id)
        sheet.ensure_section_priority_order_matches(ordered_ids=params.ordered_ids)
        await self.storage.update_section_priorities(params=params)

    async def update_subsection_priorities(
        self,
        *,
        params: CompetencyMatrixSubsectionPriorityUpdateParams,
    ) -> None:
        structure = await self.storage.list_structure()
        section = structure.require_section(section_id=params.section_id)
        section.ensure_subsection_priority_order_matches(ordered_ids=params.ordered_ids)
        await self.storage.update_subsection_priorities(params=params)

    async def find_resources(
        self,
        *,
        params: CompetencyMatrixResourceSearchParams,
    ) -> ExternalResources:
        return await self.storage.search_competency_matrix_resources(
            search_name=params.search_name.cleaned,
            limit=params.limit,
            language=params.language,
        )

    async def list_items(
        self,
        *,
        filters: CompetencyMatrixItemFilters,
    ) -> CompetencyMatrixItems:
        items = await self.storage.list_competency_matrix_items(filters=filters)
        matrix = CompetencyMatrixItems(values=items)
        return matrix.only_available() if filters.only_published is True else matrix

    async def get_item(
        self,
        *,
        params: CompetencyMatrixItemGetParams,
    ) -> CompetencyMatrixItem:
        item = await self.storage.get_competency_matrix_item(item_id=params.item_id)
        if params.only_published and not item.is_available():
            raise CompetencyMatrixItemNotFoundError
        return item

    async def get_item_by_slug(
        self,
        *,
        params: CompetencyMatrixItemBySlugGetParams,
    ) -> CompetencyMatrixItem:
        item = await self.storage.get_competency_matrix_item_by_slug(slug=params.slug)
        if params.only_published and not item.is_available():
            raise CompetencyMatrixItemNotFoundError
        return item

    async def list_published_items_for_seo(self) -> PublishedCompetencyMatrixItemsForSeo:
        items = await self.storage.list_competency_matrix_items(
            filters=CompetencyMatrixItemFilters(only_published=True),
        )
        return CompetencyMatrixItems(values=items).only_available().to_published_for_seo()

    async def list_workspace_items(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> CompetencyMatrixWorkspace:
        items, total_count, summary = await self.storage.list_competency_matrix_workspace_items(
            filters=filters,
        )
        return CompetencyMatrixWorkspace.from_page(
            values=items,
            total_count=total_count,
            page_size=filters.page_size,
            summary=summary,
        )

    async def list_workspace_filter_options(
        self,
        *,
        language: LanguageEnum,
    ) -> CompetencyMatrixFilterOptions:
        return await self.storage.list_competency_matrix_workspace_filter_options(
            language=language,
        )

    async def create_item(
        self,
        *,
        params: CompetencyMatrixItemCreateParams,
        suggested_by_username: str,
    ) -> CompetencyMatrixItem:
        resource_ids_to_assign = params.get_resource_ids_to_assign()
        resources = (
            await self.storage.get_resources_by_ids(resource_ids=resource_ids_to_assign)
            if resource_ids_to_assign
            else ExternalResources(values=[])
        )
        if not resources.all_resources_exists_by_ids(ids=set(resource_ids_to_assign)):
            raise CompetencyMatrixItemNotFoundError
        structure = await self.storage.get_item_structure_by_subsection_id(
            subsection_id=params.subsection_id,
        )
        item = params.to_item(
            resources=resources,
            structure=structure,
            published_at=None,
            suggested_by_username=suggested_by_username,
        )
        if item.publish_status == PublishStatusEnum.PUBLISHED:
            item.ensure_public_ready()
        return await self.storage.create_competency_matrix_item(item=item)

    async def create_item_from_queue(
        self,
        *,
        params: QueuedCompetencyMatrixQuestionCreateItemParams,
        current_datetime: datetime,
    ) -> CompetencyMatrixItem:
        queued_question = await self.storage.get_queued_question(
            question_id=params.queued_question_id,
            lock=True,
        )
        if queued_question.claim is not None and queued_question.claim.is_active(
            current_datetime=current_datetime,
        ):
            raise MatrixQuestionClaimConflictError
        resource_ids_to_assign = params.item.get_resource_ids_to_assign()
        resources = (
            await self.storage.get_resources_by_ids(resource_ids=resource_ids_to_assign)
            if resource_ids_to_assign
            else ExternalResources(values=[])
        )
        if not resources.all_resources_exists_by_ids(ids=set(resource_ids_to_assign)):
            raise CompetencyMatrixItemNotFoundError
        structure = await self.storage.get_item_structure_by_subsection_id(
            subsection_id=params.item.subsection_id,
        )
        item = params.item.to_item(
            resources=resources,
            structure=structure,
            published_at=None,
            suggested_by_username=queued_question.suggested_by_username,
        )
        if item.publish_status == PublishStatusEnum.PUBLISHED:
            item.ensure_public_ready()
        created_item = await self.storage.create_competency_matrix_item(item=item)
        await self.storage.delete_queued_question(question_id=params.queued_question_id)
        return created_item

    async def update_item(
        self,
        *,
        params: CompetencyMatrixItemUpdateParams,
    ) -> CompetencyMatrixItem:
        resource_ids_to_assign = params.get_resource_ids_to_assign()
        resources = (
            await self.storage.get_resources_by_ids(resource_ids=resource_ids_to_assign)
            if resource_ids_to_assign
            else ExternalResources(values=[])
        )
        if not resources.all_resources_exists_by_ids(ids=set(resource_ids_to_assign)):
            raise CompetencyMatrixItemNotFoundError
        structure = await self.storage.get_item_structure_by_subsection_id(
            subsection_id=params.subsection_id,
        )
        existing_item = await self.storage.get_competency_matrix_item(item_id=params.id)
        item = params.to_item(
            resources=resources,
            structure=structure,
            published_at=None,
            suggested_by_username=existing_item.suggested_by_username,
        )
        if item.publish_status == PublishStatusEnum.PUBLISHED:
            item.ensure_public_ready()
        return await self.storage.update_competency_matrix_item(item=item)

    async def delete_item(self, *, item_id: str) -> None:
        await self.storage.delete_competency_matrix_item(item_id=item_id)

    async def switch_item_publish_status(
        self,
        *,
        params: CompetencyMatrixItemPublishStatusSwitchParams,
    ) -> None:
        if params.publish_status == PublishStatusEnum.PUBLISHED:
            item = await self.storage.get_competency_matrix_item(item_id=params.item_id)
            item.ensure_public_ready()
        await self.storage.update_competency_matrix_item_publish_status(
            item_id=params.item_id,
            publish_status=params.publish_status,
        )

    async def suggest_question(
        self,
        *,
        params: QuestionSuggestionCreateParams,
    ) -> QueuedCompetencyMatrixQuestion:
        sheet_key = params.question.sheet
        if params.validate_public_sheet and (
            sheet_key is None or not (await self.storage.list_sheets()).has_key(key=sheet_key)
        ):
            raise QuestionSuggestionSheetUnavailableError
        if params.reject_duplicates:
            if sheet_key is None:
                raise QuestionSuggestionSheetUnavailableError
            fingerprint = CompetencyMatrixQuestionFingerprint.from_question(
                question=params.question.question,
            )
            if await self.storage.question_suggestion_exists(
                fingerprint=fingerprint,
                sheet_key=sheet_key,
            ):
                raise QuestionSuggestionAlreadyExistsError
        if params.limit is not None:
            await self.question_suggestion_limiter.check_create_allowed(params=params.limit)
        return await self.storage.create_queued_question(
            params=params.question,
            suggested_by_username=params.suggested_by_username,
        )

    async def list_queued_questions(
        self,
        *,
        current_datetime: datetime,
    ) -> QueuedCompetencyMatrixQuestions:
        return await self.storage.list_queued_questions_with_active_claims(
            active_at=current_datetime,
        )

    async def preview_queued_questions_import(
        self,
        *,
        preview: QuestionQueueImportPreview,
    ) -> QuestionQueueImportPreview:
        queued_questions = await self.storage.list_queued_questions()
        return preview.with_duplicate_warnings(queued_questions=queued_questions)

    async def import_queued_questions(
        self,
        *,
        params: QueuedCompetencyMatrixQuestionsCreateParams,
        suggested_by_username: str,
    ) -> QueuedCompetencyMatrixQuestions:
        return await self.storage.create_queued_questions(
            params=params,
            suggested_by_username=suggested_by_username,
        )

    async def delete_queued_question(
        self,
        *,
        question_id: str,
        current_datetime: datetime,
    ) -> None:
        queued_question = await self.storage.get_queued_question(
            question_id=question_id,
            lock=True,
        )
        if queued_question.claim is not None and queued_question.claim.is_active(
            current_datetime=current_datetime,
        ):
            raise MatrixQuestionClaimConflictError
        await self.storage.delete_queued_question(question_id=question_id)

    async def release_queued_question_agent_claim(self, *, question_id: str) -> None:
        queued_question = await self.storage.get_queued_question(
            question_id=question_id,
            lock=True,
        )
        if queued_question.claim is not None:
            await self.storage.delete_question_claim(claim_id=queued_question.claim.id)
