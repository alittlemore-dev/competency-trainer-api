from abc import ABC, abstractmethod
from datetime import datetime

from core.agent_access.schemas import (
    AgentAuditEvent,
    AgentAuditEventCreateParams,
    AgentAuditEventPageQuery,
    AgentCertificate,
    AgentCertificateRotation,
    AgentClient,
    AgentClientCertificateRotation,
    AgentClientRevokeParams,
    AgentCredential,
    IssuedLocalAgentCredentialRotation,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
    PreparedLocalAgentCredentialRotation,
)


class AgentAdminStorage(ABC):
    @abstractmethod
    async def client_name_exists(self, *, normalized_name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_client(self, *, client: AgentClient) -> AgentClient:
        raise NotImplementedError

    @abstractmethod
    async def list_clients(self) -> list[AgentClient]:
        raise NotImplementedError

    @abstractmethod
    async def create_certificate(
        self,
        *,
        certificate: AgentCertificate,
    ) -> AgentCertificate:
        raise NotImplementedError

    @abstractmethod
    async def list_certificates(self, *, agent_client_id: str) -> list[AgentCertificate]:
        raise NotImplementedError

    @abstractmethod
    async def revoke_client(self, *, params: AgentClientRevokeParams) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_audit_events(
        self,
        *,
        params: AgentAuditEventPageQuery,
    ) -> tuple[AgentAuditEvent, ...]:
        raise NotImplementedError


class AgentIdentityStorage(ABC):
    @abstractmethod
    async def get_credential_by_fingerprint(
        self,
        *,
        fingerprint_sha256: str,
    ) -> AgentCredential:
        raise NotImplementedError


class AgentCertificateRotationStorage(ABC):
    @abstractmethod
    async def create_audit_event(
        self,
        *,
        params: AgentAuditEventCreateParams,
    ) -> AgentAuditEvent:
        raise NotImplementedError

    @abstractmethod
    async def get_client_for_rotation(self, *, agent_client_id: str) -> AgentClient:
        raise NotImplementedError

    @abstractmethod
    async def get_certificate_for_rotation(
        self,
        *,
        certificate_id: str,
        agent_client_id: str,
    ) -> AgentCertificate:
        raise NotImplementedError

    @abstractmethod
    async def get_certificate_by_id(
        self,
        *,
        certificate_id: str,
        agent_client_id: str,
    ) -> AgentCertificate:
        raise NotImplementedError

    @abstractmethod
    async def get_certificate_rotation(
        self,
        *,
        rotation_id: str,
    ) -> AgentCertificateRotation | None:
        raise NotImplementedError

    @abstractmethod
    async def get_pending_certificate_rotation(
        self,
        *,
        current_certificate_id: str,
    ) -> AgentCertificateRotation | None:
        raise NotImplementedError

    @abstractmethod
    async def create_certificate_rotation(
        self,
        *,
        rotation: AgentCertificateRotation,
        replacement: AgentCertificate,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def confirm_certificate_rotation(
        self,
        *,
        rotation_id: str,
        current_certificate_id: str,
        confirmed_at: datetime,
    ) -> AgentCertificateRotation:
        raise NotImplementedError


class MatrixAgentStorage(ABC):
    @abstractmethod
    async def create_audit_event(
        self,
        *,
        params: AgentAuditEventCreateParams,
    ) -> AgentAuditEvent:
        raise NotImplementedError

    @abstractmethod
    async def claim_next_matrix_question(
        self,
        *,
        agent_client_id: str,
        claimed_at: datetime,
        expires_at: datetime,
    ) -> MatrixQuestionClaim:
        raise NotImplementedError

    @abstractmethod
    async def get_matrix_question_draft_completion(
        self,
        *,
        claim_id: str,
        agent_client_id: str,
    ) -> MatrixQuestionDraftCompletion | None:
        raise NotImplementedError

    @abstractmethod
    async def lock_matrix_question_claim(
        self,
        *,
        agent_client_id: str,
        claim_id: str,
    ) -> MatrixQuestionClaim | None:
        raise NotImplementedError

    @abstractmethod
    async def create_matrix_question_draft_completion(
        self,
        *,
        completion: MatrixQuestionDraftCompletion,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def consume_matrix_question_claim(
        self,
        *,
        agent_client_id: str,
        claim_id: str,
        queue_item_id: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def release_matrix_question_claim(
        self,
        *,
        agent_client_id: str,
        claim_id: str,
        released_at: datetime,
    ) -> str:
        raise NotImplementedError


class AgentAuditStorage(ABC):
    @abstractmethod
    async def create_audit_event(
        self,
        *,
        params: AgentAuditEventCreateParams,
    ) -> AgentAuditEvent:
        raise NotImplementedError

    @abstractmethod
    async def prune_audit_events(self, *, created_at_before: datetime) -> int:
        raise NotImplementedError


class LocalAgentCredentialRotationStorage(ABC):
    @abstractmethod
    def get_active_certificate_expires_at(self) -> datetime:
        raise NotImplementedError

    @abstractmethod
    def load_pending_rotation(
        self,
    ) -> PreparedLocalAgentCredentialRotation | IssuedLocalAgentCredentialRotation | None:
        raise NotImplementedError

    @abstractmethod
    def prepare_rotation(
        self,
        *,
        rotation_id: str,
    ) -> PreparedLocalAgentCredentialRotation:
        raise NotImplementedError

    @abstractmethod
    def persist_replacement(
        self,
        *,
        pending: PreparedLocalAgentCredentialRotation,
        response: AgentClientCertificateRotation,
        current_datetime: datetime,
    ) -> IssuedLocalAgentCredentialRotation:
        raise NotImplementedError

    @abstractmethod
    def is_rotation_active(self, *, rotation_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def activate_rotation(self, *, rotation: IssuedLocalAgentCredentialRotation) -> None:
        raise NotImplementedError

    @abstractmethod
    def complete_rotation(self, *, rotation: IssuedLocalAgentCredentialRotation) -> None:
        raise NotImplementedError
