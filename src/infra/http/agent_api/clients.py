import ssl
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx

from core.agent_access.clients import AgentApiClient
from core.agent_access.exceptions import AgentApiClientError
from core.agent_access.schemas import (
    AgentCertificateRotationConfirmation,
    AgentCertificateRotationStartParams,
    AgentClientCertificateRotation,
    AgentMatrixQuestionClaim,
    MatrixAuthoringContext,
    MatrixQuestionDraftSaveParams,
    MatrixQuestionDraftSaveResult,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixResourceSearchParams,
    ExternalResources,
)
from infra.config.agent_access import AgentBridgeSettings
from infra.cryptography.agent_credentials import AgentCredentialPairProvider
from infra.http.agent_api.schemas import (
    AgentApiWireSchema,
    AgentCertificateRotationConfirmResponse,
    AgentCertificateRotationRequest,
    AgentCertificateRotationResponse,
    ClaimReference,
    MatrixAuthoringContextResponse,
    MatrixQuestionClaimReleaseResponse,
    MatrixQuestionClaimResponse,
    MatrixQuestionDraftSaveRequest,
    MatrixQuestionDraftSaveResponse,
    MatrixResourceSearchQuery,
    MatrixResourcesResponse,
    RotationReference,
)

AgentApiWireSchemaT = TypeVar("AgentApiWireSchemaT", bound=AgentApiWireSchema)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentApiHttpClient(AgentApiClient):
    settings: AgentBridgeSettings
    credential_provider: AgentCredentialPairProvider
    transport: httpx.AsyncBaseTransport | None

    async def claim_next_matrix_question(self) -> AgentMatrixQuestionClaim:
        response = await self._request(
            method="POST",
            path="matrix/question-claims",
            response_schema=MatrixQuestionClaimResponse,
        )
        return response.to_domain_schema()

    async def get_matrix_authoring_context(self) -> MatrixAuthoringContext:
        response = await self._request(
            method="GET",
            path="matrix/authoring-context",
            response_schema=MatrixAuthoringContextResponse,
        )
        return response.to_domain_schema()

    async def search_matrix_resources(
        self,
        *,
        params: CompetencyMatrixResourceSearchParams,
    ) -> ExternalResources:
        try:
            query = MatrixResourceSearchQuery(
                search_name=params.search_name,
                limit=params.limit,
                language=params.language.value,
            )
        except ValueError:
            raise AgentApiClientError from None
        response = await self._request(
            method="GET",
            path="matrix/resources",
            query=query.model_dump(mode="json", by_alias=True),
            response_schema=MatrixResourcesResponse,
        )
        return response.to_domain_schema()

    async def save_matrix_question_draft(
        self,
        *,
        params: MatrixQuestionDraftSaveParams,
    ) -> MatrixQuestionDraftSaveResult:
        try:
            claim = ClaimReference(claim_id=params.claim_id)
            request = MatrixQuestionDraftSaveRequest.from_domain_schema(schema=params)
        except ValueError:
            raise AgentApiClientError from None
        response = await self._request(
            method="PUT",
            path=f"matrix/question-claims/{claim.claim_id}/draft",
            json=request.model_dump(mode="json", by_alias=True),
            response_schema=MatrixQuestionDraftSaveResponse,
        )
        return response.to_domain_schema()

    async def release_matrix_question_claim(self, *, claim_id: str) -> None:
        try:
            claim = ClaimReference(claim_id=claim_id)
        except ValueError:
            raise AgentApiClientError from None
        await self._request(
            method="DELETE",
            path=f"matrix/question-claims/{claim.claim_id}",
            response_schema=MatrixQuestionClaimReleaseResponse,
        )

    async def start_certificate_rotation(
        self,
        *,
        params: AgentCertificateRotationStartParams,
    ) -> AgentClientCertificateRotation:
        try:
            request = AgentCertificateRotationRequest.from_domain_schema(schema=params)
        except ValueError:
            raise AgentApiClientError from None
        response = await self._request(
            method="POST",
            path="certificate-rotations",
            json=request.model_dump(mode="json", by_alias=True),
            response_schema=AgentCertificateRotationResponse,
        )
        return response.to_domain_schema()

    async def confirm_certificate_rotation(
        self,
        *,
        rotation_id: str,
    ) -> AgentCertificateRotationConfirmation:
        try:
            rotation = RotationReference(rotation_id=rotation_id)
        except ValueError:
            raise AgentApiClientError from None
        response = await self._request(
            method="POST",
            path=f"certificate-rotations/{rotation.rotation_id}/confirm",
            response_schema=AgentCertificateRotationConfirmResponse,
        )
        return response.to_domain_schema()

    async def _request(
        self,
        *,
        method: str,
        path: str,
        response_schema: type[AgentApiWireSchemaT],
        query: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> AgentApiWireSchemaT:
        pair = self.credential_provider.active_pair()
        try:
            ssl_context = ssl.create_default_context(
                cafile=str(self.settings.ca_certificate_file),
            )
            ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
            ssl_context.load_cert_chain(
                certfile=str(pair.certificate_file),
                keyfile=str(pair.private_key_file),
            )
            async with httpx.AsyncClient(
                base_url=f"{self.settings.api_base_url}/",
                verify=ssl_context,
                timeout=self.settings.request_timeout_seconds,
                transport=self.transport,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.request(method, path, params=query, json=json)
            response.raise_for_status()
            return response_schema.model_validate(
                response.json(),
                by_alias=True,
                by_name=False,
            )
        except httpx.HTTPError, OSError, ValueError:
            raise AgentApiClientError from None
