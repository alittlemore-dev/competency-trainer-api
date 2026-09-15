from abc import ABC, abstractmethod

from core.agent_access.schemas import (
    AgentCertificateIssueParams,
    AgentCertificateRotationConfirmation,
    AgentCertificateRotationStartParams,
    AgentClientCertificateRotation,
    AgentMatrixQuestionClaim,
    IssuedAgentCertificate,
    MatrixAuthoringContext,
    MatrixQuestionDraftSaveParams,
    MatrixQuestionDraftSaveResult,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixResourceSearchParams,
    ExternalResources,
)


class AgentCertificateIssuer(ABC):
    @abstractmethod
    def issue(self, *, params: AgentCertificateIssueParams) -> IssuedAgentCertificate:
        raise NotImplementedError

    @abstractmethod
    def get_certificate_chain_pem(self) -> str:
        raise NotImplementedError


class AgentApiClient(ABC):
    @abstractmethod
    async def claim_next_matrix_question(self) -> AgentMatrixQuestionClaim:
        raise NotImplementedError

    @abstractmethod
    async def get_matrix_authoring_context(self) -> MatrixAuthoringContext:
        raise NotImplementedError

    @abstractmethod
    async def search_matrix_resources(
        self,
        *,
        params: CompetencyMatrixResourceSearchParams,
    ) -> ExternalResources:
        raise NotImplementedError

    @abstractmethod
    async def save_matrix_question_draft(
        self,
        *,
        params: MatrixQuestionDraftSaveParams,
    ) -> MatrixQuestionDraftSaveResult:
        raise NotImplementedError

    @abstractmethod
    async def release_matrix_question_claim(self, *, claim_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def start_certificate_rotation(
        self,
        *,
        params: AgentCertificateRotationStartParams,
    ) -> AgentClientCertificateRotation:
        raise NotImplementedError

    @abstractmethod
    async def confirm_certificate_rotation(
        self,
        *,
        rotation_id: str,
    ) -> AgentCertificateRotationConfirmation:
        raise NotImplementedError
