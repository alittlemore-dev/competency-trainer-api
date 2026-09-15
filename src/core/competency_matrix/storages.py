from abc import ABC, abstractmethod
from datetime import datetime

from core.competency_matrix.schemas import (
    CompetencyMatrixFilterOptions,
    CompetencyMatrixItem,
    CompetencyMatrixItemFilters,
    CompetencyMatrixItemStructure,
    CompetencyMatrixQuestionFingerprint,
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
    CompetencyMatrixWorkspaceFilters,
    CompetencyMatrixWorkspaceItem,
    CompetencyMatrixWorkspaceSummary,
    ExternalResources,
    QuestionSuggestionQuota,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestions,
    QueuedCompetencyMatrixQuestionsCreateParams,
    Sheets,
)
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum


class CompetencyMatrixStorage(ABC):
    @abstractmethod
    async def list_sheets(self) -> Sheets:
        raise NotImplementedError

    @abstractmethod
    async def list_structure(self) -> CompetencyMatrixStructure:
        raise NotImplementedError

    @abstractmethod
    async def get_item_structure_by_subsection_id(
        self,
        *,
        subsection_id: str,
    ) -> CompetencyMatrixItemStructure:
        raise NotImplementedError

    @abstractmethod
    async def create_sheet(
        self,
        *,
        params: CompetencyMatrixSheetCreateParams,
    ) -> CompetencyMatrixStructureSheet:
        raise NotImplementedError

    @abstractmethod
    async def create_section(
        self,
        *,
        params: CompetencyMatrixSectionCreateParams,
    ) -> CompetencyMatrixStructureSection:
        raise NotImplementedError

    @abstractmethod
    async def create_subsection(
        self,
        *,
        params: CompetencyMatrixSubsectionCreateParams,
    ) -> CompetencyMatrixStructureSubsection:
        raise NotImplementedError

    @abstractmethod
    async def update_sheet_priorities(
        self,
        *,
        params: CompetencyMatrixSheetPriorityUpdateParams,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update_section_priorities(
        self,
        *,
        params: CompetencyMatrixSectionPriorityUpdateParams,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update_subsection_priorities(
        self,
        *,
        params: CompetencyMatrixSubsectionPriorityUpdateParams,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_competency_matrix_items(
        self,
        *,
        filters: CompetencyMatrixItemFilters,
    ) -> list[CompetencyMatrixItem]:
        raise NotImplementedError

    @abstractmethod
    async def list_competency_matrix_workspace_items(
        self,
        *,
        filters: CompetencyMatrixWorkspaceFilters,
    ) -> tuple[
        list[CompetencyMatrixWorkspaceItem],
        int,
        CompetencyMatrixWorkspaceSummary,
    ]:
        raise NotImplementedError

    @abstractmethod
    async def list_competency_matrix_workspace_filter_options(
        self,
        *,
        language: LanguageEnum,
    ) -> CompetencyMatrixFilterOptions:
        raise NotImplementedError

    @abstractmethod
    async def get_competency_matrix_item(self, item_id: str) -> CompetencyMatrixItem:
        raise NotImplementedError

    @abstractmethod
    async def get_competency_matrix_item_by_slug(self, slug: str) -> CompetencyMatrixItem:
        raise NotImplementedError

    @abstractmethod
    async def create_competency_matrix_item(
        self,
        item: CompetencyMatrixItem,
    ) -> CompetencyMatrixItem:
        raise NotImplementedError

    @abstractmethod
    async def update_competency_matrix_item(
        self,
        item: CompetencyMatrixItem,
    ) -> CompetencyMatrixItem:
        raise NotImplementedError

    @abstractmethod
    async def update_competency_matrix_item_publish_status(
        self,
        item_id: str,
        publish_status: PublishStatusEnum,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_resources_by_ids(
        self,
        resource_ids: list[str],
    ) -> ExternalResources:
        raise NotImplementedError

    @abstractmethod
    async def delete_competency_matrix_item(self, item_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def search_competency_matrix_resources(
        self,
        search_name: str,
        limit: int,
        language: LanguageEnum,
    ) -> ExternalResources:
        raise NotImplementedError

    @abstractmethod
    async def list_queued_questions(self) -> QueuedCompetencyMatrixQuestions:
        raise NotImplementedError

    @abstractmethod
    async def list_queued_questions_with_active_claims(
        self,
        *,
        active_at: datetime,
    ) -> QueuedCompetencyMatrixQuestions:
        raise NotImplementedError

    @abstractmethod
    async def get_queued_question(
        self,
        question_id: str,
        *,
        lock: bool,
    ) -> QueuedCompetencyMatrixQuestion:
        raise NotImplementedError

    @abstractmethod
    async def question_suggestion_exists(
        self,
        *,
        fingerprint: CompetencyMatrixQuestionFingerprint,
        sheet_key: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_queued_question(
        self,
        *,
        params: QueuedCompetencyMatrixQuestionCreateParams,
        suggested_by_username: str,
    ) -> QueuedCompetencyMatrixQuestion:
        raise NotImplementedError

    @abstractmethod
    async def create_queued_questions(
        self,
        *,
        params: QueuedCompetencyMatrixQuestionsCreateParams,
        suggested_by_username: str,
    ) -> QueuedCompetencyMatrixQuestions:
        raise NotImplementedError

    @abstractmethod
    async def delete_queued_question(self, question_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_question_claim(self, claim_id: str) -> None:
        raise NotImplementedError


class QuestionSuggestionQuotaStorage(ABC):
    @abstractmethod
    async def consume_question_suggestion_quota(
        self,
        *,
        actor_key: str,
        limit: int,
        ttl_seconds: int,
    ) -> QuestionSuggestionQuota:
        raise NotImplementedError
