from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.exceptions import DomainError, EntryNotFoundError

if TYPE_CHECKING:
    from core.competency_matrix.schemas import CompetencyMatrixMissingFieldEnum


class CompetencyMatrixItemNotFoundError(EntryNotFoundError):
    message = "Competency matrix item not found"


class CompetencyMatrixItemConflictError(DomainError):
    message = "Competency matrix item already exists"


class CompetencyMatrixStructureNotFoundError(EntryNotFoundError):
    message = "Competency matrix structure entry not found"


class CompetencyMatrixStructureAlreadyExistsError(DomainError):
    message = "Competency matrix structure entry already exists"


class CompetencyMatrixStructurePriorityInvalidError(DomainError):
    message = "Competency matrix structure priority order is invalid"


class CompetencyMatrixItemNotPublicReadyError(DomainError):
    message = "Competency matrix item is not public-ready."

    def __init__(
        self,
        *,
        missing_fields: tuple[CompetencyMatrixMissingFieldEnum, ...],
    ) -> None:
        self.missing_fields = missing_fields
        super().__init__()


class QueuedCompetencyMatrixQuestionNotFoundError(EntryNotFoundError):
    message = "Queued competency matrix question not found"


class MatrixQuestionClaimConflictError(DomainError):
    message = "Queued competency matrix question is claimed by an agent"


class QuestionSuggestionQuotaExceededError(DomainError):
    message = "Question suggestion daily quota exceeded"


class QuestionSuggestionAlreadyExistsError(DomainError):
    message = "Question already exists in the competency matrix or suggestion queue"


class QuestionSuggestionSheetUnavailableError(DomainError):
    message = "Selected competency matrix sheet is not publicly available"


@dataclass(frozen=True, kw_only=True, slots=True)
class QuestionQueueImportIssue:
    message: str
    row_number: int | None

    @property
    def attr_name(self) -> str:
        if self.row_number is None:
            return "file"
        return f"file.row.{self.row_number}"


class QuestionQueueImportInvalidError(DomainError):
    message = "Question queue import file is invalid."

    def __init__(self, *, issues: list[QuestionQueueImportIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__()
