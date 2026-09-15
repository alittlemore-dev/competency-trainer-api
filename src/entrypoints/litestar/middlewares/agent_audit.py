import hashlib
from typing import cast

from dishka import AsyncContainer
from litestar.enums import ScopeType
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_500_INTERNAL_SERVER_ERROR
from litestar.types import ASGIApp, Message, Receive, ReceiveMessage, Scope, Send

from core.agent_access.enums import AgentAuditResultEnum
from core.agent_access.schemas import AgentAuditEventCreateParams
from core.agent_access.use_cases import AgentAuditUseCase
from infra.config.constants import constants
from infra.config.loggers import log_sanitized_exception


class AgentOutcomeAuditMiddleware:
    def __init__(self, *, app: ASGIApp, container: AsyncContainer) -> None:
        self.app = app
        self.container = container

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        prefix = constants.agent_access.api_path_prefix
        if scope["type"] != ScopeType.HTTP or not (path == prefix or path.startswith(f"{prefix}/")):
            await self.app(scope, receive, send)
            return
        state = scope["state"]
        input_hasher = hashlib.sha256()
        input_hasher.update(scope["query_string"])
        state["agent_input_hasher"] = input_hasher
        response_status = 500

        async def audit_receive() -> ReceiveMessage:
            message = await receive()
            body = message.get("body")
            if isinstance(body, bytes):
                input_hasher.update(body)
            return message

        async def audit_send(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = message["status"]
            await send(message)

        await self.app(scope, audit_receive, audit_send)
        action = state.get("agent_action")
        agent_client_id = state.get("agent_client_id")
        certificate_id = state.get("agent_certificate_id")
        if (
            response_status < HTTP_400_BAD_REQUEST
            or action is None
            or not isinstance(agent_client_id, str)
            or not isinstance(certificate_id, str)
        ):
            return
        audit_event = AgentAuditEventCreateParams(
            agent_client_id=agent_client_id,
            certificate_id=certificate_id,
            action=action,
            queue_item_id=None,
            matrix_item_id=None,
            request_id=cast("str", state["agent_audit_request_id"]),
            result=(
                AgentAuditResultEnum.REJECTED
                if response_status < HTTP_500_INTERNAL_SERVER_ERROR
                else AgentAuditResultEnum.FAILED
            ),
            input_digest=input_hasher.hexdigest(),
            created_at=state["agent_requested_at"],
        )
        try:
            async with self.container() as audit_container:
                use_case = await audit_container.get(AgentAuditUseCase)
                await use_case.record(params=audit_event)
        except Exception as error:  # noqa: BLE001
            log_sanitized_exception(
                event="agent_api_failure_audit_write_failed",
                error=error,
                request_id=state["agent_request_id"],
                action=action.value,
                agent_client_id=agent_client_id,
                certificate_id=certificate_id,
            )
