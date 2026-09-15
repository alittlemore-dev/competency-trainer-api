from datetime import datetime
from typing import cast

from dishka import AsyncContainer
from litestar.connection import ASGIConnection
from litestar.handlers import BaseRouteHandler
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult
from litestar.types import ASGIApp

from core.agent_access.enums import AgentScopeEnum
from core.agent_access.exceptions import (
    AgentAuthenticationError,
    AgentKnownAuthenticationError,
)
from core.agent_access.schemas import AgentClientAuthenticationParams, AgentIdentity
from core.agent_access.use_cases import AgentIdentityUseCase
from core.generators import HexUuidIdGenerator
from infra.config.constants import constants
from infra.config.loggers import logger
from infra.cryptography.agent_certificates import parse_agent_certificate_fingerprint

_OPERATION_ID_LENGTH = 32


class AgentAuthenticationMiddleware(AbstractAuthenticationMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(
            app=app,
            exclude=None,
            exclude_from_auth_key="agent_authentication_excluded",
            exclude_http_methods=None,
            scopes=None,
        )

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        state = connection.scope["state"]
        route_handler = connection.route_handler
        action = route_handler.opt["agent_action"]
        state["agent_action"] = action
        request_container = cast("AsyncContainer", state["dishka_container"])
        current_datetime = await request_container.get(datetime)
        id_generator = await request_container.get(HexUuidIdGenerator)
        request_id = id_generator.get_next()
        path_params = connection.scope["path_params"]
        path_operation_id = path_params.get("claim_id") or path_params.get("rotation_id")
        audit_request_id = (
            path_operation_id
            if isinstance(path_operation_id, str)
            and len(path_operation_id) == _OPERATION_ID_LENGTH
            and all(character in "0123456789abcdef" for character in path_operation_id)
            else request_id
        )
        state["agent_request_id"] = request_id
        state["agent_audit_request_id"] = audit_request_id
        state["agent_requested_at"] = current_datetime
        try:
            fingerprint = parse_agent_certificate_fingerprint(
                escaped_certificate_pem=connection.headers.get(
                    constants.agent_access.trusted_client_certificate_header,
                    "",
                ),
            )
        except AgentAuthenticationError:
            logger.warning(
                "agent_api_certificate_header_rejected",
                request_id=request_id,
                action=action.value,
            )
            raise
        use_case = await request_container.get(AgentIdentityUseCase)
        params = AgentClientAuthenticationParams(
            fingerprint_sha256=fingerprint,
            authenticated_at=current_datetime,
        )
        try:
            identity = (
                await use_case.authenticate_business_client(params=params)
                if route_handler.opt["agent_identity_mode"] == "business"
                else await use_case.authenticate_client(params=params)
            )
        except AgentKnownAuthenticationError as error:
            state["agent_client_id"] = error.agent_client_id
            state["agent_certificate_id"] = error.certificate_id
            logger.warning(
                "agent_api_known_certificate_rejected",
                request_id=request_id,
                action=action.value,
                agent_client_id=error.agent_client_id,
                certificate_id=error.certificate_id,
            )
            raise
        except AgentAuthenticationError:
            logger.warning(
                "agent_api_unknown_certificate_rejected",
                request_id=request_id,
                action=action.value,
            )
            raise
        state["agent_client_id"] = identity.agent_client_id
        state["agent_certificate_id"] = identity.certificate_id
        return AuthenticationResult(user=identity, auth=fingerprint)


def agent_scope_guard(connection: ASGIConnection, route_handler: BaseRouteHandler) -> None:
    required_scope = cast("AgentScopeEnum | None", route_handler.opt["agent_scope"])
    if required_scope is None:
        return
    identity = cast("AgentIdentity", connection.user)
    identity.ensure_scope(scope=required_scope)
