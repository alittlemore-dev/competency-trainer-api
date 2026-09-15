from dataclasses import dataclass

import httpx

from core.agent_access.schemas import LocalAgentCredentialRotationPolicy
from core.agent_access.use_cases import (
    AgentBridgeUseCase,
    AutomaticAgentCredentialRotationUseCase,
)
from core.generators import HexUuidIdGenerator, generate_uuid4_hex
from entrypoints.agent_bridge.server import AgentBridgeServer
from infra.config.agent_access import (
    AgentBridgeSettings,
    DesktopAgentBridgeSettings,
)
from infra.config.constants import constants
from infra.cryptography.agent_credentials import (
    AgentCredentialPairProvider,
    DesktopAgentCredentialStore,
    ExternalAgentCredentialStore,
)
from infra.http.agent_api import AgentApiHttpClient


@dataclass(frozen=True, slots=True, kw_only=True)
class AutomaticAgentCredentialRotationRuntime:
    use_case: AutomaticAgentCredentialRotationUseCase
    policy: LocalAgentCredentialRotationPolicy


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentBridgeRuntime:
    server: AgentBridgeServer
    automatic_rotation: AutomaticAgentCredentialRotationRuntime | None


def compose_agent_bridge_runtime(
    *,
    settings: AgentBridgeSettings,
    transport: httpx.AsyncBaseTransport | None,
) -> AgentBridgeRuntime:
    if isinstance(settings, DesktopAgentBridgeSettings):
        credential_provider: AgentCredentialPairProvider = DesktopAgentCredentialStore(
            credential_directory=settings.credential_directory,
            directory_mode=constants.agent_access.desktop_directory_mode,
            private_key_mode=constants.agent_access.desktop_private_key_mode,
            pending_file_mode=constants.agent_access.desktop_pending_file_mode,
            csr_pem_max_length=constants.agent_access.csr_pem_max_length,
        )
    else:
        credential_provider = ExternalAgentCredentialStore(
            certificate_file=settings.certificate_file,
            private_key_file=settings.private_key_file,
            private_key_mode=constants.agent_access.desktop_private_key_mode,
        )
    client = AgentApiHttpClient(
        settings=settings,
        credential_provider=credential_provider,
        transport=transport,
    )
    bridge_use_case = AgentBridgeUseCase(client=client)
    automatic_rotation = None
    if isinstance(credential_provider, DesktopAgentCredentialStore):
        automatic_rotation = AutomaticAgentCredentialRotationRuntime(
            use_case=AutomaticAgentCredentialRotationUseCase(
                storage=credential_provider,
                client=client,
                id_generator=HexUuidIdGenerator(generator=generate_uuid4_hex),
            ),
            policy=LocalAgentCredentialRotationPolicy(
                rotation_window_seconds=(
                    constants.agent_access.certificate_rotation_window_seconds
                ),
            ),
        )
    return AgentBridgeRuntime(
        server=AgentBridgeServer(use_case=bridge_use_case),
        automatic_rotation=automatic_rotation,
    )
