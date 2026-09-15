import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.exceptions import (
    AgentCertificateRotationConflictError,
    AgentClientNameConflictError,
    AgentIdempotencyConflictError,
    MatrixQuestionQueueEmptyError,
)
from core.agent_access.schemas import (
    AgentAuditCursor,
    AgentAuditEventCreateParams,
    AgentAuditEventPageQuery,
    AgentCertificate,
    AgentCertificateRotation,
    AgentClient,
    AgentClientRevokeParams,
    AgentIdentity,
    ExistingMatrixQuestionDraftResourceParams,
    MatrixAgentPolicy,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
    MatrixQuestionDraftResourceParams,
    MatrixQuestionDraftSaveParams,
    MatrixQuestionDraftSaveResult,
)
from core.agent_access.use_cases import MatrixAgentUseCase
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemNotFoundError,
    CompetencyMatrixStructureNotFoundError,
)
from core.competency_matrix.schemas import QueuedCompetencyMatrixQuestion
from core.enums import PublishStatusEnum
from core.generators import HexUuidIdGenerator
from infra.postgresql.models import (
    AgentAuditEventModel,
    AgentCertificateModel,
    CompetencyMatrixItemModel,
    ExternalResourceModel,
    MatrixQuestionClaimModel,
    MatrixQuestionDraftCompletionModel,
    QueuedQuestionModel,
)
from infra.postgresql.storages.agent_access import AgentAccessDatabaseStorage
from infra.postgresql.storages.competency_matrix import CompetencyMatrixDatabaseStorage
from tests.test_cases import StorageTestCase

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
FINGERPRINT = "a" * 64
INPUT_DIGEST = "b" * 64
MATRIX_POLICY = MatrixAgentPolicy(
    claim_ttl_seconds=7200,
    minimum_resource_count=1,
    maximum_resource_count=3,
)


class TestAgentAccessDatabaseStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.storage = AgentAccessDatabaseStorage(session=session)

    async def test_client_name_lookup_is_case_insensitive_and_duplicate_is_mapped(self) -> None:
        client = await self._create_client(client_id=1, name="Desktop Codex")

        assert await self.storage.client_name_exists(normalized_name="desktop codex") is True
        assert await self.storage.client_name_exists(normalized_name="other") is False
        with pytest.raises(AgentClientNameConflictError):
            await self.storage.create_client(
                client=replace(client, id=self.factory.core.hex_id(2), name="DESKTOP CODEX"),
            )

    async def test_credential_marks_only_pending_current_certificate_with_overlap(self) -> None:
        client = await self._create_client(client_id=3, name="rotating-agent")
        current = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=4,
                client_id=client.id,
                fingerprint="1" * 64,
            ),
        )
        replacement = self._certificate(
            certificate_id=5,
            client_id=client.id,
            fingerprint="2" * 64,
            serial_number="02",
        )
        rotation = self._rotation(
            rotation_id="rotation-1",
            client=client,
            current=current,
            replacement=replacement,
        )
        await self.storage.create_certificate_rotation(
            rotation=rotation,
            replacement=replacement,
        )

        current_credential = await self.storage.get_credential_by_fingerprint(
            fingerprint_sha256=current.fingerprint_sha256,
        )
        replacement_credential = await self.storage.get_credential_by_fingerprint(
            fingerprint_sha256=replacement.fingerprint_sha256,
        )

        assert current_credential.normal_access_until == rotation.normal_access_until
        assert replacement_credential.normal_access_until is None

    async def test_claim_next_matrix_question_uses_fifo_and_reuses_active_claim(self) -> None:
        client = await self._create_client(client_id=10)
        later = self.factory.core.queued_competency_matrix_question(
            question_id=12,
            question="Later question",
            created_at=NOW + timedelta(minutes=1),
        )
        earlier = self.factory.core.queued_competency_matrix_question(
            question_id=11,
            question="Earlier question",
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[later, earlier])

        first = await self._claim(client=client, claimed_at=NOW + timedelta(minutes=2))
        repeated = await self._claim(client=client, claimed_at=NOW + timedelta(minutes=3))

        assert first.question == earlier
        assert repeated == first
        assert (
            await self.db_session.scalar(
                select(func.count()).select_from(MatrixQuestionClaimModel),
            )
            == 1
        )

    async def test_get_queued_question_returns_current_agent_claim_without_lock(self) -> None:
        client = await self._create_client(client_id=13, name="claim-summary-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=14,
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        claim = await self._claim(client=client, claimed_at=NOW)
        matrix_storage = CompetencyMatrixDatabaseStorage(session=self.db_session)

        loaded = await matrix_storage.get_queued_question(question_id=question.id, lock=False)

        assert loaded.id == question.id
        assert loaded.claim is not None
        assert loaded.claim.id == claim.id
        assert loaded.claim.agent_client_id == client.id
        assert loaded.claim.agent_client_name == client.name

    async def test_locked_queued_question_read_returns_claim_committed_by_prior_locker(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        client = await self._create_client(client_id=15, name="prior-locker-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=16,
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        await self.db_session.commit()
        agent_claim_created = asyncio.Event()
        human_lock_started = asyncio.Event()

        async def claim_while_holding_queue_lock() -> MatrixQuestionClaim:
            async with session_maker.begin() as session:
                claim = await AgentAccessDatabaseStorage(
                    session=session,
                ).claim_next_matrix_question(
                    agent_client_id=client.id,
                    claimed_at=NOW,
                    expires_at=NOW + timedelta(hours=2),
                )
                agent_claim_created.set()
                await human_lock_started.wait()
                await asyncio.sleep(0.05)
                return claim

        async def read_after_agent_queue_lock() -> QueuedCompetencyMatrixQuestion:
            await agent_claim_created.wait()
            async with session_maker.begin() as session:
                human_lock_started.set()
                return await CompetencyMatrixDatabaseStorage(
                    session=session,
                ).get_queued_question(question_id=question.id, lock=True)

        claim, loaded = await asyncio.wait_for(
            asyncio.gather(claim_while_holding_queue_lock(), read_after_agent_queue_lock()),
            timeout=5,
        )

        assert loaded.claim is not None
        assert loaded.claim.id == claim.id
        assert loaded.claim.agent_client_id == client.id
        assert loaded.claim.agent_client_name == client.name

    async def test_parallel_clients_cannot_claim_the_same_question(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        first_client = await self._create_client(client_id=20, name="first-agent")
        second_client = await self._create_client(client_id=21, name="second-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=22,
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        await self.db_session.commit()

        async def claim_in_transaction(client_id: str) -> MatrixQuestionClaim:
            async with session_maker.begin() as session:
                return await AgentAccessDatabaseStorage(
                    session=session,
                ).claim_next_matrix_question(
                    agent_client_id=client_id,
                    claimed_at=NOW,
                    expires_at=NOW + timedelta(hours=2),
                )

        results = await asyncio.gather(
            claim_in_transaction(first_client.id),
            claim_in_transaction(second_client.id),
            return_exceptions=True,
        )

        assert len([result for result in results if isinstance(result, MatrixQuestionClaim)]) == 1
        assert (
            len(
                [result for result in results if isinstance(result, MatrixQuestionQueueEmptyError)],
            )
            == 1
        )

    async def test_expired_claim_makes_question_reclaimable(self) -> None:
        first_client = await self._create_client(client_id=30, name="expired-agent")
        second_client = await self._create_client(client_id=31, name="reclaiming-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=32,
            created_at=NOW - timedelta(days=1),
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        expired = await self._claim(
            client=first_client,
            claimed_at=NOW - timedelta(hours=3),
        )

        reclaimed = await self._claim(client=second_client, claimed_at=NOW)

        assert reclaimed.question == question
        assert reclaimed.id != expired.id

    async def test_expired_claim_cleanup_waits_for_human_queue_lock_without_deadlock(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        client = await self._create_client(client_id=33, name="expired-lock-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=34,
            created_at=NOW - timedelta(days=1),
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        expired = await self._claim(
            client=client,
            claimed_at=NOW - timedelta(hours=3),
        )
        await self.db_session.commit()
        human_has_queue_lock = asyncio.Event()
        agent_started = asyncio.Event()

        async def human_cleanup() -> None:
            async with session_maker.begin() as session:
                storage = CompetencyMatrixDatabaseStorage(session=session)
                await storage.get_queued_question(question_id=question.id, lock=True)
                human_has_queue_lock.set()
                await agent_started.wait()
                await asyncio.sleep(0.05)
                await storage.delete_question_claim(expired.id)

        async def agent_reclaim() -> MatrixQuestionClaim:
            await human_has_queue_lock.wait()
            agent_started.set()
            async with session_maker.begin() as session:
                return await AgentAccessDatabaseStorage(
                    session=session,
                ).claim_next_matrix_question(
                    agent_client_id=client.id,
                    claimed_at=NOW,
                    expires_at=NOW + timedelta(hours=2),
                )

        human_result, reclaimed = await asyncio.wait_for(
            asyncio.gather(human_cleanup(), agent_reclaim()),
            timeout=5,
        )

        assert human_result is None
        assert reclaimed.question == question
        assert reclaimed.id != expired.id

    async def test_agent_lock_waits_for_human_queue_lock_without_deadlock(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        client = await self._create_client(client_id=40, name="lock-order-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=41,
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        claim = await self._claim(client=client, claimed_at=NOW)
        await self.db_session.commit()
        human_has_queue_lock = asyncio.Event()
        agent_started = asyncio.Event()

        async def human_release() -> None:
            async with session_maker.begin() as session:
                storage = CompetencyMatrixDatabaseStorage(session=session)
                await storage.get_queued_question(question_id=question.id, lock=True)
                human_has_queue_lock.set()
                await agent_started.wait()
                await asyncio.sleep(0.05)
                await storage.delete_question_claim(claim.id)

        async def agent_lock() -> MatrixQuestionClaim | None:
            await human_has_queue_lock.wait()
            agent_started.set()
            async with session_maker.begin() as session:
                return await AgentAccessDatabaseStorage(
                    session=session,
                ).lock_matrix_question_claim(
                    agent_client_id=client.id,
                    claim_id=claim.id,
                )

        human_result, agent_result = await asyncio.wait_for(
            asyncio.gather(human_release(), agent_lock()),
            timeout=5,
        )

        assert human_result is None
        assert agent_result is None

    async def test_release_claim_keeps_queue_item_available(self) -> None:
        client = await self._create_client(client_id=45, name="release-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=46,
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        claim = await self._claim(client=client, claimed_at=NOW)

        queue_item_id = await self.storage.release_matrix_question_claim(
            agent_client_id=client.id,
            claim_id=claim.id,
            released_at=NOW + timedelta(minutes=1),
        )

        assert queue_item_id == question.id
        assert await self.db_session.get(QueuedQuestionModel, question.id) is not None
        assert await self.db_session.get(MatrixQuestionClaimModel, claim.id) is None

    async def test_revoke_client_releases_all_owned_claims_and_keeps_queue_available(
        self,
    ) -> None:
        client = await self._create_client(client_id=47, name="revoked-claim-agent")
        question = self.factory.core.queued_competency_matrix_question(
            question_id=48,
            created_at=NOW,
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        claim = await self._claim(client=client, claimed_at=NOW)

        await self.storage.revoke_client(
            params=AgentClientRevokeParams(
                agent_client_id=client.id,
                revoked_at=NOW + timedelta(minutes=1),
            ),
        )

        assert await self.db_session.get(MatrixQuestionClaimModel, claim.id) is None
        assert await self.db_session.get(QueuedQuestionModel, question.id) is not None

    async def test_save_transaction_creates_completion_draft_and_audit_then_consumes_queue(
        self,
    ) -> None:
        client, certificate, claim, params = await self._prepare_draft_save(seed=50)
        use_case = self._matrix_use_case(
            storage=self.storage,
            generated_ids=[self.factory.core.hex_id(56), self.factory.core.hex_id(57)],
        )

        result = await use_case.save_matrix_question_draft(
            identity=self._identity(client=client, certificate=certificate),
            params=params,
            completed_at=NOW + timedelta(minutes=30),
            policy=MATRIX_POLICY,
        )

        item = await self.db_session.get(CompetencyMatrixItemModel, result.item_id)
        completion = await self.db_session.get(MatrixQuestionDraftCompletionModel, claim.id)
        audit = await self.db_session.scalar(select(AgentAuditEventModel))
        assert item is not None
        assert item.publish_status == PublishStatusEnum.DRAFT
        assert item.published_at is None
        assert completion is not None
        assert completion.input_digest == params.canonical_digest()
        assert audit is not None
        assert audit.action == AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT
        assert audit.matrix_item_id == item.id
        assert await self.db_session.get(QueuedQuestionModel, claim.question.id) is None
        assert await self.db_session.get(MatrixQuestionClaimModel, claim.id) is None

    async def test_digest_replay_returns_same_draft_and_changed_input_conflicts(self) -> None:
        client, certificate, _claim, params = await self._prepare_draft_save(seed=60)
        identity = self._identity(client=client, certificate=certificate)
        use_case = self._matrix_use_case(
            storage=self.storage,
            generated_ids=[self.factory.core.hex_id(66), self.factory.core.hex_id(67)],
        )
        first = await use_case.save_matrix_question_draft(
            identity=identity,
            params=params,
            completed_at=NOW + timedelta(minutes=30),
            policy=MATRIX_POLICY,
        )

        replayed = await use_case.save_matrix_question_draft(
            identity=identity,
            params=params,
            completed_at=NOW + timedelta(minutes=31),
            policy=MATRIX_POLICY,
        )
        with pytest.raises(AgentIdempotencyConflictError):
            await use_case.save_matrix_question_draft(
                identity=identity,
                params=replace(params, answer_en="A changed answer"),
                completed_at=NOW + timedelta(minutes=32),
                policy=MATRIX_POLICY,
            )

        assert replayed == MatrixQuestionDraftSaveResult(item_id=first.item_id, replayed=True)
        assert (
            await self.db_session.scalar(
                select(func.count()).select_from(CompetencyMatrixItemModel),
            )
            == 1
        )

    async def test_parallel_save_lock_wait_replays_committed_completion(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        client, certificate, _claim, params = await self._prepare_draft_save(seed=70)
        identity = self._identity(client=client, certificate=certificate)
        await self.db_session.commit()

        async def save_in_transaction(
            item_id: int,
            resource_id: int,
        ) -> MatrixQuestionDraftSaveResult:
            async with session_maker.begin() as session:
                return await self._matrix_use_case(
                    storage=AgentAccessDatabaseStorage(session=session),
                    matrix_storage=CompetencyMatrixDatabaseStorage(session=session),
                    generated_ids=[
                        self.factory.core.hex_id(item_id),
                        self.factory.core.hex_id(resource_id),
                    ],
                ).save_matrix_question_draft(
                    identity=identity,
                    params=params,
                    completed_at=NOW + timedelta(minutes=30),
                    policy=MATRIX_POLICY,
                )

        first, second = await asyncio.gather(
            save_in_transaction(76, 77),
            save_in_transaction(78, 79),
        )

        assert first.item_id == second.item_id
        assert {first.replayed, second.replayed} == {False, True}

    async def test_late_audit_failure_rolls_back_draft_completion_and_consumption(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        client, certificate, claim, params = await self._prepare_draft_save(seed=80)
        identity = replace(
            self._identity(client=client, certificate=certificate),
            certificate_id=self.factory.core.hex_id(999),
        )
        await self.db_session.commit()

        with pytest.raises(IntegrityError):
            async with session_maker.begin() as session:
                await self._matrix_use_case(
                    storage=AgentAccessDatabaseStorage(session=session),
                    matrix_storage=CompetencyMatrixDatabaseStorage(session=session),
                    generated_ids=[self.factory.core.hex_id(86), self.factory.core.hex_id(87)],
                ).save_matrix_question_draft(
                    identity=identity,
                    params=params,
                    completed_at=NOW + timedelta(minutes=30),
                    policy=MATRIX_POLICY,
                )

        async with session_maker() as session:
            assert await session.get(QueuedQuestionModel, claim.question.id) is not None
            assert await session.get(MatrixQuestionClaimModel, claim.id) is not None
            assert await session.get(MatrixQuestionDraftCompletionModel, claim.id) is None
            assert (
                await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel))
                == 0
            )
            assert (
                await session.scalar(select(func.count()).select_from(ExternalResourceModel)) == 0
            )
            assert await session.scalar(select(func.count()).select_from(AgentAuditEventModel)) == 0

    async def test_missing_structure_is_domain_mapped_before_any_draft_mutation(self) -> None:
        client, certificate, claim, params = await self._prepare_draft_save(seed=88)
        use_case = self._matrix_use_case(
            storage=self.storage,
            generated_ids=[self.factory.core.hex_id(894), self.factory.core.hex_id(895)],
        )

        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            await use_case.save_matrix_question_draft(
                identity=self._identity(client=client, certificate=certificate),
                params=replace(params, subsection_id=self.factory.core.hex_id(999)),
                completed_at=NOW + timedelta(minutes=30),
                policy=MATRIX_POLICY,
            )

        assert await self.db_session.get(QueuedQuestionModel, claim.question.id) is not None
        assert await self.db_session.get(MatrixQuestionClaimModel, claim.id) is not None
        assert await self.db_session.get(MatrixQuestionDraftCompletionModel, claim.id) is None

    async def test_missing_existing_resource_is_domain_mapped_before_draft_mutation(self) -> None:
        client, certificate, claim, params = await self._prepare_draft_save(seed=89)
        use_case = self._matrix_use_case(
            storage=self.storage,
            generated_ids=[self.factory.core.hex_id(904)],
        )
        missing_resource_params = replace(
            params,
            resources=(
                ExistingMatrixQuestionDraftResourceParams(
                    resource_id=self.factory.core.hex_id(999),
                    context_ru="Контекст",
                    context_en="Context",
                ),
            ),
        )

        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await use_case.save_matrix_question_draft(
                identity=self._identity(client=client, certificate=certificate),
                params=missing_resource_params,
                completed_at=NOW + timedelta(minutes=30),
                policy=MATRIX_POLICY,
            )

        assert await self.db_session.get(QueuedQuestionModel, claim.question.id) is not None
        assert await self.db_session.get(MatrixQuestionClaimModel, claim.id) is not None
        assert await self.db_session.get(MatrixQuestionDraftCompletionModel, claim.id) is None

    async def test_two_phase_rotation_replays_pending_and_confirm_revokes_current(self) -> None:
        client = await self._create_client(client_id=90, name="two-phase-agent")
        current = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=91,
                client_id=client.id,
                fingerprint="3" * 64,
            ),
        )
        replacement = self._certificate(
            certificate_id=92,
            client_id=client.id,
            fingerprint="4" * 64,
            serial_number="04",
        )
        rotation = self._rotation(
            rotation_id="rotation-2",
            client=client,
            current=current,
            replacement=replacement,
        )

        await self.storage.create_certificate_rotation(
            rotation=rotation,
            replacement=replacement,
        )
        loaded = await self.storage.get_certificate_rotation(rotation_id=rotation.rotation_id)
        pending = await self.storage.get_pending_certificate_rotation(
            current_certificate_id=current.id,
        )
        confirmed = await self.storage.confirm_certificate_rotation(
            rotation_id=rotation.rotation_id,
            current_certificate_id=current.id,
            confirmed_at=NOW + timedelta(minutes=2),
        )
        confirmed_retry = await self.storage.confirm_certificate_rotation(
            rotation_id=rotation.rotation_id,
            current_certificate_id=current.id,
            confirmed_at=NOW + timedelta(minutes=3),
        )

        current_model = await self.db_session.get(AgentCertificateModel, current.id)
        assert loaded == rotation
        assert pending == rotation
        assert confirmed.confirmed_at == NOW + timedelta(minutes=2)
        assert confirmed_retry == confirmed
        assert current_model is not None
        assert current_model.revoked_at == NOW + timedelta(minutes=2)

    async def test_second_pending_rotation_is_mapped_to_domain_conflict(self) -> None:
        client = await self._create_client(client_id=100, name="pending-conflict-agent")
        current = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=101,
                client_id=client.id,
                fingerprint="5" * 64,
            ),
        )
        first_replacement = self._certificate(
            certificate_id=102,
            client_id=client.id,
            fingerprint="6" * 64,
            serial_number="06",
        )
        second_replacement = self._certificate(
            certificate_id=103,
            client_id=client.id,
            fingerprint="7" * 64,
            serial_number="07",
        )
        await self.storage.create_certificate_rotation(
            rotation=self._rotation(
                rotation_id="rotation-first",
                client=client,
                current=current,
                replacement=first_replacement,
            ),
            replacement=first_replacement,
        )

        with pytest.raises(AgentCertificateRotationConflictError):
            await self.storage.create_certificate_rotation(
                rotation=self._rotation(
                    rotation_id="rotation-second",
                    client=client,
                    current=current,
                    replacement=second_replacement,
                ),
                replacement=second_replacement,
            )

    async def test_audit_cursor_is_newest_first_and_bounded_by_retention(self) -> None:
        client = await self._create_client(client_id=110, name="audit-agent")
        certificate = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=111,
                client_id=client.id,
                fingerprint="8" * 64,
            ),
        )
        created = []
        for index, created_at in enumerate(
            [NOW - timedelta(days=400), NOW, NOW, NOW + timedelta(minutes=1)],
            start=1,
        ):
            created.append(
                await self.storage.create_audit_event(
                    params=self._audit_params(
                        client=client,
                        certificate=certificate,
                        request_id=f"request-{index}",
                        created_at=created_at,
                    ),
                ),
            )

        first_page = await self.storage.list_audit_events(
            params=AgentAuditEventPageQuery(
                agent_client_id=client.id,
                limit=2,
                cursor=None,
                created_at_from=NOW - timedelta(days=365),
            ),
        )
        second_page = await self.storage.list_audit_events(
            params=AgentAuditEventPageQuery(
                agent_client_id=client.id,
                limit=101,
                cursor=AgentAuditCursor(
                    created_at=first_page[-1].created_at,
                    event_id=first_page[-1].id,
                ),
                created_at_from=NOW - timedelta(days=365),
            ),
        )

        eligible = tuple(
            sorted(
                created[1:],
                key=lambda event: (event.created_at, event.id),
                reverse=True,
            ),
        )
        assert first_page == eligible[:2]
        assert second_page == eligible[2:]

    async def test_audit_persists_success_rejected_and_failed_outcomes(self) -> None:
        client = await self._create_client(client_id=115, name="audit-outcomes-agent")
        certificate = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=116,
                client_id=client.id,
                fingerprint="f" * 64,
            ),
        )
        created = []
        for index, result in enumerate(AgentAuditResultEnum):
            created.append(
                await self.storage.create_audit_event(
                    params=replace(
                        self._audit_params(
                            client=client,
                            certificate=certificate,
                            request_id=f"outcome-{index}",
                            created_at=NOW + timedelta(seconds=index),
                        ),
                        action=AgentActionEnum.ROTATE_AGENT_CERTIFICATE,
                        result=result,
                    ),
                ),
            )

        loaded = await self.storage.list_audit_events(
            params=AgentAuditEventPageQuery(
                agent_client_id=client.id,
                limit=100,
                cursor=None,
                created_at_from=NOW - timedelta(seconds=1),
            ),
        )

        assert {event.result for event in loaded} == set(AgentAuditResultEnum)
        assert all(event.action == AgentActionEnum.ROTATE_AGENT_CERTIFICATE for event in loaded)
        assert set(loaded) == set(created)

    async def test_prune_deletes_only_old_audits_and_preserves_completion(self) -> None:
        client = await self._create_client(client_id=120, name="prune-agent")
        certificate = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=121,
                client_id=client.id,
                fingerprint="9" * 64,
            ),
        )
        old_event = await self.storage.create_audit_event(
            params=self._audit_params(
                client=client,
                certificate=certificate,
                request_id="old",
                created_at=NOW - timedelta(days=366),
            ),
        )
        current_event = await self.storage.create_audit_event(
            params=self._audit_params(
                client=client,
                certificate=certificate,
                request_id="current",
                created_at=NOW,
            ),
        )
        completion = MatrixQuestionDraftCompletion(
            claim_id=self.factory.core.hex_id(122),
            agent_client_id=client.id,
            queue_item_id=self.factory.core.hex_id(123),
            matrix_item_id=self.factory.core.hex_id(124),
            input_digest=INPUT_DIGEST,
            completed_at=NOW - timedelta(days=500),
        )
        await self.storage.create_matrix_question_draft_completion(completion=completion)

        deleted_count = await self.storage.prune_audit_events(
            created_at_before=NOW - timedelta(days=365),
        )

        assert deleted_count == 1
        assert await self.db_session.get(AgentAuditEventModel, old_event.id) is None
        assert await self.db_session.get(AgentAuditEventModel, current_event.id) is not None
        assert (
            await self.db_session.get(MatrixQuestionDraftCompletionModel, completion.claim_id)
            is not None
        )

    async def _prepare_draft_save(
        self,
        *,
        seed: int,
    ) -> tuple[AgentClient, AgentCertificate, MatrixQuestionClaim, MatrixQuestionDraftSaveParams]:
        client = await self._create_client(client_id=seed, name=f"draft-agent-{seed}")
        certificate = await self.storage.create_certificate(
            certificate=self._certificate(
                certificate_id=seed + 1,
                client_id=client.id,
                fingerprint=f"{seed % 10}" * 64,
                serial_number=f"{seed:02d}",
            ),
        )
        structure = self.factory.core.competency_matrix_item_structure(
            sheet_id=seed + 2,
            section_id=seed + 3,
            subsection_id=seed + 4,
            sheet_key=f"sheet-{seed}",
        )
        await self.storage_helper.create_competency_matrix_structure(structure=structure)
        question = self.factory.core.queued_competency_matrix_question(
            question_id=seed + 5,
            created_at=NOW - timedelta(days=1),
        )
        await self.storage_helper.create_queued_matrix_questions(questions=[question])
        claim = await self._claim(client=client, claimed_at=NOW)
        return (
            client,
            certificate,
            claim,
            self._draft_params(claim_id=claim.id, subsection_id=structure.subsection_id),
        )

    def _matrix_use_case(
        self,
        *,
        storage: AgentAccessDatabaseStorage,
        generated_ids: list[str],
        matrix_storage: CompetencyMatrixDatabaseStorage | None = None,
    ) -> MatrixAgentUseCase:
        ids = iter(generated_ids)
        return MatrixAgentUseCase(
            storage=storage,
            matrix_storage=matrix_storage
            or CompetencyMatrixDatabaseStorage(
                session=storage.session,
            ),
            id_generator=HexUuidIdGenerator(generator=lambda: next(ids)),
        )

    def _client(self, *, client_id: int, name: str = "desktop-codex") -> AgentClient:
        return AgentClient(
            id=self.factory.core.hex_id(client_id),
            name=name,
            status=AgentClientStatusEnum.ACTIVE,
            scopes=frozenset(AgentScopeEnum),
            created_at=NOW - timedelta(days=2),
            revoked_at=None,
        )

    async def _create_client(
        self,
        *,
        client_id: int,
        name: str = "desktop-codex",
    ) -> AgentClient:
        return await self.storage.create_client(client=self._client(client_id=client_id, name=name))

    def _certificate(
        self,
        *,
        certificate_id: int,
        client_id: str,
        fingerprint: str,
        serial_number: str = "01",
    ) -> AgentCertificate:
        return AgentCertificate(
            id=self.factory.core.hex_id(certificate_id),
            agent_client_id=client_id,
            fingerprint_sha256=fingerprint,
            serial_number=serial_number,
            certificate_pem="-----BEGIN CERTIFICATE-----\ntest\n-----END CERTIFICATE-----",
            valid_from=NOW - timedelta(days=1),
            expires_at=NOW + timedelta(days=89),
            created_at=NOW - timedelta(days=1),
            revoked_at=None,
        )

    def _rotation(
        self,
        *,
        rotation_id: str,
        client: AgentClient,
        current: AgentCertificate,
        replacement: AgentCertificate,
    ) -> AgentCertificateRotation:
        return AgentCertificateRotation(
            rotation_id=rotation_id,
            agent_client_id=client.id,
            current_certificate_id=current.id,
            replacement_certificate_id=replacement.id,
            csr_digest="c" * 64,
            created_at=NOW,
            normal_access_until=NOW + timedelta(minutes=15),
            confirmed_at=None,
        )

    def _identity(
        self,
        *,
        client: AgentClient,
        certificate: AgentCertificate,
    ) -> AgentIdentity:
        return AgentIdentity(
            agent_client_id=client.id,
            agent_client_name=client.name,
            certificate_id=certificate.id,
            scopes=client.scopes,
        )

    async def _claim(
        self,
        *,
        client: AgentClient,
        claimed_at: datetime,
    ) -> MatrixQuestionClaim:
        return await self.storage.claim_next_matrix_question(
            agent_client_id=client.id,
            claimed_at=claimed_at,
            expires_at=claimed_at + timedelta(hours=2),
        )

    def _draft_params(
        self,
        *,
        claim_id: str,
        subsection_id: str,
    ) -> MatrixQuestionDraftSaveParams:
        return MatrixQuestionDraftSaveParams(
            claim_id=claim_id,
            slug=f"draft-{claim_id}",
            subsection_id=subsection_id,
            grade=GradeEnum.JUNIOR,
            interview_frequency=InterviewFrequencyEnum.OFTEN,
            question_ru="Что такое PEP 8?",
            question_en="What is PEP 8?",
            answer_ru="Руководство по стилю Python.",
            answer_en="The Python style guide.",
            interview_answer_explanation_ru="Объяснить назначение и основные правила.",
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

    def _audit_params(
        self,
        *,
        client: AgentClient,
        certificate: AgentCertificate,
        request_id: str,
        created_at: datetime,
    ) -> AgentAuditEventCreateParams:
        return AgentAuditEventCreateParams(
            agent_client_id=client.id,
            certificate_id=certificate.id,
            action=AgentActionEnum.GET_MATRIX_AUTHORING_CONTEXT,
            queue_item_id=None,
            matrix_item_id=None,
            request_id=request_id,
            result=AgentAuditResultEnum.SUCCESS,
            input_digest=INPUT_DIGEST,
            created_at=created_at,
        )
