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
    AgentAuditPaginationError,
    AgentAuthenticationError,
    AgentCertificateRotationConfirmationError,
    AgentCertificateRotationConflictError,
    AgentClientNameConflictError,
    AgentIdempotencyConflictError,
    AgentScopeDeniedError,
    MatrixQuestionClaimNotFoundError,
    MatrixQuestionDraftValidationError,
)
from core.agent_access.schemas import (
    AgentAuditCursor,
    AgentAuditEvent,
    AgentAuditEventPage,
    AgentAuditEventPageParams,
    AgentAuditPolicy,
    AgentCertificate,
    AgentCertificatePolicy,
    AgentCertificateRotation,
    AgentCertificateRotationConfirmParams,
    AgentCertificateRotationParams,
    AgentClient,
    AgentClientRegisterParams,
    AgentIdentity,
    ExistingMatrixQuestionDraftResourceParams,
    MatrixAgentPolicy,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
    MatrixQuestionDraftResourceParams,
    MatrixQuestionDraftSaveParams,
)
from core.agent_access.storages import (
    AgentAdminStorage,
    AgentCertificateRotationStorage,
    MatrixAgentStorage,
)
from core.agent_access.use_cases import (
    AgentAdminUseCase,
    AgentCertificateRotationUseCase,
    MatrixAgentUseCase,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import CompetencyMatrixItemStructure
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.enums import PublishStatusEnum
from core.generators import HexUuidIdGenerator
from tests.test_cases import TestCase

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
CSR_PEM = "-----BEGIN CERTIFICATE REQUEST-----\ncsr\n-----END CERTIFICATE REQUEST-----"


class TestMatrixQuestionDraftCompletionPolicy(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=MatrixAgentStorage)
        self.matrix_storage = Mock(spec=CompetencyMatrixStorage)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.item_id = self.factory.core.hex_id(20)
        self.resource_id = self.factory.core.hex_id(21)
        self.id_generator.get_next.side_effect = [self.item_id, self.resource_id]
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
            scopes=frozenset({AgentScopeEnum.MATRIX_DRAFT_CREATE}),
        )
        self.claim = MatrixQuestionClaim(
            id=self.factory.core.hex_id(3),
            agent_client_id=self.identity.agent_client_id,
            question=self.factory.core.queued_competency_matrix_question(
                question_id=4,
                created_at=NOW - timedelta(days=1),
            ),
            claimed_at=NOW - timedelta(minutes=1),
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
        self.matrix_storage.create_competency_matrix_item.side_effect = lambda *, item: item
        self.matrix_storage.get_item_structure_by_subsection_id.return_value = (
            CompetencyMatrixItemStructure(
                sheet_id=self.factory.core.hex_id(6),
                sheet_key="python",
                sheet_ru="Python",
                sheet_en="Python",
                section_id=self.factory.core.hex_id(7),
                section_ru="Стандарты",
                section_en="Standards",
                subsection_id=self.params.subsection_id,
                subsection_ru="Стиль",
                subsection_en="Style",
            )
        )

    async def test_save_constructs_server_forced_draft_and_canonical_digest(self) -> None:
        result = await self.use_case.save_matrix_question_draft(
            identity=self.identity,
            params=self.params,
            completed_at=NOW,
            policy=self.policy,
        )

        item = self.matrix_storage.create_competency_matrix_item.await_args.kwargs["item"]
        assert item.publish_status == PublishStatusEnum.DRAFT
        assert item.published_at is None
        assert item.id == self.item_id
        assert item.resources.values[0].id == self.resource_id
        completion = self.storage.create_matrix_question_draft_completion.await_args.kwargs[
            "completion"
        ]
        assert completion.input_digest == self.params.canonical_digest()
        assert result.item_id == self.item_id
        assert result.replayed is False
        self.storage.create_audit_event.assert_awaited_once()
        assert (
            self.storage.create_audit_event.await_args.kwargs["params"].action
            == AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT
        )

    async def test_save_replays_same_claim_and_same_canonical_params(self) -> None:
        completion = MatrixQuestionDraftCompletion(
            claim_id=self.claim.id,
            agent_client_id=self.identity.agent_client_id,
            queue_item_id=self.claim.question.id,
            matrix_item_id=self.item_id,
            input_digest=self.params.canonical_digest(),
            completed_at=NOW - timedelta(minutes=1),
        )
        self.storage.get_matrix_question_draft_completion.side_effect = None
        self.storage.get_matrix_question_draft_completion.return_value = completion

        result = await self.use_case.save_matrix_question_draft(
            identity=self.identity,
            params=self.params,
            completed_at=NOW,
            policy=self.policy,
        )

        assert result.item_id == self.item_id
        assert result.replayed is True
        self.storage.lock_matrix_question_claim.assert_not_awaited()
        self.matrix_storage.create_competency_matrix_item.assert_not_awaited()

    async def test_save_rejects_same_claim_with_changed_canonical_field(self) -> None:
        completion = MatrixQuestionDraftCompletion(
            claim_id=self.claim.id,
            agent_client_id=self.identity.agent_client_id,
            queue_item_id=self.claim.question.id,
            matrix_item_id=self.item_id,
            input_digest=self.params.canonical_digest(),
            completed_at=NOW - timedelta(minutes=1),
        )
        self.storage.get_matrix_question_draft_completion.side_effect = None
        self.storage.get_matrix_question_draft_completion.return_value = completion

        with pytest.raises(AgentIdempotencyConflictError):
            await self.use_case.save_matrix_question_draft(
                identity=self.identity,
                params=replace(self.params, answer_en="Changed answer"),
                completed_at=NOW,
                policy=self.policy,
            )

        self.storage.lock_matrix_question_claim.assert_not_awaited()
        self.matrix_storage.create_competency_matrix_item.assert_not_awaited()

    async def test_save_replays_completion_created_while_waiting_for_claim_lock(self) -> None:
        completion = MatrixQuestionDraftCompletion(
            claim_id=self.claim.id,
            agent_client_id=self.identity.agent_client_id,
            queue_item_id=self.claim.question.id,
            matrix_item_id=self.item_id,
            input_digest=self.params.canonical_digest(),
            completed_at=NOW - timedelta(seconds=1),
        )
        self.storage.get_matrix_question_draft_completion.side_effect = [None, completion]
        self.storage.lock_matrix_question_claim.return_value = None

        result = await self.use_case.save_matrix_question_draft(
            identity=self.identity,
            params=self.params,
            completed_at=NOW,
            policy=self.policy,
        )

        assert result.item_id == completion.matrix_item_id
        assert result.replayed is True
        self.matrix_storage.create_competency_matrix_item.assert_not_awaited()

    async def test_save_rejects_expired_locked_claim_before_matrix_mutation(self) -> None:
        self.storage.lock_matrix_question_claim.return_value = replace(
            self.claim,
            expires_at=NOW,
        )

        with pytest.raises(MatrixQuestionClaimNotFoundError):
            await self.use_case.save_matrix_question_draft(
                identity=self.identity,
                params=self.params,
                completed_at=NOW,
                policy=self.policy,
            )

        self.matrix_storage.create_competency_matrix_item.assert_not_awaited()

    async def test_save_rejects_duplicate_existing_resource_before_storage_mutation(self) -> None:
        duplicated = ExistingMatrixQuestionDraftResourceParams(
            resource_id=self.factory.core.hex_id(30),
            context_ru="Контекст",
            context_en="Context",
        )

        with pytest.raises(MatrixQuestionDraftValidationError):
            await self.use_case.save_matrix_question_draft(
                identity=self.identity,
                params=replace(self.params, resources=(duplicated, duplicated)),
                completed_at=NOW,
                policy=self.policy,
            )

        self.storage.get_matrix_question_draft_completion.assert_not_awaited()

    async def test_save_rejects_wrong_scope_before_storage_mutation(self) -> None:
        with pytest.raises(AgentScopeDeniedError):
            await self.use_case.save_matrix_question_draft(
                identity=replace(self.identity, scopes=frozenset()),
                params=self.params,
                completed_at=NOW,
                policy=self.policy,
            )

        self.storage.get_matrix_question_draft_completion.assert_not_awaited()


class TestAgentCertificateRotationPolicy(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=AgentCertificateRotationStorage)
        self.issuer = Mock(spec=AgentCertificateIssuer)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.identity = AgentIdentity(
            agent_client_id=self.factory.core.hex_id(40),
            agent_client_name="desktop-codex",
            certificate_id=self.factory.core.hex_id(41),
            scopes=frozenset(),
        )
        self.client = AgentClient(
            id=self.identity.agent_client_id,
            name=self.identity.agent_client_name,
            status=AgentClientStatusEnum.ACTIVE,
            scopes=frozenset(),
            created_at=NOW - timedelta(days=80),
            revoked_at=None,
        )
        self.current_certificate = AgentCertificate(
            id=self.identity.certificate_id,
            agent_client_id=self.identity.agent_client_id,
            fingerprint_sha256="a" * 64,
            serial_number="01",
            certificate_pem="current certificate",
            valid_from=NOW - timedelta(days=76),
            expires_at=NOW + timedelta(days=14),
            created_at=NOW - timedelta(days=76),
            revoked_at=None,
        )
        self.replacement_certificate = replace(
            self.current_certificate,
            id=self.factory.core.hex_id(42),
            fingerprint_sha256="b" * 64,
            serial_number="02",
            certificate_pem="replacement certificate",
            valid_from=NOW,
            expires_at=NOW + timedelta(days=90),
            created_at=NOW,
        )
        self.params = AgentCertificateRotationParams(
            rotation_id=self.factory.core.hex_id(43),
            csr_pem=CSR_PEM,
            rotated_at=NOW,
        )
        self.rotation = AgentCertificateRotation(
            rotation_id=self.params.rotation_id,
            agent_client_id=self.identity.agent_client_id,
            current_certificate_id=self.current_certificate.id,
            replacement_certificate_id=self.replacement_certificate.id,
            csr_digest=self.params.csr_digest(),
            created_at=NOW,
            normal_access_until=NOW + timedelta(minutes=15),
            confirmed_at=None,
        )
        self.storage.get_client_for_rotation.return_value = self.client
        self.storage.get_certificate_for_rotation.return_value = self.current_certificate
        self.storage.get_certificate_rotation.return_value = None
        self.storage.get_pending_certificate_rotation.return_value = None
        self.storage.get_certificate_by_id.return_value = self.replacement_certificate
        self.issuer.get_certificate_chain_pem.return_value = "certificate chain"
        self.certificate_policy = AgentCertificatePolicy(
            lifetime_seconds=7_776_000,
            rotation_window_seconds=1_209_600,
            normal_access_overlap_seconds=900,
        )
        self.use_case = AgentCertificateRotationUseCase(
            storage=self.storage,
            certificate_issuer=self.issuer,
            id_generator=self.id_generator,
        )

    async def test_start_replays_same_rotation_id_and_csr(self) -> None:
        self.storage.get_certificate_rotation.return_value = self.rotation

        result = await self.use_case.rotate(
            identity=self.identity,
            params=self.params,
            policy=self.certificate_policy,
        )

        assert result.certificate == self.replacement_certificate
        assert result.replayed is True
        self.issuer.issue.assert_not_called()
        self.issuer.get_certificate_chain_pem.assert_called_once_with()
        self.storage.create_certificate_rotation.assert_not_awaited()
        audit = self.storage.create_audit_event.await_args.kwargs["params"]
        assert audit.action is AgentActionEnum.ROTATE_AGENT_CERTIFICATE
        assert audit.result is AgentAuditResultEnum.SUCCESS
        assert audit.request_id == self.params.rotation_id
        assert audit.input_digest == self.params.csr_digest()

    async def test_start_rejects_same_rotation_id_with_changed_csr(self) -> None:
        self.storage.get_certificate_rotation.return_value = self.rotation

        with pytest.raises(AgentIdempotencyConflictError):
            await self.use_case.rotate(
                identity=self.identity,
                params=replace(self.params, csr_pem=f"{CSR_PEM}\nchanged"),
                policy=self.certificate_policy,
            )

        self.issuer.issue.assert_not_called()

    async def test_start_rejects_another_rotation_while_current_has_pending(self) -> None:
        self.storage.get_pending_certificate_rotation.return_value = replace(
            self.rotation,
            rotation_id=self.factory.core.hex_id(44),
        )

        with pytest.raises(AgentCertificateRotationConflictError):
            await self.use_case.rotate(
                identity=self.identity,
                params=self.params,
                policy=self.certificate_policy,
            )

        self.issuer.issue.assert_not_called()

    async def test_confirm_requires_replacement_certificate(self) -> None:
        self.storage.get_certificate_rotation.return_value = self.rotation

        with pytest.raises(AgentCertificateRotationConfirmationError):
            await self.use_case.confirm(
                identity=self.identity,
                params=AgentCertificateRotationConfirmParams(
                    rotation_id=self.rotation.rotation_id,
                    confirmed_at=NOW + timedelta(minutes=1),
                ),
            )

        self.storage.confirm_certificate_rotation.assert_not_awaited()

    async def test_confirm_retry_is_idempotent(self) -> None:
        confirmed = replace(self.rotation, confirmed_at=NOW + timedelta(minutes=1))
        self.storage.get_certificate_rotation.return_value = confirmed
        replacement_identity = replace(
            self.identity,
            certificate_id=self.replacement_certificate.id,
        )

        result = await self.use_case.confirm(
            identity=replacement_identity,
            params=AgentCertificateRotationConfirmParams(
                rotation_id=self.rotation.rotation_id,
                confirmed_at=NOW + timedelta(minutes=2),
            ),
        )

        assert result == confirmed
        self.storage.confirm_certificate_rotation.assert_not_awaited()
        audit = self.storage.create_audit_event.await_args.kwargs["params"]
        assert audit.action is AgentActionEnum.CONFIRM_AGENT_CERTIFICATE_ROTATION
        assert audit.result is AgentAuditResultEnum.SUCCESS
        assert audit.request_id == self.rotation.rotation_id

    async def test_confirm_with_replacement_certificate_revokes_current_atomically(self) -> None:
        confirmed_at = NOW + timedelta(minutes=1)
        confirmed = replace(self.rotation, confirmed_at=confirmed_at)
        self.storage.get_certificate_rotation.return_value = self.rotation
        self.storage.confirm_certificate_rotation.return_value = confirmed
        replacement_identity = replace(
            self.identity,
            certificate_id=self.replacement_certificate.id,
        )

        result = await self.use_case.confirm(
            identity=replacement_identity,
            params=AgentCertificateRotationConfirmParams(
                rotation_id=self.rotation.rotation_id,
                confirmed_at=confirmed_at,
            ),
        )

        assert result == confirmed
        self.storage.confirm_certificate_rotation.assert_awaited_once_with(
            rotation_id=self.rotation.rotation_id,
            current_certificate_id=self.current_certificate.id,
            confirmed_at=confirmed_at,
        )
        audit = self.storage.create_audit_event.await_args.kwargs["params"]
        assert audit.action is AgentActionEnum.CONFIRM_AGENT_CERTIFICATE_ROTATION
        assert audit.result is AgentAuditResultEnum.SUCCESS
        assert audit.certificate_id == self.replacement_certificate.id

    @pytest.mark.parametrize("operation", ["start", "retry", "confirm"])
    async def test_revoked_client_cannot_start_retry_or_confirm(self, operation: str) -> None:
        self.storage.get_client_for_rotation.return_value = replace(
            self.client,
            status=AgentClientStatusEnum.REVOKED,
            revoked_at=NOW,
        )
        if operation == "retry":
            self.storage.get_certificate_rotation.return_value = self.rotation
        identity = self.identity
        if operation == "confirm":
            self.storage.get_certificate_rotation.return_value = self.rotation
            identity = replace(identity, certificate_id=self.replacement_certificate.id)

        operation_call = (
            self.use_case.confirm(
                identity=identity,
                params=AgentCertificateRotationConfirmParams(
                    rotation_id=self.rotation.rotation_id,
                    confirmed_at=NOW,
                ),
            )
            if operation == "confirm"
            else self.use_case.rotate(
                identity=identity,
                params=self.params,
                policy=self.certificate_policy,
            )
        )
        with pytest.raises(AgentAuthenticationError):
            await operation_call

        self.issuer.issue.assert_not_called()
        self.storage.confirm_certificate_rotation.assert_not_awaited()


class TestAgentAdminPolicy(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=AgentAdminStorage)
        self.issuer = Mock(spec=AgentCertificateIssuer)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.certificate_policy = AgentCertificatePolicy(
            lifetime_seconds=7_776_000,
            rotation_window_seconds=1_209_600,
            normal_access_overlap_seconds=900,
        )
        self.audit_policy = AgentAuditPolicy(
            page_size_max=100,
            retention_seconds=31_536_000,
        )
        self.use_case = AgentAdminUseCase(
            storage=self.storage,
            certificate_issuer=self.issuer,
            id_generator=self.id_generator,
        )

    async def test_register_rejects_duplicate_name_case_insensitively(self) -> None:
        self.storage.client_name_exists.return_value = True

        with pytest.raises(AgentClientNameConflictError):
            await self.use_case.register_client(
                params=AgentClientRegisterParams(
                    name=" Desktop-Codex ",
                    scopes=frozenset({AgentScopeEnum.MATRIX_QUEUE_CLAIM}),
                    csr_pem=CSR_PEM,
                    registered_at=NOW,
                ),
                policy=self.certificate_policy,
            )

        self.storage.client_name_exists.assert_awaited_once_with(
            normalized_name="desktop-codex",
        )
        self.issuer.issue.assert_not_called()
        self.storage.create_client.assert_not_awaited()

    @pytest.mark.parametrize("page_size", [0, 101])
    async def test_audit_page_rejects_unbounded_page_size(self, page_size: int) -> None:
        with pytest.raises(AgentAuditPaginationError):
            await self.use_case.list_audit_events(
                params=AgentAuditEventPageParams(
                    agent_client_id=self.factory.core.hex_id(50),
                    page_size=page_size,
                    cursor=None,
                ),
                requested_at=NOW,
                policy=self.audit_policy,
            )

        self.storage.list_audit_events.assert_not_awaited()

    async def test_audit_page_uses_retention_cutoff_and_newest_first_cursor(self) -> None:
        client_id = self.factory.core.hex_id(50)
        events = tuple(
            AgentAuditEvent(
                id=self.factory.core.hex_id(index),
                agent_client_id=client_id,
                certificate_id=self.factory.core.hex_id(60),
                action=AgentActionEnum.GET_MATRIX_AUTHORING_CONTEXT,
                queue_item_id=None,
                matrix_item_id=None,
                request_id=f"request-{index}",
                result=AgentAuditResultEnum.SUCCESS,
                input_digest="a" * 64,
                created_at=NOW - timedelta(minutes=index),
            )
            for index in range(1, 4)
        )
        self.storage.list_audit_events.return_value = events

        result = await self.use_case.list_audit_events(
            params=AgentAuditEventPageParams(
                agent_client_id=client_id,
                page_size=2,
                cursor=AgentAuditCursor(
                    created_at=NOW - timedelta(seconds=1),
                    event_id=self.factory.core.hex_id(99),
                ),
            ),
            requested_at=NOW,
            policy=self.audit_policy,
        )

        assert result == AgentAuditEventPage(
            events=events[:2],
            next_cursor=AgentAuditCursor(
                created_at=events[1].created_at,
                event_id=events[1].id,
            ),
        )
        query = self.storage.list_audit_events.await_args.kwargs["params"]
        assert query.created_at_from == NOW - timedelta(days=365)
        assert query.limit == 3

    async def test_audit_page_skips_storage_for_cursor_older_than_retention(self) -> None:
        result = await self.use_case.list_audit_events(
            params=AgentAuditEventPageParams(
                agent_client_id=self.factory.core.hex_id(50),
                page_size=50,
                cursor=AgentAuditCursor(
                    created_at=NOW - timedelta(days=366),
                    event_id=self.factory.core.hex_id(99),
                ),
            ),
            requested_at=NOW,
            policy=self.audit_policy,
        )

        assert result == AgentAuditEventPage(events=(), next_cursor=None)
        self.storage.list_audit_events.assert_not_awaited()
