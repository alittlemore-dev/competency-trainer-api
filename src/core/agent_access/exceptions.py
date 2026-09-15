from core.exceptions import DomainError, EntryNotFoundError


class AgentApiClientError(Exception):
    def __init__(self) -> None:
        super().__init__("agent API request failed")


class AgentCredentialStoreError(Exception):
    def __init__(self) -> None:
        super().__init__("agent credential access failed")


class AgentCredentialCertificateValidationError(AgentCredentialStoreError):
    def __init__(self) -> None:
        Exception.__init__(self, "agent certificate validation failed")


class AgentAuthenticationError(DomainError):
    message = "Agent certificate authentication failed"


class AgentKnownAuthenticationError(AgentAuthenticationError):
    def __init__(self, *, agent_client_id: str, certificate_id: str) -> None:
        self.agent_client_id = agent_client_id
        self.certificate_id = certificate_id
        super().__init__()


class AgentScopeDeniedError(DomainError):
    message = "Agent scope is not allowed"


class MatrixQuestionDraftValidationError(DomainError):
    message = "Matrix question draft payload is invalid"


class MatrixQuestionClaimNotFoundError(EntryNotFoundError):
    message = "Matrix question claim not found"


class MatrixQuestionQueueEmptyError(EntryNotFoundError):
    message = "Matrix question queue is empty"


class AgentCertificateRequestError(DomainError):
    message = "Agent certificate request is invalid"


class AgentClientValidationError(DomainError):
    message = "Agent client payload is invalid"


class AgentClientNotFoundError(EntryNotFoundError):
    message = "Agent client not found"


class AgentClientNameConflictError(DomainError):
    message = "Agent client name already exists"


class AgentIdempotencyConflictError(DomainError):
    message = "Agent request conflicts with a completed request"


class AgentCertificateRotationConflictError(DomainError):
    message = "Agent certificate already has a pending rotation"


class AgentCertificateRotationConfirmationError(DomainError):
    message = "Agent certificate rotation confirmation is invalid"


class AgentCertificateRotationNotFoundError(EntryNotFoundError):
    message = "Agent certificate rotation not found"


class AgentAuditPaginationError(DomainError):
    message = "Agent audit pagination is invalid"
