from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, delete, get, post, put, status_codes
from litestar.di import NamedDependency, Provide
from litestar.middleware import DefineMiddleware

from core.agent_access.enums import AgentActionEnum, AgentScopeEnum
from core.agent_access.schemas import (
    AgentCertificatePolicy,
    AgentCertificateRotationConfirmParams,
    AgentCertificateRotationParams,
    AgentIdentity,
    MatrixAgentPolicy,
)
from core.agent_access.use_cases import AgentCertificateRotationUseCase, MatrixAgentUseCase
from core.competency_matrix.schemas import CompetencyMatrixResourceSearchParams
from entrypoints.litestar.api.agent_access.dependencies import (
    AgentClaimIdPath,
    AgentRequestMetadata,
    provide_agent_certificate_rotation_confirm_params,
    provide_agent_certificate_rotation_params,
    provide_agent_identity,
    provide_agent_request_metadata,
    provide_matrix_resource_search_params,
)
from entrypoints.litestar.api.agent_access.exception_handlers import (
    AGENT_ACCESS_EXCEPTION_HANDLERS,
)
from entrypoints.litestar.api.agent_access.schemas import (
    AgentCertificateRotationConfirmResponseSchema,
    AgentCertificateRotationResponseSchema,
    MatrixAuthoringContextResponseSchema,
    MatrixQuestionClaimReleaseResponseSchema,
    MatrixQuestionClaimResponseSchema,
    MatrixQuestionDraftSaveRequestSchema,
    MatrixQuestionDraftSaveResponseSchema,
    MatrixResourcesResponseSchema,
)
from entrypoints.litestar.middlewares.agent_authentication import (
    AgentAuthenticationMiddleware,
    agent_scope_guard,
)
from entrypoints.litestar.middlewares.agent_transaction import AgentTransactionMiddleware
from infra.config.constants import constants


class AgentApiController(Controller):
    path = constants.agent_access.api_path_prefix
    guards = [agent_scope_guard]

    @post(
        "/matrix/question-claims",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.CLAIM_NEXT_MATRIX_QUESTION,
            "agent_scope": AgentScopeEnum.MATRIX_QUEUE_CLAIM,
            "agent_identity_mode": "business",
        },
    )
    async def claim_next_matrix_question(
        self,
        identity: NamedDependency[AgentIdentity],
        metadata: NamedDependency[AgentRequestMetadata],
        use_case: FromDishka[MatrixAgentUseCase],
        policy: FromDishka[MatrixAgentPolicy],
    ) -> MatrixQuestionClaimResponseSchema:
        claim = await use_case.claim_next_matrix_question(
            identity=identity,
            claimed_at=metadata.requested_at,
            input_digest=metadata.input_digest,
            policy=policy,
        )
        return MatrixQuestionClaimResponseSchema.from_domain_schema(schema=claim)

    @get(
        "/matrix/authoring-context",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.GET_MATRIX_AUTHORING_CONTEXT,
            "agent_scope": AgentScopeEnum.MATRIX_CONTEXT_READ,
            "agent_identity_mode": "business",
        },
    )
    async def get_matrix_authoring_context(
        self,
        identity: NamedDependency[AgentIdentity],
        metadata: NamedDependency[AgentRequestMetadata],
        use_case: FromDishka[MatrixAgentUseCase],
        policy: FromDishka[MatrixAgentPolicy],
    ) -> MatrixAuthoringContextResponseSchema:
        context = await use_case.get_matrix_authoring_context(
            identity=identity,
            request_id=metadata.request_id,
            input_digest=metadata.input_digest,
            requested_at=metadata.requested_at,
            policy=policy,
        )
        return MatrixAuthoringContextResponseSchema.from_domain_schema(schema=context)

    @get(
        "/matrix/resources",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
            "params": Provide(provide_matrix_resource_search_params, sync_to_thread=False),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.SEARCH_MATRIX_RESOURCES,
            "agent_scope": AgentScopeEnum.MATRIX_RESOURCES_READ,
            "agent_identity_mode": "business",
        },
    )
    async def search_matrix_resources(
        self,
        identity: NamedDependency[AgentIdentity],
        metadata: NamedDependency[AgentRequestMetadata],
        params: NamedDependency[CompetencyMatrixResourceSearchParams],
        use_case: FromDishka[MatrixAgentUseCase],
    ) -> MatrixResourcesResponseSchema:
        resources = await use_case.search_matrix_resources(
            identity=identity,
            params=params,
            request_id=metadata.request_id,
            input_digest=metadata.input_digest,
            requested_at=metadata.requested_at,
        )
        return MatrixResourcesResponseSchema.from_domain_schema(schema=resources)

    @put(
        "/matrix/question-claims/{claim_id:str}/draft",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
            "agent_scope": AgentScopeEnum.MATRIX_DRAFT_CREATE,
            "agent_identity_mode": "business",
        },
    )
    async def save_matrix_question_draft(  # noqa: PLR0913
        self,
        claim_id: AgentClaimIdPath,
        data: MatrixQuestionDraftSaveRequestSchema,
        identity: NamedDependency[AgentIdentity],
        metadata: NamedDependency[AgentRequestMetadata],
        use_case: FromDishka[MatrixAgentUseCase],
        policy: FromDishka[MatrixAgentPolicy],
    ) -> MatrixQuestionDraftSaveResponseSchema:
        result = await use_case.save_matrix_question_draft(
            identity=identity,
            params=data.to_domain_schema(claim_id=claim_id),
            completed_at=metadata.requested_at,
            policy=policy,
        )
        return MatrixQuestionDraftSaveResponseSchema.from_domain_schema(schema=result)

    @delete(
        "/matrix/question-claims/{claim_id:str}",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.RELEASE_MATRIX_QUESTION_CLAIM,
            "agent_scope": AgentScopeEnum.MATRIX_QUEUE_CLAIM,
            "agent_identity_mode": "business",
        },
    )
    async def release_matrix_question_claim(
        self,
        claim_id: AgentClaimIdPath,
        identity: NamedDependency[AgentIdentity],
        metadata: NamedDependency[AgentRequestMetadata],
        use_case: FromDishka[MatrixAgentUseCase],
    ) -> MatrixQuestionClaimReleaseResponseSchema:
        await use_case.release_matrix_question_claim(
            identity=identity,
            claim_id=claim_id,
            input_digest=metadata.input_digest,
            released_at=metadata.requested_at,
        )
        return MatrixQuestionClaimReleaseResponseSchema(released=True)

    @post(
        "/certificate-rotations",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
            "params": Provide(provide_agent_certificate_rotation_params, sync_to_thread=False),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.ROTATE_AGENT_CERTIFICATE,
            "agent_scope": None,
            "agent_identity_mode": "client",
        },
    )
    async def rotate_agent_certificate(
        self,
        identity: NamedDependency[AgentIdentity],
        params: NamedDependency[AgentCertificateRotationParams],
        use_case: FromDishka[AgentCertificateRotationUseCase],
        policy: FromDishka[AgentCertificatePolicy],
    ) -> AgentCertificateRotationResponseSchema:
        result = await use_case.rotate(identity=identity, params=params, policy=policy)
        return AgentCertificateRotationResponseSchema.from_domain_schema(schema=result)

    @post(
        "/certificate-rotations/{rotation_id:str}/confirm",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "identity": Provide(provide_agent_identity, sync_to_thread=False),
            "metadata": Provide(provide_agent_request_metadata, sync_to_thread=False),
            "params": Provide(
                provide_agent_certificate_rotation_confirm_params,
                sync_to_thread=False,
            ),
        },
        opt={
            "access_classification": constants.agent_access.access_classification,
            "agent_action": AgentActionEnum.CONFIRM_AGENT_CERTIFICATE_ROTATION,
            "agent_scope": None,
            "agent_identity_mode": "client",
        },
    )
    async def confirm_agent_certificate_rotation(
        self,
        identity: NamedDependency[AgentIdentity],
        params: NamedDependency[AgentCertificateRotationConfirmParams],
        use_case: FromDishka[AgentCertificateRotationUseCase],
    ) -> AgentCertificateRotationConfirmResponseSchema:
        result = await use_case.confirm(identity=identity, params=params)
        return AgentCertificateRotationConfirmResponseSchema.from_domain_schema(schema=result)


agent_api_router = DishkaRouter(
    path="",
    route_handlers=[AgentApiController],
    middleware=[
        DefineMiddleware(AgentTransactionMiddleware),
        DefineMiddleware(AgentAuthenticationMiddleware),
    ],
    exception_handlers=AGENT_ACCESS_EXCEPTION_HANDLERS,
    request_max_body_size=constants.agent_access.request_body_max_size_bytes,
    include_in_schema=False,
    opt={"exclude_from_auth": True},
)
