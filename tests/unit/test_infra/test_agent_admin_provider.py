from dishka import make_async_container

from core.agent_access.schemas import AgentAuditPolicy
from core.agent_access.storages import (
    AgentAdminStorage,
    AgentAuditStorage,
    AgentCertificateRotationStorage,
    AgentIdentityStorage,
    MatrixAgentStorage,
)
from core.agent_access.use_cases import AgentAuditCleanupUseCase
from infra.config.constants import constants
from infra.ioc.registry import get_providers
from infra.postgresql.storages.agent_access import AgentAccessDatabaseStorage


async def test_main_container_resolves_agent_audit_cleanup_use_case() -> None:
    container = make_async_container(*get_providers())
    try:
        async with container() as request_container:
            use_case = await request_container.get(AgentAuditCleanupUseCase)
            storage = await request_container.get(AgentAuditStorage)
            policy = await request_container.get(AgentAuditPolicy)

            assert use_case.storage is storage
            assert policy.retention_seconds == constants.agent_access.audit_retention_seconds
    finally:
        await container.close()


async def test_agent_storage_interfaces_alias_one_request_storage_instance() -> None:
    container = make_async_container(*get_providers())
    try:
        async with container() as request_container:
            storage = await request_container.get(AgentAccessDatabaseStorage)

            assert await request_container.get(AgentAdminStorage) is storage
            assert await request_container.get(AgentAuditStorage) is storage
            assert await request_container.get(AgentIdentityStorage) is storage
            assert await request_container.get(AgentCertificateRotationStorage) is storage
            assert await request_container.get(MatrixAgentStorage) is storage
    finally:
        await container.close()
