from typing import Any

from litestar import Request, Response
from litestar.exceptions import HTTPException, ValidationException
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_405_METHOD_NOT_ALLOWED,
    HTTP_409_CONFLICT,
    HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from litestar.types import ExceptionHandlersMap

from core.agent_access.exceptions import (
    AgentAuditPaginationError,
    AgentAuthenticationError,
    AgentCertificateRequestError,
    AgentCertificateRotationConfirmationError,
    AgentCertificateRotationConflictError,
    AgentClientNameConflictError,
    AgentClientValidationError,
    AgentIdempotencyConflictError,
    AgentScopeDeniedError,
    MatrixQuestionDraftValidationError,
)
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemConflictError,
    CompetencyMatrixStructureAlreadyExistsError,
    MatrixQuestionClaimConflictError,
)
from core.exceptions import DomainError, EntryNotFoundError
from infra.config.loggers import log_sanitized_exception

AGENT_DOMAIN_ERROR_RESPONSES: dict[type[DomainError], tuple[int, str]] = {
    AgentAuthenticationError: (HTTP_401_UNAUTHORIZED, "agent_authentication_failed"),
    AgentScopeDeniedError: (HTTP_403_FORBIDDEN, "agent_scope_denied"),
    EntryNotFoundError: (HTTP_404_NOT_FOUND, "not_found"),
    AgentIdempotencyConflictError: (HTTP_409_CONFLICT, "agent_idempotency_conflict"),
    AgentCertificateRotationConflictError: (HTTP_409_CONFLICT, "conflict"),
    AgentCertificateRotationConfirmationError: (HTTP_409_CONFLICT, "conflict"),
    AgentClientNameConflictError: (HTTP_409_CONFLICT, "conflict"),
    CompetencyMatrixItemConflictError: (HTTP_409_CONFLICT, "conflict"),
    CompetencyMatrixStructureAlreadyExistsError: (HTTP_409_CONFLICT, "conflict"),
    MatrixQuestionClaimConflictError: (HTTP_409_CONFLICT, "conflict"),
    AgentAuditPaginationError: (HTTP_400_BAD_REQUEST, "invalid_request"),
    AgentCertificateRequestError: (HTTP_400_BAD_REQUEST, "invalid_request"),
    AgentClientValidationError: (HTTP_400_BAD_REQUEST, "invalid_request"),
    MatrixQuestionDraftValidationError: (HTTP_400_BAD_REQUEST, "invalid_request"),
}


def _request_id(request: Request[Any, Any, Any]) -> str:
    value = request.scope["state"].get("agent_request_id")
    return value if isinstance(value, str) else "unavailable"


def agent_domain_exception_handler(
    request: Request[Any, Any, Any],
    exc: DomainError,
) -> Response[dict[str, str]]:
    response = next(
        (
            declared_response
            for error_type, declared_response in AGENT_DOMAIN_ERROR_RESPONSES.items()
            if isinstance(exc, error_type)
        ),
        None,
    )
    if response is None:
        log_sanitized_exception(
            event="agent_api_unmapped_domain_error",
            error=exc,
            request_id=_request_id(request),
        )
        response = (HTTP_500_INTERNAL_SERVER_ERROR, "internal_error")
    status_code, code = response
    return Response(
        content={"code": code, "requestId": _request_id(request)},
        status_code=status_code,
    )


def agent_validation_exception_handler(
    request: Request[Any, Any, Any],
    exc: ValidationException,
) -> Response[dict[str, object]]:
    errors: list[dict[str, object]] = []
    if isinstance(exc.extra, list):
        for raw_error in exc.extra:
            if not isinstance(raw_error, dict):
                continue
            error_type = raw_error.get("type")
            errors.append(
                {
                    "location": ["request"],
                    "code": error_type if isinstance(error_type, str) else "invalid",
                },
            )
    if not errors:
        errors.append({"location": ["request"], "code": "invalid"})
    return Response(
        content={
            "code": "validation_error",
            "requestId": _request_id(request),
            "errors": errors,
        },
        status_code=HTTP_400_BAD_REQUEST,
    )


def agent_http_exception_handler(
    request: Request[Any, Any, Any],
    exc: HTTPException,
) -> Response[dict[str, str]]:
    status_code = exc.status_code
    code = {
        HTTP_404_NOT_FOUND: "not_found",
        HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
        HTTP_413_REQUEST_ENTITY_TOO_LARGE: "request_too_large",
    }.get(
        status_code,
        "invalid_request" if status_code < HTTP_500_INTERNAL_SERVER_ERROR else "internal_error",
    )
    return Response(
        content={"code": code, "requestId": _request_id(request)},
        status_code=status_code,
        headers=exc.headers,
    )


def agent_unexpected_exception_handler(
    request: Request[Any, Any, Any],
    exc: Exception,
) -> Response[dict[str, str]]:
    log_sanitized_exception(
        event="agent_api_request_failed",
        error=exc,
        request_id=_request_id(request),
        action=request.scope["state"].get("agent_action", "unavailable"),
    )
    return Response(
        content={"code": "internal_error", "requestId": _request_id(request)},
        status_code=HTTP_500_INTERNAL_SERVER_ERROR,
    )


AGENT_ACCESS_EXCEPTION_HANDLERS: ExceptionHandlersMap = {
    DomainError: agent_domain_exception_handler,
    ValidationException: agent_validation_exception_handler,
    HTTPException: agent_http_exception_handler,
    Exception: agent_unexpected_exception_handler,
}
