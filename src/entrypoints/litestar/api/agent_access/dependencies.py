from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Protocol, cast

from litestar import Request
from litestar.di import NamedDependency
from litestar.params import PathParameter, QueryParameter

from core.agent_access.schemas import (
    AgentCertificateRotationConfirmParams,
    AgentCertificateRotationParams,
    AgentIdentity,
)
from core.competency_matrix.schemas import CompetencyMatrixResourceSearchParams
from core.i18n.enums import LanguageEnum
from core.types import SearchName
from entrypoints.litestar.api.agent_access.schemas import (
    AgentCertificateRotationRequestSchema,
)
from infra.config.constants import constants


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentRequestMetadata:
    request_id: str
    requested_at: datetime
    input_digest: str


class AgentInputHasher(Protocol):
    def hexdigest(self) -> str: ...


AgentClaimIdPath = Annotated[
    str,
    PathParameter(
        name="claim_id",
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
    ),
]
AgentRotationIdPath = Annotated[
    str,
    PathParameter(
        name="rotation_id",
        min_length=32,
        max_length=32,
        pattern=r"^[0-9a-f]{32}$",
    ),
]
AgentResourceSearchNameQuery = Annotated[
    str,
    QueryParameter(
        name="searchName",
        min_length=1,
        max_length=constants.admin_validation.short_text_max_length,
    ),
]
AgentResourceSearchLimitQuery = Annotated[int, QueryParameter(name="limit", ge=1, le=50)]
AgentResourceLanguageQuery = Annotated[LanguageEnum, QueryParameter(name="language")]


def provide_agent_request_metadata(request: Request) -> AgentRequestMetadata:
    state = request.scope["state"]
    return AgentRequestMetadata(
        request_id=cast("str", state["agent_request_id"]),
        requested_at=cast("datetime", state["agent_requested_at"]),
        input_digest=cast("AgentInputHasher", state["agent_input_hasher"]).hexdigest(),
    )


def provide_agent_identity(request: Request) -> AgentIdentity:
    return cast("AgentIdentity", request.user)


def provide_matrix_resource_search_params(
    search_name: AgentResourceSearchNameQuery,
    limit: AgentResourceSearchLimitQuery,
    language: AgentResourceLanguageQuery,
) -> CompetencyMatrixResourceSearchParams:
    return CompetencyMatrixResourceSearchParams(
        search_name=SearchName(search_name),
        limit=limit,
        language=language,
    )


def provide_agent_certificate_rotation_params(
    data: AgentCertificateRotationRequestSchema,
    metadata: NamedDependency[AgentRequestMetadata],
) -> AgentCertificateRotationParams:
    return AgentCertificateRotationParams(
        rotation_id=data.rotation_id,
        csr_pem=data.csr_pem,
        rotated_at=metadata.requested_at,
    )


def provide_agent_certificate_rotation_confirm_params(
    rotation_id: AgentRotationIdPath,
    metadata: NamedDependency[AgentRequestMetadata],
) -> AgentCertificateRotationConfirmParams:
    return AgentCertificateRotationConfirmParams(
        rotation_id=rotation_id,
        confirmed_at=metadata.requested_at,
    )
