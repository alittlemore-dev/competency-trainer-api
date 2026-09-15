from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import and_, delete, exists, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer, joinedload

from core.agent_access.enums import AgentClientStatusEnum
from core.agent_access.exceptions import (
    AgentAuthenticationError,
    AgentCertificateRotationConfirmationError,
    AgentCertificateRotationConflictError,
    AgentCertificateRotationNotFoundError,
    AgentClientNameConflictError,
    AgentClientNotFoundError,
    AgentIdempotencyConflictError,
    MatrixQuestionClaimNotFoundError,
    MatrixQuestionQueueEmptyError,
)
from core.agent_access.schemas import (
    AgentAuditEvent,
    AgentAuditEventCreateParams,
    AgentAuditEventPageQuery,
    AgentCertificate,
    AgentCertificateRotation,
    AgentClient,
    AgentClientRevokeParams,
    AgentCredential,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
)
from core.agent_access.storages import (
    AgentAdminStorage,
    AgentAuditStorage,
    AgentCertificateRotationStorage,
    AgentIdentityStorage,
    MatrixAgentStorage,
)
from infra.postgresql.models import (
    AgentAuditEventModel,
    AgentCertificateModel,
    AgentCertificateRotationModel,
    AgentClientModel,
    MatrixQuestionClaimModel,
    MatrixQuestionDraftCompletionModel,
    QueuedQuestionModel,
)


@dataclass(kw_only=True)
class AgentAccessDatabaseStorage(
    AgentAdminStorage,
    AgentIdentityStorage,
    AgentCertificateRotationStorage,
    MatrixAgentStorage,
    AgentAuditStorage,
):
    session: AsyncSession

    async def client_name_exists(self, *, normalized_name: str) -> bool:
        return bool(
            await self.session.scalar(
                select(
                    exists().where(func.lower(AgentClientModel.name) == normalized_name),
                ),
            ),
        )

    async def create_client(self, *, client: AgentClient) -> AgentClient:
        model = AgentClientModel.from_domain_schema(client)
        self.session.add(model)
        try:
            await self.session.flush()
        except IntegrityError as error:
            if self._constraint_name(error) == "agent_client_name_lower_uniq":
                raise AgentClientNameConflictError from error
            raise
        return model.to_domain_schema()

    async def list_clients(self) -> list[AgentClient]:
        clients = await self.session.scalars(
            select(AgentClientModel).order_by(
                AgentClientModel.created_at,
                AgentClientModel.id,
            ),
        )
        return [client.to_domain_schema() for client in clients]

    async def create_certificate(
        self,
        *,
        certificate: AgentCertificate,
    ) -> AgentCertificate:
        model = AgentCertificateModel.from_domain_schema(certificate)
        self.session.add(model)
        await self.session.flush()
        return model.to_domain_schema()

    async def list_certificates(self, *, agent_client_id: str) -> list[AgentCertificate]:
        certificates = await self.session.scalars(
            select(AgentCertificateModel)
            .where(AgentCertificateModel.agent_client_id == agent_client_id)
            .order_by(AgentCertificateModel.created_at, AgentCertificateModel.id),
        )
        return [certificate.to_domain_schema() for certificate in certificates]

    async def revoke_client(self, *, params: AgentClientRevokeParams) -> None:
        revoked_client_id = await self.session.scalar(
            update(AgentClientModel)
            .where(
                AgentClientModel.id == params.agent_client_id,
                AgentClientModel.status != AgentClientStatusEnum.REVOKED,
            )
            .values(
                status=AgentClientStatusEnum.REVOKED,
                revoked_at=params.revoked_at,
            )
            .returning(AgentClientModel.id),
        )
        if revoked_client_id is None:
            existing_client_id = await self.session.scalar(
                select(AgentClientModel.id).where(
                    AgentClientModel.id == params.agent_client_id,
                ),
            )
            if existing_client_id is None:
                raise AgentClientNotFoundError
        await self.session.execute(
            update(AgentCertificateModel)
            .where(
                AgentCertificateModel.agent_client_id == params.agent_client_id,
                AgentCertificateModel.revoked_at.is_(None),
            )
            .values(revoked_at=params.revoked_at),
        )
        await self.session.execute(
            delete(MatrixQuestionClaimModel).where(
                MatrixQuestionClaimModel.agent_client_id == params.agent_client_id,
            ),
        )
        await self.session.flush()

    async def get_credential_by_fingerprint(
        self,
        *,
        fingerprint_sha256: str,
    ) -> AgentCredential:
        row = (
            await self.session.execute(
                select(
                    AgentCertificateModel,
                    AgentCertificateRotationModel.normal_access_until,
                )
                .outerjoin(
                    AgentCertificateRotationModel,
                    and_(
                        AgentCertificateRotationModel.current_certificate_id
                        == AgentCertificateModel.id,
                        AgentCertificateRotationModel.confirmed_at.is_(None),
                    ),
                )
                .where(AgentCertificateModel.fingerprint_sha256 == fingerprint_sha256)
                .options(joinedload(AgentCertificateModel.client)),
            )
        ).one_or_none()
        if row is None:
            raise AgentAuthenticationError
        certificate, normal_access_until = row
        return AgentCredential(
            client=certificate.client.to_domain_schema(),
            certificate=certificate.to_domain_schema(),
            normal_access_until=normal_access_until,
        )

    async def get_client_for_rotation(self, *, agent_client_id: str) -> AgentClient:
        client = await self.session.scalar(
            select(AgentClientModel)
            .where(AgentClientModel.id == agent_client_id)
            .with_for_update(),
        )
        if client is None:
            raise AgentAuthenticationError
        return client.to_domain_schema()

    async def get_certificate_for_rotation(
        self,
        *,
        certificate_id: str,
        agent_client_id: str,
    ) -> AgentCertificate:
        certificate = await self.session.scalar(
            select(AgentCertificateModel)
            .where(
                AgentCertificateModel.id == certificate_id,
                AgentCertificateModel.agent_client_id == agent_client_id,
                AgentCertificateModel.revoked_at.is_(None),
            )
            .with_for_update(),
        )
        if certificate is None:
            raise AgentAuthenticationError
        return certificate.to_domain_schema()

    async def get_certificate_by_id(
        self,
        *,
        certificate_id: str,
        agent_client_id: str,
    ) -> AgentCertificate:
        certificate = await self.session.scalar(
            select(AgentCertificateModel).where(
                AgentCertificateModel.id == certificate_id,
                AgentCertificateModel.agent_client_id == agent_client_id,
            ),
        )
        if certificate is None:
            raise AgentAuthenticationError
        return certificate.to_domain_schema()

    async def get_certificate_rotation(
        self,
        *,
        rotation_id: str,
    ) -> AgentCertificateRotation | None:
        rotation = await self.session.get(AgentCertificateRotationModel, rotation_id)
        return rotation.to_domain_schema() if rotation is not None else None

    async def get_pending_certificate_rotation(
        self,
        *,
        current_certificate_id: str,
    ) -> AgentCertificateRotation | None:
        rotation = await self.session.scalar(
            select(AgentCertificateRotationModel).where(
                AgentCertificateRotationModel.current_certificate_id == current_certificate_id,
                AgentCertificateRotationModel.confirmed_at.is_(None),
            ),
        )
        return rotation.to_domain_schema() if rotation is not None else None

    async def create_certificate_rotation(
        self,
        *,
        rotation: AgentCertificateRotation,
        replacement: AgentCertificate,
    ) -> None:
        self.session.add(AgentCertificateModel.from_domain_schema(replacement))
        self.session.add(AgentCertificateRotationModel.from_domain_schema(rotation))
        try:
            await self.session.flush()
        except IntegrityError as error:
            constraint_name = self._constraint_name(error)
            if constraint_name == "agent_certificate_rotation_pkey":
                raise AgentIdempotencyConflictError from error
            if constraint_name in {
                "agent_certificate_rotation_pending_current_uniq",
                "agent_certificate_rotation_replacement_uniq",
            }:
                raise AgentCertificateRotationConflictError from error
            raise

    async def confirm_certificate_rotation(
        self,
        *,
        rotation_id: str,
        current_certificate_id: str,
        confirmed_at: datetime,
    ) -> AgentCertificateRotation:
        rotation = await self.session.scalar(
            select(AgentCertificateRotationModel)
            .where(AgentCertificateRotationModel.rotation_id == rotation_id)
            .with_for_update(),
        )
        if rotation is None:
            raise AgentCertificateRotationNotFoundError
        if rotation.current_certificate_id != current_certificate_id:
            raise AgentCertificateRotationConfirmationError
        if rotation.confirmed_at is not None:
            return rotation.to_domain_schema()
        revoked_certificate_id = await self.session.scalar(
            update(AgentCertificateModel)
            .where(
                AgentCertificateModel.id == current_certificate_id,
                AgentCertificateModel.agent_client_id == rotation.agent_client_id,
                AgentCertificateModel.revoked_at.is_(None),
            )
            .values(revoked_at=confirmed_at)
            .returning(AgentCertificateModel.id),
        )
        if revoked_certificate_id is None:
            raise AgentCertificateRotationConfirmationError
        rotation.confirmed_at = confirmed_at
        await self.session.flush()
        return rotation.to_domain_schema()

    async def create_audit_event(
        self,
        *,
        params: AgentAuditEventCreateParams,
    ) -> AgentAuditEvent:
        event = AgentAuditEventModel(
            agent_client_id=params.agent_client_id,
            certificate_id=params.certificate_id,
            action=params.action,
            queue_item_id=params.queue_item_id,
            matrix_item_id=params.matrix_item_id,
            request_id=params.request_id,
            result=params.result,
            input_digest=params.input_digest,
            created_at=params.created_at,
        )
        self.session.add(event)
        await self.session.flush()
        return event.to_domain_schema()

    async def prune_audit_events(self, *, created_at_before: datetime) -> int:
        result = await self.session.execute(
            delete(AgentAuditEventModel).where(
                AgentAuditEventModel.created_at < created_at_before,
            ),
        )
        await self.session.flush()
        rowcount = cast("int | None", getattr(result, "rowcount", None))
        if rowcount is None:
            return 0
        return rowcount

    async def claim_next_matrix_question(
        self,
        *,
        agent_client_id: str,
        claimed_at: datetime,
        expires_at: datetime,
    ) -> MatrixQuestionClaim:
        client = await self.session.scalar(
            select(AgentClientModel)
            .where(AgentClientModel.id == agent_client_id)
            .with_for_update(),
        )
        if (
            client is None
            or client.status != AgentClientStatusEnum.ACTIVE
            or client.revoked_at is not None
        ):
            raise AgentAuthenticationError

        owned_claim_queue_item_id = await self.session.scalar(
            select(QueuedQuestionModel.id)
            .join(
                MatrixQuestionClaimModel,
                MatrixQuestionClaimModel.queue_item_id == QueuedQuestionModel.id,
            )
            .where(
                MatrixQuestionClaimModel.agent_client_id == agent_client_id,
            )
            .with_for_update(of=QueuedQuestionModel),
        )
        if owned_claim_queue_item_id is not None:
            owned_claim = await self.session.scalar(
                select(MatrixQuestionClaimModel)
                .where(
                    MatrixQuestionClaimModel.agent_client_id == agent_client_id,
                    MatrixQuestionClaimModel.queue_item_id == owned_claim_queue_item_id,
                )
                .options(
                    joinedload(MatrixQuestionClaimModel.question).defer(
                        QueuedQuestionModel.question_fingerprint,
                    ),
                )
                .with_for_update(of=MatrixQuestionClaimModel),
            )
            if owned_claim is not None:
                if owned_claim.expires_at > claimed_at:
                    return owned_claim.to_domain_schema()
                await self.session.delete(owned_claim)
                await self.session.flush()

        active_claim_exists = exists(
            select(MatrixQuestionClaimModel.id).where(
                MatrixQuestionClaimModel.queue_item_id == QueuedQuestionModel.id,
                MatrixQuestionClaimModel.expires_at > claimed_at,
            ),
        )
        question = await self.session.scalar(
            select(QueuedQuestionModel)
            .where(~active_claim_exists)
            .order_by(QueuedQuestionModel.created_at, QueuedQuestionModel.id)
            .options(defer(QueuedQuestionModel.question_fingerprint))
            .with_for_update(skip_locked=True),
        )
        if question is None:
            raise MatrixQuestionQueueEmptyError

        await self.session.execute(
            delete(MatrixQuestionClaimModel).where(
                MatrixQuestionClaimModel.queue_item_id == question.id,
                MatrixQuestionClaimModel.expires_at <= claimed_at,
            ),
        )
        claim = MatrixQuestionClaimModel(
            agent_client_id=agent_client_id,
            queue_item_id=question.id,
            question=question,
            claimed_at=claimed_at,
            expires_at=expires_at,
        )
        self.session.add(claim)
        await self.session.flush()
        return claim.to_domain_schema()

    async def get_matrix_question_draft_completion(
        self,
        *,
        claim_id: str,
        agent_client_id: str,
    ) -> MatrixQuestionDraftCompletion | None:
        completion = await self.session.scalar(
            select(MatrixQuestionDraftCompletionModel).where(
                MatrixQuestionDraftCompletionModel.claim_id == claim_id,
                MatrixQuestionDraftCompletionModel.agent_client_id == agent_client_id,
            ),
        )
        return completion.to_domain_schema() if completion is not None else None

    async def lock_matrix_question_claim(
        self,
        *,
        agent_client_id: str,
        claim_id: str,
    ) -> MatrixQuestionClaim | None:
        queue_item_id = await self.session.scalar(
            select(MatrixQuestionClaimModel.queue_item_id).where(
                MatrixQuestionClaimModel.id == claim_id,
                MatrixQuestionClaimModel.agent_client_id == agent_client_id,
            ),
        )
        if queue_item_id is None:
            return None
        queue_item = await self.session.scalar(
            select(QueuedQuestionModel)
            .where(QueuedQuestionModel.id == queue_item_id)
            .options(defer(QueuedQuestionModel.question_fingerprint))
            .with_for_update(),
        )
        if queue_item is None:
            return None
        claim = await self.session.scalar(
            select(MatrixQuestionClaimModel)
            .where(
                MatrixQuestionClaimModel.id == claim_id,
                MatrixQuestionClaimModel.agent_client_id == agent_client_id,
                MatrixQuestionClaimModel.queue_item_id == queue_item_id,
            )
            .options(
                joinedload(MatrixQuestionClaimModel.question).defer(
                    QueuedQuestionModel.question_fingerprint,
                ),
            )
            .with_for_update(of=MatrixQuestionClaimModel),
        )
        return claim.to_domain_schema() if claim is not None else None

    async def create_matrix_question_draft_completion(
        self,
        *,
        completion: MatrixQuestionDraftCompletion,
    ) -> None:
        self.session.add(MatrixQuestionDraftCompletionModel.from_domain_schema(completion))
        try:
            await self.session.flush()
        except IntegrityError as error:
            if self._constraint_name(error) in {
                "agent_access__matrix_question_draft_completion_model_pkey",
                "matrix_question_draft_completion_model_pkey",
            }:
                raise AgentIdempotencyConflictError from error
            raise

    async def consume_matrix_question_claim(
        self,
        *,
        agent_client_id: str,
        claim_id: str,
        queue_item_id: str,
    ) -> None:
        locked_queue_item_id = await self.session.scalar(
            select(QueuedQuestionModel.id)
            .where(QueuedQuestionModel.id == queue_item_id)
            .with_for_update(),
        )
        if locked_queue_item_id is None:
            raise MatrixQuestionClaimNotFoundError
        consumed_claim_id = await self.session.scalar(
            delete(MatrixQuestionClaimModel)
            .where(
                MatrixQuestionClaimModel.id == claim_id,
                MatrixQuestionClaimModel.agent_client_id == agent_client_id,
                MatrixQuestionClaimModel.queue_item_id == queue_item_id,
            )
            .returning(MatrixQuestionClaimModel.id),
        )
        if consumed_claim_id is None:
            raise MatrixQuestionClaimNotFoundError
        consumed_queue_item_id = await self.session.scalar(
            delete(QueuedQuestionModel)
            .where(QueuedQuestionModel.id == queue_item_id)
            .returning(QueuedQuestionModel.id),
        )
        if consumed_queue_item_id is None:
            raise MatrixQuestionClaimNotFoundError
        await self.session.flush()

    async def release_matrix_question_claim(
        self,
        *,
        agent_client_id: str,
        claim_id: str,
        released_at: datetime,
    ) -> str:
        queue_item_id = await self.session.scalar(
            select(MatrixQuestionClaimModel.queue_item_id).where(
                MatrixQuestionClaimModel.id == claim_id,
                MatrixQuestionClaimModel.agent_client_id == agent_client_id,
                MatrixQuestionClaimModel.expires_at > released_at,
            ),
        )
        if queue_item_id is None:
            raise MatrixQuestionClaimNotFoundError
        locked_queue_item_id = await self.session.scalar(
            select(QueuedQuestionModel.id)
            .where(QueuedQuestionModel.id == queue_item_id)
            .with_for_update(),
        )
        if locked_queue_item_id is None:
            raise MatrixQuestionClaimNotFoundError
        released_queue_item_id = await self.session.scalar(
            delete(MatrixQuestionClaimModel)
            .where(
                MatrixQuestionClaimModel.id == claim_id,
                MatrixQuestionClaimModel.agent_client_id == agent_client_id,
                MatrixQuestionClaimModel.queue_item_id == queue_item_id,
                MatrixQuestionClaimModel.expires_at > released_at,
            )
            .returning(MatrixQuestionClaimModel.queue_item_id),
        )
        if released_queue_item_id is None:
            raise MatrixQuestionClaimNotFoundError
        await self.session.flush()
        return released_queue_item_id

    async def list_audit_events(
        self,
        *,
        params: AgentAuditEventPageQuery,
    ) -> tuple[AgentAuditEvent, ...]:
        stmt = (
            select(AgentAuditEventModel)
            .where(
                AgentAuditEventModel.agent_client_id == params.agent_client_id,
                AgentAuditEventModel.created_at >= params.created_at_from,
            )
            .order_by(
                AgentAuditEventModel.created_at.desc(),
                AgentAuditEventModel.id.desc(),
            )
            .limit(params.limit)
        )
        if params.cursor is not None:
            stmt = stmt.where(
                or_(
                    AgentAuditEventModel.created_at < params.cursor.created_at,
                    and_(
                        AgentAuditEventModel.created_at == params.cursor.created_at,
                        AgentAuditEventModel.id < params.cursor.event_id,
                    ),
                ),
            )
        events = await self.session.scalars(stmt)
        return tuple(event.to_domain_schema() for event in events)

    def _constraint_name(self, error: IntegrityError) -> str | None:
        candidates: tuple[Any, ...] = (
            error.orig,
            getattr(error.orig, "__cause__", None),
            getattr(error.orig, "__context__", None),
        )
        for candidate in candidates:
            for source in (candidate, getattr(candidate, "diag", None)):
                constraint_name = getattr(source, "constraint_name", None)
                if isinstance(constraint_name, str):
                    return constraint_name
        return None
