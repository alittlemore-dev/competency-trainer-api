from dishka import Provider, Scope, provide

from core.agent_access.clients import AgentCertificateIssuer
from core.agent_access.schemas import AgentAuditPolicy, AgentCertificatePolicy
from core.agent_access.storages import AgentAdminStorage, AgentAuditStorage
from core.agent_access.use_cases import AgentAdminUseCase, AgentAuditCleanupUseCase
from core.generators import HexUuidIdGenerator
from core.schemas import Secret
from infra.config.constants import constants
from infra.config.settings import AgentAccessSettings
from infra.cryptography.agent_certificates import CryptographyAgentCertificateIssuer


class AgentAdminProvider(Provider):
    def __init__(
        self,
        *,
        settings: AgentAccessSettings,
    ) -> None:
        super().__init__()
        self.settings = settings

    @provide(scope=Scope.APP)
    def provide_agent_certificate_policy(self) -> AgentCertificatePolicy:
        return AgentCertificatePolicy(
            lifetime_seconds=constants.agent_access.certificate_lifetime_seconds,
            rotation_window_seconds=constants.agent_access.certificate_rotation_window_seconds,
            normal_access_overlap_seconds=(
                constants.agent_access.certificate_rotation_normal_access_overlap_seconds
            ),
        )

    @provide(scope=Scope.APP)
    def provide_agent_audit_policy(self) -> AgentAuditPolicy:
        return AgentAuditPolicy(
            page_size_max=constants.agent_access.audit_page_max_size,
            retention_seconds=constants.agent_access.audit_retention_seconds,
        )

    @provide(scope=Scope.APP)
    def provide_agent_certificate_issuer(self) -> AgentCertificateIssuer:
        return CryptographyAgentCertificateIssuer(
            issuing_certificate_pem=self.settings.issuing_certificate_file.read_text(
                encoding="utf-8",
            ),
            issuing_private_key_pem=Secret(
                self.settings.issuing_private_key_file.read_text(encoding="utf-8"),
            ),
            certificate_chain_pem=self.settings.certificate_chain_file.read_text(
                encoding="utf-8",
            ),
        )

    @provide(scope=Scope.REQUEST)
    def provide_agent_admin_use_case(
        self,
        storage: AgentAdminStorage,
        certificate_issuer: AgentCertificateIssuer,
        id_generator: HexUuidIdGenerator,
    ) -> AgentAdminUseCase:
        return AgentAdminUseCase(
            storage=storage,
            certificate_issuer=certificate_issuer,
            id_generator=id_generator,
        )

    @provide(scope=Scope.REQUEST)
    def provide_agent_audit_cleanup_use_case(
        self,
        storage: AgentAuditStorage,
    ) -> AgentAuditCleanupUseCase:
        return AgentAuditCleanupUseCase(storage=storage)
