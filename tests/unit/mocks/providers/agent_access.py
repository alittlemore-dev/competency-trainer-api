from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.agent_access.schemas import AgentAuditPolicy, AgentCertificatePolicy
from core.agent_access.use_cases import AgentAdminUseCase


class MockAgentAccessProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_agent_certificate_policy(self) -> AgentCertificatePolicy:
        return AgentCertificatePolicy(
            lifetime_seconds=7_776_000,
            rotation_window_seconds=1_209_600,
            normal_access_overlap_seconds=900,
        )

    @provide(scope=Scope.APP)
    async def provide_agent_audit_policy(self) -> AgentAuditPolicy:
        return AgentAuditPolicy(page_size_max=100, retention_seconds=31_536_000)

    @provide(scope=Scope.APP)
    async def provide_agent_admin_use_case(self) -> AgentAdminUseCase:
        return Mock(spec=AgentAdminUseCase)
