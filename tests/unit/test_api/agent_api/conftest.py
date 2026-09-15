from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, Mock
from urllib.parse import quote

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from dishka import Provider, Scope, make_async_container, provide
from dishka.integrations.litestar import LitestarProvider
from litestar import Litestar
from litestar.testing import TestClient

from core.agent_access.schemas import AgentCertificatePolicy, AgentIdentity, MatrixAgentPolicy
from core.agent_access.use_cases import (
    AgentAuditUseCase,
    AgentCertificateRotationUseCase,
    AgentIdentityUseCase,
    MatrixAgentUseCase,
)
from core.generators import HexUuidIdGenerator
from entrypoints.litestar.initializers.main import create_litestar_app
from infra.postgresql.transactions import DatabaseTransactionState

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)


class MockAgentApiProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.identity_use_case = AsyncMock(spec=AgentIdentityUseCase)
        self.matrix_use_case = AsyncMock(spec=MatrixAgentUseCase)
        self.rotation_use_case = AsyncMock(spec=AgentCertificateRotationUseCase)
        self.audit_use_case = AsyncMock(spec=AgentAuditUseCase)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.id_generator.get_next.return_value = "request-id"
        self.matrix_policy = MatrixAgentPolicy(
            claim_ttl_seconds=7200,
            minimum_resource_count=1,
            maximum_resource_count=3,
        )

    @provide(scope=Scope.REQUEST)
    def provide_audit_use_case(self) -> AgentAuditUseCase:
        return cast("AgentAuditUseCase", self.audit_use_case)

    @provide(scope=Scope.REQUEST)
    def provide_identity_use_case(self) -> AgentIdentityUseCase:
        return cast("AgentIdentityUseCase", self.identity_use_case)

    @provide(scope=Scope.REQUEST)
    def provide_matrix_use_case(self) -> MatrixAgentUseCase:
        return cast("MatrixAgentUseCase", self.matrix_use_case)

    @provide(scope=Scope.REQUEST)
    def provide_rotation_use_case(self) -> AgentCertificateRotationUseCase:
        return cast("AgentCertificateRotationUseCase", self.rotation_use_case)

    @provide(scope=Scope.REQUEST)
    def provide_now(self) -> datetime:
        return NOW

    @provide(scope=Scope.APP)
    def provide_id_generator(self) -> HexUuidIdGenerator:
        return cast("HexUuidIdGenerator", self.id_generator)

    @provide(scope=Scope.APP)
    def provide_agent_certificate_policy(self) -> AgentCertificatePolicy:
        return AgentCertificatePolicy(
            lifetime_seconds=7_776_000,
            rotation_window_seconds=1_209_600,
            normal_access_overlap_seconds=900,
        )

    @provide(scope=Scope.APP)
    def provide_matrix_agent_policy(self) -> MatrixAgentPolicy:
        return self.matrix_policy

    @provide(scope=Scope.REQUEST)
    def provide_transaction_state(self) -> DatabaseTransactionState:
        return DatabaseTransactionState(rollback_required=False)


@pytest.fixture
def agent_api_provider() -> MockAgentApiProvider:
    return MockAgentApiProvider()


@pytest.fixture
def agent_identity() -> AgentIdentity:
    return AgentIdentity(
        agent_client_id="a" * 32,
        agent_client_name="author",
        certificate_id="b" * 32,
        scopes=frozenset(),
    )


@pytest.fixture
def escaped_agent_certificate() -> str:
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "agent:test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(1)
        .not_valid_before(NOW - timedelta(days=1))
        .not_valid_after(NOW + timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    return quote(certificate.public_bytes(serialization.Encoding.PEM).decode(), safe="")


@pytest.fixture
def agent_api_app(
    agent_api_provider: MockAgentApiProvider,
) -> Litestar:
    container = make_async_container(LitestarProvider(), agent_api_provider)
    return create_litestar_app(
        lifespan=[],
        container=container,
        extra_plugins=[],
        extra_middlewares=[],
    )


@pytest.fixture
def agent_api_client(
    agent_api_app: Litestar,
    escaped_agent_certificate: str,
) -> Generator[TestClient]:
    with TestClient(agent_api_app) as client:
        client.headers["X-Agent-Client-Certificate"] = escaped_agent_certificate
        yield client
