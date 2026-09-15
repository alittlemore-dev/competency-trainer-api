from datetime import datetime
from typing import Annotated

from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, get, post, status_codes
from litestar.di import NamedDependency, Provide

from core.agent_access.schemas import (
    AgentAuditEventPageParams,
    AgentAuditPolicy,
    AgentCertificatePolicy,
    AgentClientRevokeParams,
)
from core.agent_access.use_cases import AgentAdminUseCase
from entrypoints.litestar.api.agent_clients.dependencies import (
    provide_agent_audit_event_page_params,
)
from entrypoints.litestar.api.agent_clients.schemas import (
    AgentAuditEventsResponseSchema,
    AgentClientRegisterRequestSchema,
    AgentClientRegistrationResponseSchema,
    AgentClientsResponseSchema,
)
from entrypoints.litestar.api.parameters import AgentClientIdPath, api_json_body
from entrypoints.litestar.guards import owner_guard


class AdminAgentClientsApiController(Controller):
    path = "/agent-clients"
    tags = ["admin agent clients"]
    guards = [owner_guard]

    @get(
        "",
        description="List agent clients and their public certificate metadata.",
        name="admin-agent-clients-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_clients(
        self,
        use_case: FromDishka[AgentAdminUseCase],
    ) -> AgentClientsResponseSchema:
        clients = await use_case.list_client_details()
        return AgentClientsResponseSchema.from_domain_schema(schemas=clients)

    @post(
        "",
        description="Register an agent client from a locally generated CSR.",
        name="admin-agent-client-register-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def register_client(
        self,
        data: Annotated[
            AgentClientRegisterRequestSchema,
            api_json_body(
                title="Agent client registration request",
                description="Agent name, scopes and PKCS#10 CSR; never a private key.",
                examples=(
                    {
                        "name": "desktop-codex",
                        "scopes": ["matrix.queue.claim", "matrix.draft.create"],
                        "csrPem": "-----BEGIN CERTIFICATE REQUEST-----...",
                    },
                ),
            ),
        ],
        current_datetime: FromDishka[datetime],
        use_case: FromDishka[AgentAdminUseCase],
        policy: FromDishka[AgentCertificatePolicy],
    ) -> AgentClientRegistrationResponseSchema:
        result = await use_case.register_client(
            params=data.to_domain_schema(registered_at=current_datetime),
            policy=policy,
        )
        return AgentClientRegistrationResponseSchema.from_domain_schema(schema=result)

    @post(
        "/{client_id:str}/revoke",
        description="Permanently revoke an agent client and all of its certificates.",
        name="admin-agent-client-revoke-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def revoke_client(
        self,
        client_id: AgentClientIdPath,
        current_datetime: FromDishka[datetime],
        use_case: FromDishka[AgentAdminUseCase],
    ) -> None:
        await use_case.revoke_client(
            params=AgentClientRevokeParams(
                agent_client_id=client_id,
                revoked_at=current_datetime,
            ),
        )

    @get(
        "/{client_id:str}/audit",
        description="List privacy-safe audit metadata for an agent client.",
        name="admin-agent-client-audit-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        dependencies={
            "params": Provide(
                provide_agent_audit_event_page_params,
                sync_to_thread=False,
            ),
        },
    )
    async def list_audit_events(
        self,
        params: NamedDependency[AgentAuditEventPageParams],
        current_datetime: FromDishka[datetime],
        use_case: FromDishka[AgentAdminUseCase],
        policy: FromDishka[AgentAuditPolicy],
    ) -> AgentAuditEventsResponseSchema:
        page = await use_case.list_audit_events(
            params=params,
            requested_at=current_datetime,
            policy=policy,
        )
        return AgentAuditEventsResponseSchema.from_domain_schema(schema=page)


admin_router = DishkaRouter("", route_handlers=[AdminAgentClientsApiController])
