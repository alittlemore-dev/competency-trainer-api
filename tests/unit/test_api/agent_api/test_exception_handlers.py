from typing import Any, cast
from unittest.mock import Mock

import pytest
from litestar import Request
from litestar.exceptions import HTTPException, ValidationException
from litestar.status_codes import (
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
    HTTP_409_CONFLICT,
)

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
from entrypoints.litestar.api.agent_access.exception_handlers import (
    AGENT_ACCESS_EXCEPTION_HANDLERS,
    AGENT_DOMAIN_ERROR_RESPONSES,
    agent_domain_exception_handler,
    agent_http_exception_handler,
    agent_unexpected_exception_handler,
    agent_validation_exception_handler,
)


class UnmappedAgentDomainError(DomainError):
    message = "AUTHORED-SECRET-MARKER"


class AgentRequestStub:
    scope = {"state": {"agent_request_id": "request-id"}}


def test_agent_exception_handlers_are_a_ready_router_mapping() -> None:
    actual_handlers = AGENT_ACCESS_EXCEPTION_HANDLERS

    assert actual_handlers == {
        DomainError: agent_domain_exception_handler,
        ValidationException: agent_validation_exception_handler,
        HTTPException: agent_http_exception_handler,
        Exception: agent_unexpected_exception_handler,
    }


def test_agent_domain_error_responses_declare_every_current_error_group() -> None:
    actual_responses = AGENT_DOMAIN_ERROR_RESPONSES

    assert actual_responses == {
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


def test_unmapped_agent_domain_error_uses_sanitized_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = cast("Request[Any, Any, Any]", AgentRequestStub())
    error = UnmappedAgentDomainError()
    sanitized_logger = Mock()
    monkeypatch.setattr(
        "entrypoints.litestar.api.agent_access.exception_handlers.log_sanitized_exception",
        sanitized_logger,
    )

    response = agent_domain_exception_handler(request, error)

    assert response.status_code == 500
    assert response.content == {"code": "internal_error", "requestId": "request-id"}
    sanitized_logger.assert_called_once_with(
        event="agent_api_unmapped_domain_error",
        error=error,
        request_id="request-id",
    )
