from typing import Any

from litestar import Request, Response
from verbose_http_exceptions import (
    BadRequestHTTPException,
    ConflictHTTPException,
    ForbiddenHTTPException,
    InternalServerErrorHTTPException,
    NotFoundHTTPException,
    TooManyRequestsHTTPException,
    UnauthorizedHTTPException,
    status,
)
from verbose_http_exceptions.exc.base import BaseVerboseHTTPException, VerboseHTTPExceptionDict
from verbose_http_exceptions.ext.litestar import (
    ALL_EXCEPTION_HANDLERS_MAP,
    verbose_http_exception_handler,
)
from verbose_http_exceptions.ext.litestar.types import LitestarExceptionHandlersMap

from core.account.exceptions import (
    AccountUsernameAlreadyExistsError,
    InvalidManagedAccountRoleError,
    ManagedAccountActionForbiddenError,
    SelfAccountActionForbiddenError,
)
from core.agent_access.exceptions import (
    AgentAuditPaginationError,
    AgentAuthenticationError,
    AgentCertificateRequestError,
    AgentClientNameConflictError,
    AgentClientValidationError,
    AgentScopeDeniedError,
    MatrixQuestionDraftValidationError,
)
from core.articles.exceptions import (
    ArticleFolderAlreadyExistsError,
    ArticleFolderPriorityInvalidError,
)
from core.auth.exceptions import ForbiddenError, UnauthorizedError
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemNotPublicReadyError,
    CompetencyMatrixStructureAlreadyExistsError,
    CompetencyMatrixStructurePriorityInvalidError,
    MatrixQuestionClaimConflictError,
    QuestionQueueImportInvalidError,
    QuestionSuggestionAlreadyExistsError,
    QuestionSuggestionQuotaExceededError,
    QuestionSuggestionSheetUnavailableError,
)
from core.exceptions import DomainError, EntryNotFoundError
from core.files.exceptions import FileClientInternalError, FileInUseError, InvalidFileDataError
from infra.healthcheck import ReadinessCheckError

DOMAIN_ERROR_MAPPING: dict[type[DomainError], type[BaseVerboseHTTPException]] = {
    EntryNotFoundError: NotFoundHTTPException,
    UnauthorizedError: UnauthorizedHTTPException,
    ForbiddenError: ForbiddenHTTPException,
    AgentAuthenticationError: UnauthorizedHTTPException,
    AgentScopeDeniedError: ForbiddenHTTPException,
    AgentCertificateRequestError: BadRequestHTTPException,
    AgentClientNameConflictError: ConflictHTTPException,
    AgentClientValidationError: BadRequestHTTPException,
    AgentAuditPaginationError: BadRequestHTTPException,
    MatrixQuestionDraftValidationError: BadRequestHTTPException,
    MatrixQuestionClaimConflictError: ConflictHTTPException,
    InvalidFileDataError: BadRequestHTTPException,
    FileInUseError: BadRequestHTTPException,
    FileClientInternalError: InternalServerErrorHTTPException,
    CompetencyMatrixItemNotPublicReadyError: BadRequestHTTPException,
    CompetencyMatrixStructureAlreadyExistsError: BadRequestHTTPException,
    CompetencyMatrixStructurePriorityInvalidError: BadRequestHTTPException,
    QuestionSuggestionQuotaExceededError: TooManyRequestsHTTPException,
    QuestionSuggestionAlreadyExistsError: ConflictHTTPException,
    QuestionSuggestionSheetUnavailableError: BadRequestHTTPException,
    QuestionQueueImportInvalidError: BadRequestHTTPException,
    AccountUsernameAlreadyExistsError: BadRequestHTTPException,
    InvalidManagedAccountRoleError: BadRequestHTTPException,
    SelfAccountActionForbiddenError: ForbiddenHTTPException,
    ManagedAccountActionForbiddenError: ForbiddenHTTPException,
    ArticleFolderAlreadyExistsError: BadRequestHTTPException,
    ArticleFolderPriorityInvalidError: BadRequestHTTPException,
}


def find_verbose_exception_type(
    *,
    domain_error: DomainError,
) -> type[BaseVerboseHTTPException]:
    for domain_error_type, verbose_exception_type in DOMAIN_ERROR_MAPPING.items():
        if isinstance(domain_error, domain_error_type):
            return verbose_exception_type
    return InternalServerErrorHTTPException


def create_verbose_exception[VerboseHTTPExceptionT: BaseVerboseHTTPException](
    *,
    domain_error: DomainError,
    verbose_exception_type: type[VerboseHTTPExceptionT],
) -> VerboseHTTPExceptionT:
    if isinstance(domain_error, QuestionQueueImportInvalidError):
        nested_errors = tuple(
            BadRequestHTTPException(
                message=issue.message,
                location="body",
                attr_name=issue.attr_name,
            )
            for issue in domain_error.issues
        )
        return verbose_exception_type(*nested_errors, message=domain_error.message)
    return verbose_exception_type(message=domain_error.message)


def domain_to_verbose_response_handler(
    request: Request[Any, Any, Any],
    exc: Exception,
) -> Response[VerboseHTTPExceptionDict]:
    if not isinstance(exc, DomainError):
        return verbose_http_exception_handler(
            request,
            InternalServerErrorHTTPException(message=str(exc)),
        )
    return verbose_http_exception_handler(
        request,
        create_verbose_exception(
            domain_error=exc,
            verbose_exception_type=find_verbose_exception_type(domain_error=exc),
        ),
    )


def readiness_check_error_handler(
    _request: Request[Any, Any, Any],
    _exc: Exception,
) -> Response[str]:
    return Response(content="", status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def get_litestar_exception_handlers() -> LitestarExceptionHandlersMap:
    return {
        **ALL_EXCEPTION_HANDLERS_MAP,
        DomainError: domain_to_verbose_response_handler,
        ReadinessCheckError: readiness_check_error_handler,
    }
