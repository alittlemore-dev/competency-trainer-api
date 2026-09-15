from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest

from core.agent_access.clients import AgentCertificateIssuer
from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.exceptions import (
    AgentAuthenticationError,
    AgentClientValidationError,
    AgentScopeDeniedError,
    MatrixQuestionDraftValidationError,
)
from core.agent_access.schemas import (
    AgentAuditEventCreateParams,
    AgentCertificate,
    AgentCertificateIssueParams,
    AgentCertificatePolicy,
    AgentCertificateRotation,
    AgentCertificateRotationParams,
    AgentCertificateRotationResult,
    AgentClient,
    AgentClientAuthenticationParams,
    AgentClientRegisterParams,
    AgentClientRegistrationResult,
    AgentClientRevokeParams,
    AgentCredential,
    AgentIdentity,
    IssuedAgentCertificate,
    MatrixAgentPolicy,
    MatrixAuthoringContext,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
    MatrixQuestionDraftResourceParams,
    MatrixQuestionDraftSaveParams,
    MatrixQuestionDraftSaveResult,
)
from core.agent_access.storages import (
    AgentAdminStorage,
    AgentCertificateRotationStorage,
    AgentIdentityStorage,
    MatrixAgentStorage,
)
from core.agent_access.use_cases import (
    AgentAdminUseCase,
    AgentCertificateRotationUseCase,
    AgentIdentityUseCase,
    MatrixAgentUseCase,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import (
    CompetencyMatrixResourceSearchParams,
    CompetencyMatrixStructure,
)
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.generators import HexUuidIdGenerator
from core.i18n.enums import LanguageEnum
from core.types import SearchName
from tests.test_cases import TestCase

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
FINGERPRINT = "a" * 64
INPUT_DIGEST = "b" * 64


class TestAgentIdentityUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=AgentIdentityStorage)
        self.use_case = AgentIdentityUseCase(storage=self.storage)
        self.client = AgentClient(
            id=self.factory.core.hex_id(1),
            name="desktop-codex",
            status=AgentClientStatusEnum.ACTIVE,
            scopes=frozenset(
                {
                    AgentScopeEnum.MATRIX_QUEUE_CLAIM,
                    AgentScopeEnum.MATRIX_DRAFT_CREATE,
                },
            ),
            created_at=NOW - timedelta(days=2),
            revoked_at=None,
        )
        self.certificate = AgentCertificate(
            id=self.factory.core.hex_id(2),
            agent_client_id=self.client.id,
            fingerprint_sha256=FINGERPRINT,
            serial_number="01",
            certificate_pem="-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
            valid_from=NOW - timedelta(days=1),
            expires_at=NOW + timedelta(days=89),
            created_at=NOW - timedelta(days=1),
            revoked_at=None,
        )

    @pytest.mark.parametrize(
        ("client_status", "certificate_revoked_at", "valid_from", "expires_at"),
        [
            (
                AgentClientStatusEnum.REVOKED,
                None,
                NOW - timedelta(days=1),
                NOW + timedelta(days=89),
            ),
            (
                AgentClientStatusEnum.ACTIVE,
                NOW - timedelta(minutes=1),
                NOW - timedelta(days=1),
                NOW + timedelta(days=89),
            ),
            (
                AgentClientStatusEnum.ACTIVE,
                None,
                NOW + timedelta(minutes=1),
                NOW + timedelta(days=90),
            ),
            (
                AgentClientStatusEnum.ACTIVE,
                None,
                NOW - timedelta(days=90),
                NOW,
            ),
        ],
    )
    async def test_authenticate_business_client_rejects_inactive_client_or_certificate(
        self,
        client_status: AgentClientStatusEnum,
        certificate_revoked_at: datetime | None,
        valid_from: datetime,
        expires_at: datetime,
    ) -> None:
        self.storage.get_credential_by_fingerprint.return_value = AgentCredential(
            client=replace(self.client, status=client_status),
            certificate=replace(
                self.certificate,
                revoked_at=certificate_revoked_at,
                valid_from=valid_from,
                expires_at=expires_at,
            ),
            normal_access_until=None,
        )

        with pytest.raises(AgentAuthenticationError):
            await self.use_case.authenticate_business_client(
                params=AgentClientAuthenticationParams(
                    fingerprint_sha256=FINGERPRINT,
                    authenticated_at=NOW,
                ),
            )

    async def test_authenticate_client_does_not_require_matrix_scope(self) -> None:
        self.storage.get_credential_by_fingerprint.return_value = AgentCredential(
            client=replace(self.client, scopes=frozenset()),
            certificate=self.certificate,
            normal_access_until=None,
        )

        identity = await self.use_case.authenticate_client(
            params=AgentClientAuthenticationParams(
                fingerprint_sha256=FINGERPRINT,
                authenticated_at=NOW,
            ),
        )

        assert identity.agent_client_id == self.client.id
        assert identity.certificate_id == self.certificate.id

    async def test_pending_rotation_overlap_blocks_business_but_allows_rotation_auth(self) -> None:
        self.storage.get_credential_by_fingerprint.return_value = AgentCredential(
            client=self.client,
            certificate=self.certificate,
            normal_access_until=NOW,
        )

        with pytest.raises(AgentAuthenticationError):
            await self.use_case.authenticate_business_client(
                params=AgentClientAuthenticationParams(
                    fingerprint_sha256=FINGERPRINT,
                    authenticated_at=NOW,
                ),
            )

        identity = await self.use_case.authenticate_client(
            params=AgentClientAuthenticationParams(
                fingerprint_sha256=FINGERPRINT,
                authenticated_at=NOW,
            ),
        )
        assert identity.certificate_id == self.certificate.id


class TestAgentCertificateRotationUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=AgentCertificateRotationStorage)
        self.issuer = Mock(spec=AgentCertificateIssuer)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.id_generator.get_next.return_value = self.factory.core.hex_id(12)
        self.identity = AgentIdentity(
            agent_client_id=self.factory.core.hex_id(10),
            agent_client_name="desktop-codex",
            certificate_id=self.factory.core.hex_id(11),
            scopes=frozenset(),
        )
        self.current_certificate = AgentCertificate(
            id=self.identity.certificate_id,
            agent_client_id=self.identity.agent_client_id,
            fingerprint_sha256=FINGERPRINT,
            serial_number="01",
            certificate_pem="-----BEGIN CERTIFICATE-----\ncurrent\n-----END CERTIFICATE-----",
            valid_from=NOW - timedelta(days=76),
            expires_at=NOW + timedelta(days=14),
            created_at=NOW - timedelta(days=76),
            revoked_at=None,
        )
        self.client = AgentClient(
            id=self.identity.agent_client_id,
            name=self.identity.agent_client_name,
            status=AgentClientStatusEnum.ACTIVE,
            scopes=frozenset(),
            created_at=NOW - timedelta(days=80),
            revoked_at=None,
        )
        self.storage.get_client_for_rotation.return_value = self.client
        self.storage.get_certificate_for_rotation.return_value = self.current_certificate
        self.storage.get_certificate_rotation.return_value = None
        self.storage.get_pending_certificate_rotation.return_value = None
        self.issuer.get_certificate_chain_pem.return_value = (
            "-----BEGIN CERTIFICATE-----\nchain\n-----END CERTIFICATE-----"
        )
        self.policy = AgentCertificatePolicy(
            lifetime_seconds=7_776_000,
            rotation_window_seconds=1_209_600,
            normal_access_overlap_seconds=900,
        )
        self.use_case = AgentCertificateRotationUseCase(
            storage=self.storage,
            certificate_issuer=self.issuer,
            id_generator=self.id_generator,
        )

    async def test_rotate_issues_certificate_for_authenticated_agent_identity(self) -> None:
        issued = IssuedAgentCertificate(
            certificate_pem="-----BEGIN CERTIFICATE-----\nrotated\n-----END CERTIFICATE-----",
            certificate_chain_pem="-----BEGIN CERTIFICATE-----\nchain\n-----END CERTIFICATE-----",
            fingerprint_sha256="c" * 64,
            serial_number="02",
            valid_from=NOW,
            expires_at=NOW + timedelta(days=90),
        )
        self.issuer.issue.return_value = issued

        result = await self.use_case.rotate(
            identity=self.identity,
            params=AgentCertificateRotationParams(
                rotation_id=self.factory.core.hex_id(13),
                csr_pem=(
                    "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----"
                ),
                rotated_at=NOW,
            ),
            policy=self.policy,
        )

        certificate = self.storage.create_certificate_rotation.await_args.kwargs["replacement"]
        assert certificate.agent_client_id == self.identity.agent_client_id
        assert certificate.id == self.factory.core.hex_id(12)
        assert result == AgentCertificateRotationResult(
            certificate=certificate,
            certificate_chain_pem=issued.certificate_chain_pem,
            replayed=False,
        )
        self.issuer.issue.assert_called_once_with(
            params=AgentCertificateIssueParams(
                agent_client_id=self.identity.agent_client_id,
                csr_pem=(
                    "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----"
                ),
                valid_from=NOW,
                expires_at=NOW + timedelta(days=90),
            )
        )
        self.storage.get_certificate_for_rotation.assert_awaited_once_with(
            certificate_id=self.identity.certificate_id,
            agent_client_id=self.identity.agent_client_id,
        )
        rotation = self.storage.create_certificate_rotation.await_args.kwargs["rotation"]
        assert rotation == AgentCertificateRotation(
            rotation_id=self.factory.core.hex_id(13),
            agent_client_id=self.identity.agent_client_id,
            current_certificate_id=self.identity.certificate_id,
            replacement_certificate_id=certificate.id,
            csr_digest=AgentCertificateRotationParams(
                rotation_id=self.factory.core.hex_id(13),
                csr_pem=(
                    "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----"
                ),
                rotated_at=NOW,
            ).csr_digest(),
            created_at=NOW,
            normal_access_until=NOW + timedelta(minutes=15),
            confirmed_at=None,
        )
        self.storage.create_certificate_rotation.assert_awaited_once_with(
            rotation=rotation,
            replacement=certificate,
        )

    async def test_rotate_rejects_request_before_rotation_window(self) -> None:
        self.storage.get_certificate_for_rotation.return_value = replace(
            self.current_certificate,
            expires_at=NOW + timedelta(days=14, seconds=1),
        )

        with pytest.raises(AgentClientValidationError):
            await self.use_case.rotate(
                identity=self.identity,
                params=AgentCertificateRotationParams(
                    rotation_id=self.factory.core.hex_id(13),
                    csr_pem=(
                        "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n"
                        "-----END CERTIFICATE REQUEST-----"
                    ),
                    rotated_at=NOW,
                ),
                policy=self.policy,
            )

        self.issuer.issue.assert_not_called()
        self.storage.create_certificate_rotation.assert_not_awaited()


class TestAgentAdminUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=AgentAdminStorage)
        self.issuer = Mock(spec=AgentCertificateIssuer)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.id_generator.get_next.side_effect = [
            self.factory.core.hex_id(10),
            self.factory.core.hex_id(11),
        ]
        self.certificate_policy = AgentCertificatePolicy(
            lifetime_seconds=7_776_000,
            rotation_window_seconds=1_209_600,
            normal_access_overlap_seconds=900,
        )
        self.use_case = AgentAdminUseCase(
            storage=self.storage,
            certificate_issuer=self.issuer,
            id_generator=self.id_generator,
        )
        self.storage.client_name_exists.return_value = False

    async def test_register_client_issues_scoped_client_auth_certificate(self) -> None:
        issued = IssuedAgentCertificate(
            certificate_pem="-----BEGIN CERTIFICATE-----\nissued\n-----END CERTIFICATE-----",
            certificate_chain_pem="-----BEGIN CERTIFICATE-----\nchain\n-----END CERTIFICATE-----",
            fingerprint_sha256=FINGERPRINT,
            serial_number="01",
            valid_from=NOW,
            expires_at=NOW + timedelta(days=90),
        )
        self.issuer.issue.return_value = issued
        params = AgentClientRegisterParams(
            name="desktop-codex",
            scopes=frozenset(
                {
                    AgentScopeEnum.MATRIX_QUEUE_CLAIM,
                    AgentScopeEnum.MATRIX_CONTEXT_READ,
                    AgentScopeEnum.MATRIX_RESOURCES_READ,
                    AgentScopeEnum.MATRIX_DRAFT_CREATE,
                },
            ),
            csr_pem="-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----",
            registered_at=NOW,
        )

        result = await self.use_case.register_client(
            params=params,
            policy=self.certificate_policy,
        )

        assert result == AgentClientRegistrationResult(
            client=self.storage.create_client.await_args.kwargs["client"],
            certificate=self.storage.create_certificate.await_args.kwargs["certificate"],
            certificate_chain_pem=issued.certificate_chain_pem,
        )
        client = self.storage.create_client.await_args.kwargs["client"]
        assert client.status == AgentClientStatusEnum.ACTIVE
        assert client.scopes == params.scopes
        assert client.created_at == NOW
        certificate = self.storage.create_certificate.await_args.kwargs["certificate"]
        assert certificate.agent_client_id == client.id
        assert certificate.fingerprint_sha256 == FINGERPRINT
        assert certificate.expires_at == NOW + timedelta(days=90)
        self.issuer.issue.assert_called_once()

    async def test_revoke_client_is_permanent_storage_operation(self) -> None:
        params = AgentClientRevokeParams(
            agent_client_id=self.factory.core.hex_id(10),
            revoked_at=NOW,
        )

        await self.use_case.revoke_client(params=params)

        self.storage.revoke_client.assert_awaited_once_with(params=params)


class TestMatrixAgentUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=MatrixAgentStorage)
        self.matrix_storage = Mock(spec=CompetencyMatrixStorage)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.id_generator.get_next.side_effect = [
            self.factory.core.hex_id(6),
            self.factory.core.hex_id(7),
        ]
        self.policy = MatrixAgentPolicy(
            claim_ttl_seconds=7200,
            minimum_resource_count=1,
            maximum_resource_count=3,
        )
        self.use_case = MatrixAgentUseCase(
            storage=self.storage,
            matrix_storage=self.matrix_storage,
            id_generator=self.id_generator,
        )
        self.identity = AgentIdentity(
            agent_client_id=self.factory.core.hex_id(1),
            agent_client_name="desktop-codex",
            certificate_id=self.factory.core.hex_id(2),
            scopes=frozenset(
                {
                    AgentScopeEnum.MATRIX_QUEUE_CLAIM,
                    AgentScopeEnum.MATRIX_CONTEXT_READ,
                    AgentScopeEnum.MATRIX_RESOURCES_READ,
                    AgentScopeEnum.MATRIX_DRAFT_CREATE,
                },
            ),
        )
        self.question = self.factory.core.queued_competency_matrix_question(
            question_id=3,
            created_at=NOW - timedelta(days=1),
        )
        self.claim = MatrixQuestionClaim(
            id=self.factory.core.hex_id(4),
            agent_client_id=self.identity.agent_client_id,
            question=self.question,
            claimed_at=NOW,
            expires_at=NOW + timedelta(hours=2),
        )
        self.params = MatrixQuestionDraftSaveParams(
            claim_id=self.claim.id,
            slug="pep-8",
            subsection_id=self.factory.core.hex_id(5),
            grade=GradeEnum.JUNIOR,
            interview_frequency=InterviewFrequencyEnum.OFTEN,
            question_ru="Что такое PEP 8?",
            question_en="What is PEP 8?",
            answer_ru="Руководство по стилю Python.",
            answer_en="The Python style guide.",
            interview_answer_explanation_ru="Назвать назначение и основные правила.",
            interview_answer_explanation_en="Explain its purpose and core rules.",
            resources=(
                MatrixQuestionDraftResourceParams(
                    name_ru="PEP 8",
                    name_en="PEP 8",
                    url="https://peps.python.org/pep-0008/",
                    context_ru="Официальная спецификация.",
                    context_en="The official specification.",
                ),
            ),
        )
        self.storage.get_matrix_question_draft_completion.side_effect = [None, None]
        self.storage.lock_matrix_question_claim.return_value = self.claim
        self.matrix_storage.get_item_structure_by_subsection_id.return_value = (
            self.factory.core.competency_matrix_item_structure(
                subsection_id=self.params.subsection_id,
            )
        )
        self.matrix_storage.create_competency_matrix_item.side_effect = lambda *, item: item

    async def test_get_authoring_context_returns_structure_enums_and_limits(self) -> None:
        structure = CompetencyMatrixStructure(sheets=[])
        self.matrix_storage.list_structure.return_value = structure

        context = await self.use_case.get_matrix_authoring_context(
            identity=self.identity,
            request_id="request-1",
            input_digest=INPUT_DIGEST,
            requested_at=NOW,
            policy=self.policy,
        )

        assert context == MatrixAuthoringContext(
            structure=structure,
            grades=tuple(GradeEnum),
            interview_frequencies=tuple(InterviewFrequencyEnum),
            minimum_resource_count=1,
            maximum_resource_count=3,
        )
        self.storage.create_audit_event.assert_awaited_once_with(
            params=AgentAuditEventCreateParams(
                agent_client_id=self.identity.agent_client_id,
                certificate_id=self.identity.certificate_id,
                action=AgentActionEnum.GET_MATRIX_AUTHORING_CONTEXT,
                queue_item_id=None,
                matrix_item_id=None,
                request_id="request-1",
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=INPUT_DIGEST,
                created_at=NOW,
            ),
        )

    async def test_search_resources_reuses_existing_matrix_resource_search(self) -> None:
        params = CompetencyMatrixResourceSearchParams(
            search_name=SearchName(" PEP "),
            limit=10,
            language=LanguageEnum.RU,
        )
        expected = self.factory.core.external_resources()
        self.matrix_storage.search_competency_matrix_resources.return_value = expected

        resources = await self.use_case.search_matrix_resources(
            identity=self.identity,
            params=params,
            request_id="request-2",
            input_digest=INPUT_DIGEST,
            requested_at=NOW,
        )

        assert resources == expected
        self.matrix_storage.search_competency_matrix_resources.assert_awaited_once_with(
            search_name="pep",
            limit=10,
            language=LanguageEnum.RU,
        )
        self.storage.create_audit_event.assert_awaited_once_with(
            params=AgentAuditEventCreateParams(
                agent_client_id=self.identity.agent_client_id,
                certificate_id=self.identity.certificate_id,
                action=AgentActionEnum.SEARCH_MATRIX_RESOURCES,
                queue_item_id=None,
                matrix_item_id=None,
                request_id="request-2",
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=INPUT_DIGEST,
                created_at=NOW,
            ),
        )

    async def test_claim_next_question_uses_bounded_two_hour_lease(self) -> None:
        self.storage.claim_next_matrix_question.return_value = self.claim

        result = await self.use_case.claim_next_matrix_question(
            identity=self.identity,
            claimed_at=NOW,
            input_digest=INPUT_DIGEST,
            policy=self.policy,
        )

        assert result == self.claim
        self.storage.claim_next_matrix_question.assert_awaited_once_with(
            agent_client_id=self.identity.agent_client_id,
            claimed_at=NOW,
            expires_at=NOW + timedelta(hours=2),
        )
        self.storage.create_audit_event.assert_awaited_once_with(
            params=AgentAuditEventCreateParams(
                agent_client_id=self.identity.agent_client_id,
                certificate_id=self.identity.certificate_id,
                action=AgentActionEnum.CLAIM_NEXT_MATRIX_QUESTION,
                queue_item_id=self.question.id,
                matrix_item_id=None,
                request_id=self.claim.id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=INPUT_DIGEST,
                created_at=NOW,
            ),
        )

    async def test_claim_next_question_requires_queue_claim_scope(self) -> None:
        identity = replace(
            self.identity,
            scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
        )

        with pytest.raises(AgentScopeDeniedError):
            await self.use_case.claim_next_matrix_question(
                identity=identity,
                claimed_at=NOW,
                input_digest=INPUT_DIGEST,
                policy=self.policy,
            )

        self.storage.claim_next_matrix_question.assert_not_awaited()

    async def test_release_returns_question_to_queue_and_writes_audit(self) -> None:
        self.storage.release_matrix_question_claim.return_value = self.question.id

        await self.use_case.release_matrix_question_claim(
            identity=self.identity,
            claim_id=self.claim.id,
            input_digest=INPUT_DIGEST,
            released_at=NOW,
        )

        self.storage.create_audit_event.assert_awaited_once_with(
            params=AgentAuditEventCreateParams(
                agent_client_id=self.identity.agent_client_id,
                certificate_id=self.identity.certificate_id,
                action=AgentActionEnum.RELEASE_MATRIX_QUESTION_CLAIM,
                queue_item_id=self.question.id,
                matrix_item_id=None,
                request_id=self.claim.id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=INPUT_DIGEST,
                created_at=NOW,
            ),
        )

    async def test_save_completes_claim_atomically_as_draft(self) -> None:
        expected = MatrixQuestionDraftSaveResult(
            item_id=self.factory.core.hex_id(6),
            replayed=False,
        )

        result = await self.use_case.save_matrix_question_draft(
            identity=self.identity,
            params=self.params,
            completed_at=NOW,
            policy=self.policy,
        )

        assert result == expected
        completion = self.storage.create_matrix_question_draft_completion.await_args.kwargs[
            "completion"
        ]
        assert completion.input_digest == self.params.canonical_digest()
        self.storage.consume_matrix_question_claim.assert_awaited_once_with(
            agent_client_id=self.identity.agent_client_id,
            claim_id=self.claim.id,
            queue_item_id=self.question.id,
        )

    async def test_save_returns_storage_idempotency_replay(self) -> None:
        completion = MatrixQuestionDraftCompletion(
            claim_id=self.claim.id,
            agent_client_id=self.identity.agent_client_id,
            queue_item_id=self.question.id,
            matrix_item_id=self.factory.core.hex_id(6),
            input_digest=self.params.canonical_digest(),
            completed_at=NOW,
        )
        self.storage.get_matrix_question_draft_completion.side_effect = None
        self.storage.get_matrix_question_draft_completion.return_value = completion

        result = await self.use_case.save_matrix_question_draft(
            identity=self.identity,
            params=self.params,
            completed_at=NOW,
            policy=self.policy,
        )

        assert result == MatrixQuestionDraftSaveResult(
            item_id=completion.matrix_item_id,
            replayed=True,
        )
        self.storage.lock_matrix_question_claim.assert_not_awaited()

    @pytest.mark.parametrize(
        "resources",
        [
            (),
            tuple(
                MatrixQuestionDraftResourceParams(
                    name_ru=f"Ресурс {index}",
                    name_en=f"Resource {index}",
                    url=f"https://example.com/{index}",
                    context_ru="Контекст",
                    context_en="Context",
                )
                for index in range(4)
            ),
        ],
    )
    async def test_save_rejects_resource_count_outside_closed_contract(
        self,
        resources: tuple[MatrixQuestionDraftResourceParams, ...],
    ) -> None:
        with pytest.raises(MatrixQuestionDraftValidationError):
            await self.use_case.save_matrix_question_draft(
                identity=self.identity,
                params=replace(self.params, resources=resources),
                completed_at=NOW,
                policy=self.policy,
            )

        self.storage.get_matrix_question_draft_completion.assert_not_awaited()

    @pytest.mark.parametrize(
        "url",
        [
            "http://example.com/resource",
            "https://user:password@example.com/resource",
            "https://127.0.0.1/resource",
            "https://[::1]/resource",
        ],
    )
    async def test_save_rejects_non_https_credentials_and_ip_literal_urls(
        self,
        url: str,
    ) -> None:
        original_resource = self.params.resources[0]
        assert isinstance(original_resource, MatrixQuestionDraftResourceParams)
        resource = replace(original_resource, url=url)

        with pytest.raises(MatrixQuestionDraftValidationError):
            await self.use_case.save_matrix_question_draft(
                identity=self.identity,
                params=replace(self.params, resources=(resource,)),
                completed_at=NOW,
                policy=self.policy,
            )

        self.storage.get_matrix_question_draft_completion.assert_not_awaited()

    async def test_save_storage_failure_does_not_trigger_partial_cleanup(self) -> None:
        self.matrix_storage.create_competency_matrix_item.side_effect = RuntimeError("write failed")

        with pytest.raises(RuntimeError, match="write failed"):
            await self.use_case.save_matrix_question_draft(
                identity=self.identity,
                params=self.params,
                completed_at=NOW,
                policy=self.policy,
            )

        self.storage.release_matrix_question_claim.assert_not_awaited()
        self.storage.consume_matrix_question_claim.assert_not_awaited()
