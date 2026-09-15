import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest_asyncio
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from dishka import make_async_container
from litestar.testing import TestClient
from sqlalchemy import DDL, delete, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from core.agent_access.enums import AgentClientStatusEnum, AgentScopeEnum
from core.competency_matrix.schemas import CompetencyMatrixQuestionFingerprint
from entrypoints.litestar.initializers.main import create_litestar_app
from infra.config.constants import constants
from infra.ioc.registry import get_providers
from infra.postgresql.models import (
    AgentAuditEventModel,
    AgentCertificateModel,
    AgentClientModel,
    CompetencyMatrixItemModel,
    CompetencyMatrixSectionModel,
    CompetencyMatrixSheetModel,
    CompetencyMatrixSubsectionModel,
    ExternalResourceModel,
    MatrixQuestionClaimModel,
    MatrixQuestionDraftCompletionModel,
    QueuedQuestionModel,
)
from infra.postgresql.models.competency_matrix import ResourceToItemSecondaryModel

_DROP_FAILURE_TRIGGER = DDL(
    "DROP TRIGGER IF EXISTS test_fail_agent_success_audit_trigger "
    "ON agent_access__agent_audit_event_model",
)
_DROP_FAILURE_FUNCTION = DDL("DROP FUNCTION IF EXISTS test_fail_agent_success_audit()")
_CREATE_FAILURE_FUNCTION = DDL(
    """
    CREATE FUNCTION test_fail_agent_success_audit() RETURNS trigger AS $$
    BEGIN
        IF NEW.result::text = 'SUCCESS' THEN
            RAISE EXCEPTION 'test success audit failure';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
)
_CREATE_FAILURE_TRIGGER = DDL(
    """
    CREATE TRIGGER test_fail_agent_success_audit_trigger
    BEFORE INSERT ON agent_access__agent_audit_event_model
    FOR EACH ROW EXECUTE FUNCTION test_fail_agent_success_audit()
    """,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class FullStackAgentApiFixture:
    client: TestClient
    engine: AsyncEngine
    full_client_id: str
    full_certificate_id: str
    full_certificate_header: str
    limited_client_id: str
    limited_certificate_id: str
    limited_certificate_header: str
    expired_client_id: str
    expired_certificate_id: str
    expired_certificate_header: str
    subsection_id: str
    queue_item_ids: tuple[str, str]

    async def install_success_audit_failure(self) -> None:
        async with self.engine.begin() as connection:
            await connection.execute(_DROP_FAILURE_TRIGGER)
            await connection.execute(_DROP_FAILURE_FUNCTION)
            await connection.execute(_CREATE_FAILURE_FUNCTION)
            await connection.execute(_CREATE_FAILURE_TRIGGER)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentApiFixtureRowIds:
    client_ids: tuple[str, str, str]
    subsection_id: str
    sheet_id: str
    queue_item_ids: tuple[str, str]


@pytest_asyncio.fixture
async def full_stack_agent_api(
    session: AsyncSession,
    engine: AsyncEngine,
) -> AsyncGenerator[FullStackAgentApiFixture]:
    now = datetime.now(tz=UTC)
    issuing_key, issuing_certificate = _create_issuing_material(now=now)

    full_client_id = uuid.uuid4().hex
    limited_client_id = uuid.uuid4().hex
    expired_client_id = uuid.uuid4().hex
    full_certificate_id = uuid.uuid4().hex
    limited_certificate_id = uuid.uuid4().hex
    expired_certificate_id = uuid.uuid4().hex
    full_certificate = _create_client_certificate(
        issuing_key=issuing_key,
        issuing_certificate=issuing_certificate,
        client_id=full_client_id,
        valid_from=now - timedelta(days=1),
        expires_at=now + timedelta(days=7),
    )
    limited_certificate = _create_client_certificate(
        issuing_key=issuing_key,
        issuing_certificate=issuing_certificate,
        client_id=limited_client_id,
        valid_from=now - timedelta(days=1),
        expires_at=now + timedelta(days=7),
    )
    expired_certificate = _create_client_certificate(
        issuing_key=issuing_key,
        issuing_certificate=issuing_certificate,
        client_id=expired_client_id,
        valid_from=now - timedelta(days=7),
        expires_at=now - timedelta(days=1),
    )
    sheet_id = uuid.uuid4().hex
    section_id = uuid.uuid4().hex
    subsection_id = uuid.uuid4().hex
    first_queue_item_id = uuid.uuid4().hex
    second_queue_item_id = uuid.uuid4().hex
    fixture_key = uuid.uuid4().hex
    fixture_row_ids = AgentApiFixtureRowIds(
        client_ids=(full_client_id, limited_client_id, expired_client_id),
        subsection_id=subsection_id,
        sheet_id=sheet_id,
        queue_item_ids=(first_queue_item_id, second_queue_item_id),
    )
    session.add_all(
        [
            AgentClientModel(
                id=full_client_id,
                name=f"full-scope-{fixture_key}",
                status=AgentClientStatusEnum.ACTIVE,
                scopes=list(AgentScopeEnum),
                created_at=now,
                revoked_at=None,
            ),
            AgentClientModel(
                id=limited_client_id,
                name=f"limited-scope-{fixture_key}",
                status=AgentClientStatusEnum.ACTIVE,
                scopes=[],
                created_at=now,
                revoked_at=None,
            ),
            AgentClientModel(
                id=expired_client_id,
                name=f"expired-certificate-{fixture_key}",
                status=AgentClientStatusEnum.ACTIVE,
                scopes=[AgentScopeEnum.MATRIX_QUEUE_CLAIM],
                created_at=now - timedelta(days=7),
                revoked_at=None,
            ),
            _certificate_model(
                certificate_id=full_certificate_id,
                client_id=full_client_id,
                certificate=full_certificate,
                created_at=now,
            ),
            _certificate_model(
                certificate_id=limited_certificate_id,
                client_id=limited_client_id,
                certificate=limited_certificate,
                created_at=now,
            ),
            _certificate_model(
                certificate_id=expired_certificate_id,
                client_id=expired_client_id,
                certificate=expired_certificate,
                created_at=now - timedelta(days=7),
            ),
            CompetencyMatrixSheetModel(
                id=sheet_id,
                key=f"agent-api-{fixture_key}",
                name_ru="Интеграционный лист",
                name_en="Integration sheet",
                priority=1,
            ),
            CompetencyMatrixSectionModel(
                id=section_id,
                sheet_id=sheet_id,
                name_ru="Интеграционный раздел",
                name_en="Integration section",
                priority=1,
            ),
            CompetencyMatrixSubsectionModel(
                id=subsection_id,
                section_id=section_id,
                name_ru="Интеграционный подраздел",
                name_en="Integration subsection",
                priority=1,
            ),
            _queue_model(
                queue_item_id=first_queue_item_id,
                question="First full-stack agent question",
                created_at=now - timedelta(minutes=2),
            ),
            _queue_model(
                queue_item_id=second_queue_item_id,
                question="Second full-stack agent question",
                created_at=now - timedelta(minutes=1),
            ),
        ],
    )
    await session.commit()

    container = make_async_container(*get_providers())
    app = create_litestar_app(
        lifespan=[],
        container=container,
        extra_plugins=[],
        extra_middlewares=[],
    )
    try:
        with TestClient(app) as client:
            yield FullStackAgentApiFixture(
                client=client,
                engine=engine,
                full_client_id=full_client_id,
                full_certificate_id=full_certificate_id,
                full_certificate_header=_forwarded_certificate_header(full_certificate),
                limited_client_id=limited_client_id,
                limited_certificate_id=limited_certificate_id,
                limited_certificate_header=_forwarded_certificate_header(limited_certificate),
                expired_client_id=expired_client_id,
                expired_certificate_id=expired_certificate_id,
                expired_certificate_header=_forwarded_certificate_header(expired_certificate),
                subsection_id=subsection_id,
                queue_item_ids=(first_queue_item_id, second_queue_item_id),
            )
    finally:
        await session.rollback()
        async with engine.begin() as connection:
            await connection.execute(_DROP_FAILURE_TRIGGER)
            await connection.execute(_DROP_FAILURE_FUNCTION)
        await _clean_fixture_rows(session=session, ids=fixture_row_ids)


async def _clean_fixture_rows(*, session: AsyncSession, ids: AgentApiFixtureRowIds) -> None:
    resource_ids = list(
        await session.scalars(
            select(ResourceToItemSecondaryModel.resource_id)
            .join(
                CompetencyMatrixItemModel,
                CompetencyMatrixItemModel.id == ResourceToItemSecondaryModel.item_id,
            )
            .where(CompetencyMatrixItemModel.subsection_id == ids.subsection_id),
        ),
    )
    await session.execute(
        delete(AgentAuditEventModel).where(
            AgentAuditEventModel.agent_client_id.in_(ids.client_ids),
        ),
    )
    await session.execute(
        delete(MatrixQuestionDraftCompletionModel).where(
            MatrixQuestionDraftCompletionModel.agent_client_id.in_(ids.client_ids),
        ),
    )
    await session.execute(
        delete(MatrixQuestionClaimModel).where(
            MatrixQuestionClaimModel.agent_client_id.in_(ids.client_ids),
        ),
    )
    await session.execute(
        delete(QueuedQuestionModel).where(QueuedQuestionModel.id.in_(ids.queue_item_ids)),
    )
    await session.execute(
        delete(CompetencyMatrixItemModel).where(
            CompetencyMatrixItemModel.subsection_id == ids.subsection_id,
        ),
    )
    if resource_ids:
        await session.execute(
            delete(ExternalResourceModel).where(ExternalResourceModel.id.in_(resource_ids)),
        )
    await session.execute(
        delete(AgentCertificateModel).where(
            AgentCertificateModel.agent_client_id.in_(ids.client_ids),
        ),
    )
    await session.execute(
        delete(AgentClientModel).where(AgentClientModel.id.in_(ids.client_ids)),
    )
    await session.execute(
        delete(CompetencyMatrixSheetModel).where(CompetencyMatrixSheetModel.id == ids.sheet_id),
    )
    await session.commit()


def _create_issuing_material(
    *,
    now: datetime,
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    private_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Agent Integration CA")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=30))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )
    return private_key, certificate


def _create_client_certificate(
    *,
    issuing_key: ec.EllipticCurvePrivateKey,
    issuing_certificate: x509.Certificate,
    client_id: str,
    valid_from: datetime,
    expires_at: datetime,
) -> x509.Certificate:
    private_key = ec.generate_private_key(ec.SECP256R1())
    return (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"agent:{client_id}")]))
        .issuer_name(issuing_certificate.subject)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(expires_at)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=True,
        )
        .sign(issuing_key, hashes.SHA256())
    )


def _certificate_model(
    *,
    certificate_id: str,
    client_id: str,
    certificate: x509.Certificate,
    created_at: datetime,
) -> AgentCertificateModel:
    return AgentCertificateModel(
        id=certificate_id,
        agent_client_id=client_id,
        fingerprint_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
        serial_number=format(certificate.serial_number, "x"),
        certificate_pem=certificate.public_bytes(serialization.Encoding.PEM).decode(),
        valid_from=certificate.not_valid_before_utc,
        expires_at=certificate.not_valid_after_utc,
        created_at=created_at,
        revoked_at=None,
    )


def _queue_model(
    *,
    queue_item_id: str,
    question: str,
    created_at: datetime,
) -> QueuedQuestionModel:
    return QueuedQuestionModel(
        id=queue_item_id,
        question=question,
        question_fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
            question=question,
        ).digest,
        grade=None,
        sheet=None,
        section=None,
        subsection=None,
        suggested_by_username="integration-author",
        created_at=created_at,
    )


def _forwarded_certificate_header(certificate: x509.Certificate) -> str:
    pem = certificate.public_bytes(serialization.Encoding.PEM).decode()
    return quote(pem, safe="")


def agent_certificate_headers(*, value: str) -> dict[str, str]:
    return {constants.agent_access.trusted_client_certificate_header: value}
