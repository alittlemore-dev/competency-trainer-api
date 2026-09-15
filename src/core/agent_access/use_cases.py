from dataclasses import dataclass
from datetime import datetime, timedelta

from core.agent_access.clients import AgentApiClient, AgentCertificateIssuer
from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.exceptions import (
    AgentCertificateRotationConflictError,
    AgentCertificateRotationNotFoundError,
    AgentClientNameConflictError,
    MatrixQuestionClaimNotFoundError,
)
from core.agent_access.schemas import (
    AgentAuditCleanupResult,
    AgentAuditCursor,
    AgentAuditEventCreateParams,
    AgentAuditEventPage,
    AgentAuditEventPageParams,
    AgentAuditEventPageQuery,
    AgentAuditPolicy,
    AgentCertificate,
    AgentCertificateIssueParams,
    AgentCertificatePolicy,
    AgentCertificateRotation,
    AgentCertificateRotationConfirmParams,
    AgentCertificateRotationParams,
    AgentCertificateRotationResult,
    AgentClient,
    AgentClientAuthenticationParams,
    AgentClientDetails,
    AgentClientRegisterParams,
    AgentClientRegistrationResult,
    AgentClientRevokeParams,
    AgentIdentity,
    AgentMatrixQuestionClaim,
    ExistingMatrixQuestionDraftResourceParams,
    LocalAgentCredentialRotationPolicy,
    MatrixAgentPolicy,
    MatrixAuthoringContext,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
    MatrixQuestionDraftResourceParams,
    MatrixQuestionDraftSaveParams,
    MatrixQuestionDraftSaveResult,
    PreparedLocalAgentCredentialRotation,
)
from core.agent_access.storages import (
    AgentAdminStorage,
    AgentAuditStorage,
    AgentCertificateRotationStorage,
    AgentIdentityStorage,
    LocalAgentCredentialRotationStorage,
    MatrixAgentStorage,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.schemas import (
    CompetencyMatrixItemCreateParams,
    CompetencyMatrixResourceSearchParams,
    ExistingExternalResourceAttachment,
    ExternalResources,
    NewExternalResourceAttachment,
)
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.enums import PublishStatusEnum
from core.generators import HexUuidIdGenerator


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentBridgeUseCase:
    client: AgentApiClient

    async def claim_next_matrix_question(self) -> AgentMatrixQuestionClaim:
        return await self.client.claim_next_matrix_question()

    async def get_matrix_authoring_context(self) -> MatrixAuthoringContext:
        return await self.client.get_matrix_authoring_context()

    async def search_matrix_resources(
        self,
        *,
        params: CompetencyMatrixResourceSearchParams,
    ) -> ExternalResources:
        return await self.client.search_matrix_resources(params=params)

    async def save_matrix_question_draft(
        self,
        *,
        params: MatrixQuestionDraftSaveParams,
    ) -> MatrixQuestionDraftSaveResult:
        return await self.client.save_matrix_question_draft(params=params)

    async def release_matrix_question_claim(self, *, claim_id: str) -> None:
        await self.client.release_matrix_question_claim(claim_id=claim_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class AutomaticAgentCredentialRotationUseCase:
    storage: LocalAgentCredentialRotationStorage
    client: AgentApiClient
    id_generator: HexUuidIdGenerator

    async def rotate_if_needed(
        self,
        *,
        current_datetime: datetime,
        policy: LocalAgentCredentialRotationPolicy,
    ) -> bool:
        pending = self.storage.load_pending_rotation()
        if pending is None:
            certificate_expires_at = self.storage.get_active_certificate_expires_at()
            if not policy.rotation_is_due(
                certificate_expires_at=certificate_expires_at,
                current_datetime=current_datetime,
            ):
                return False
            pending = self.storage.prepare_rotation(rotation_id=self.id_generator.get_next())
        if isinstance(pending, PreparedLocalAgentCredentialRotation):
            response = await self.client.start_certificate_rotation(
                params=pending.to_start_params(),
            )
            pending = self.storage.persist_replacement(
                pending=pending,
                response=response,
                current_datetime=current_datetime,
            )
        if not self.storage.is_rotation_active(rotation_id=pending.rotation_id):
            self.storage.activate_rotation(rotation=pending)
        confirmation = await self.client.confirm_certificate_rotation(
            rotation_id=pending.rotation_id,
        )
        confirmation.ensure_matches(rotation_id=pending.rotation_id)
        self.storage.complete_rotation(rotation=pending)
        return True


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAdminUseCase:
    storage: AgentAdminStorage
    certificate_issuer: AgentCertificateIssuer
    id_generator: HexUuidIdGenerator

    async def register_client(
        self,
        *,
        params: AgentClientRegisterParams,
        policy: AgentCertificatePolicy,
    ) -> AgentClientRegistrationResult:
        params.ensure_valid()
        if await self.storage.client_name_exists(normalized_name=params.normalized_name):
            raise AgentClientNameConflictError
        client = AgentClient(
            id=self.id_generator.get_next(),
            name=params.name.strip(),
            status=AgentClientStatusEnum.ACTIVE,
            scopes=params.scopes,
            created_at=params.registered_at,
            revoked_at=None,
        )
        issued = self.certificate_issuer.issue(
            params=AgentCertificateIssueParams(
                agent_client_id=client.id,
                csr_pem=params.csr_pem,
                valid_from=params.registered_at,
                expires_at=params.registered_at + timedelta(seconds=policy.lifetime_seconds),
            ),
        )
        certificate = AgentCertificate(
            id=self.id_generator.get_next(),
            agent_client_id=client.id,
            fingerprint_sha256=issued.fingerprint_sha256,
            serial_number=issued.serial_number,
            certificate_pem=issued.certificate_pem,
            valid_from=issued.valid_from,
            expires_at=issued.expires_at,
            created_at=params.registered_at,
            revoked_at=None,
        )
        await self.storage.create_client(client=client)
        await self.storage.create_certificate(certificate=certificate)
        return AgentClientRegistrationResult(
            client=client,
            certificate=certificate,
            certificate_chain_pem=issued.certificate_chain_pem,
        )

    async def list_client_details(self) -> list[AgentClientDetails]:
        clients = await self.storage.list_clients()
        return [
            AgentClientDetails(
                client=client,
                certificates=tuple(
                    await self.storage.list_certificates(agent_client_id=client.id),
                ),
            )
            for client in clients
        ]

    async def revoke_client(self, *, params: AgentClientRevokeParams) -> None:
        await self.storage.revoke_client(params=params)

    async def list_audit_events(
        self,
        *,
        params: AgentAuditEventPageParams,
        requested_at: datetime,
        policy: AgentAuditPolicy,
    ) -> AgentAuditEventPage:
        params.ensure_valid(maximum_page_size=policy.page_size_max)
        created_at_from = requested_at - timedelta(seconds=policy.retention_seconds)
        if params.cursor is not None and params.cursor.created_at < created_at_from:
            return AgentAuditEventPage(events=(), next_cursor=None)
        events = await self.storage.list_audit_events(
            params=AgentAuditEventPageQuery(
                agent_client_id=params.agent_client_id,
                limit=params.page_size + 1,
                cursor=params.cursor,
                created_at_from=created_at_from,
            ),
        )
        page_events = events[: params.page_size]
        next_cursor = None
        if len(events) > params.page_size:
            last_event = page_events[-1]
            next_cursor = AgentAuditCursor(
                created_at=last_event.created_at,
                event_id=last_event.id,
            )
        return AgentAuditEventPage(events=page_events, next_cursor=next_cursor)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditCleanupUseCase:
    storage: AgentAuditStorage

    async def prune_expired_audits(
        self,
        *,
        current_datetime: datetime,
        policy: AgentAuditPolicy,
    ) -> AgentAuditCleanupResult:
        deleted_count = await self.storage.prune_audit_events(
            created_at_before=current_datetime - timedelta(seconds=policy.retention_seconds),
        )
        return AgentAuditCleanupResult(deleted_count=deleted_count)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditUseCase:
    storage: AgentAuditStorage

    async def record(self, *, params: AgentAuditEventCreateParams) -> None:
        await self.storage.create_audit_event(params=params)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentIdentityUseCase:
    storage: AgentIdentityStorage

    async def authenticate_client(
        self,
        *,
        params: AgentClientAuthenticationParams,
    ) -> AgentIdentity:
        credential = await self.storage.get_credential_by_fingerprint(
            fingerprint_sha256=params.fingerprint_sha256,
        )
        return credential.authenticate_client(
            fingerprint_sha256=params.fingerprint_sha256,
            authenticated_at=params.authenticated_at,
        )

    async def authenticate_business_client(
        self,
        *,
        params: AgentClientAuthenticationParams,
    ) -> AgentIdentity:
        credential = await self.storage.get_credential_by_fingerprint(
            fingerprint_sha256=params.fingerprint_sha256,
        )
        return credential.authenticate_business_client(
            fingerprint_sha256=params.fingerprint_sha256,
            authenticated_at=params.authenticated_at,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotationUseCase:
    storage: AgentCertificateRotationStorage
    certificate_issuer: AgentCertificateIssuer
    id_generator: HexUuidIdGenerator

    async def rotate(
        self,
        *,
        identity: AgentIdentity,
        params: AgentCertificateRotationParams,
        policy: AgentCertificatePolicy,
    ) -> AgentCertificateRotationResult:
        params.ensure_valid()
        client = await self.storage.get_client_for_rotation(
            agent_client_id=identity.agent_client_id,
        )
        client.ensure_active()
        current_certificate = await self.storage.get_certificate_for_rotation(
            certificate_id=identity.certificate_id,
            agent_client_id=identity.agent_client_id,
        )
        csr_digest = params.csr_digest()
        existing_rotation = await self.storage.get_certificate_rotation(
            rotation_id=params.rotation_id,
        )
        if existing_rotation is not None:
            existing_rotation.ensure_request_matches(
                agent_client_id=identity.agent_client_id,
                current_certificate_id=current_certificate.id,
                csr_digest=csr_digest,
            )
            replacement = await self.storage.get_certificate_by_id(
                certificate_id=existing_rotation.replacement_certificate_id,
                agent_client_id=identity.agent_client_id,
            )
            result = AgentCertificateRotationResult(
                certificate=replacement,
                certificate_chain_pem=self.certificate_issuer.get_certificate_chain_pem(),
                replayed=True,
            )
            await self.storage.create_audit_event(
                params=AgentAuditEventCreateParams(
                    agent_client_id=identity.agent_client_id,
                    certificate_id=identity.certificate_id,
                    action=AgentActionEnum.ROTATE_AGENT_CERTIFICATE,
                    queue_item_id=None,
                    matrix_item_id=None,
                    request_id=params.rotation_id,
                    result=AgentAuditResultEnum.SUCCESS,
                    input_digest=csr_digest,
                    created_at=params.rotated_at,
                ),
            )
            return result
        current_certificate.ensure_rotation_allowed(
            rotated_at=params.rotated_at,
            rotation_window_seconds=policy.rotation_window_seconds,
        )
        pending_rotation = await self.storage.get_pending_certificate_rotation(
            current_certificate_id=current_certificate.id,
        )
        if pending_rotation is not None:
            raise AgentCertificateRotationConflictError
        issued = self.certificate_issuer.issue(
            params=AgentCertificateIssueParams(
                agent_client_id=identity.agent_client_id,
                csr_pem=params.csr_pem,
                valid_from=params.rotated_at,
                expires_at=params.rotated_at + timedelta(seconds=policy.lifetime_seconds),
            ),
        )
        certificate = AgentCertificate(
            id=self.id_generator.get_next(),
            agent_client_id=identity.agent_client_id,
            fingerprint_sha256=issued.fingerprint_sha256,
            serial_number=issued.serial_number,
            certificate_pem=issued.certificate_pem,
            valid_from=issued.valid_from,
            expires_at=issued.expires_at,
            created_at=params.rotated_at,
            revoked_at=None,
        )
        rotation = AgentCertificateRotation(
            rotation_id=params.rotation_id,
            agent_client_id=identity.agent_client_id,
            current_certificate_id=current_certificate.id,
            replacement_certificate_id=certificate.id,
            csr_digest=csr_digest,
            created_at=params.rotated_at,
            normal_access_until=params.rotated_at
            + timedelta(seconds=policy.normal_access_overlap_seconds),
            confirmed_at=None,
        )
        await self.storage.create_certificate_rotation(
            rotation=rotation,
            replacement=certificate,
        )
        result = AgentCertificateRotationResult(
            certificate=certificate,
            certificate_chain_pem=issued.certificate_chain_pem,
            replayed=False,
        )
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.ROTATE_AGENT_CERTIFICATE,
                queue_item_id=None,
                matrix_item_id=None,
                request_id=params.rotation_id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=csr_digest,
                created_at=params.rotated_at,
            ),
        )
        return result

    async def confirm(
        self,
        *,
        identity: AgentIdentity,
        params: AgentCertificateRotationConfirmParams,
    ) -> AgentCertificateRotation:
        params.ensure_valid()
        client = await self.storage.get_client_for_rotation(
            agent_client_id=identity.agent_client_id,
        )
        client.ensure_active()
        rotation = await self.storage.get_certificate_rotation(rotation_id=params.rotation_id)
        if rotation is None:
            raise AgentCertificateRotationNotFoundError
        rotation.ensure_confirmed_by(identity=identity)
        if rotation.confirmed_at is not None:
            await self.storage.create_audit_event(
                params=AgentAuditEventCreateParams(
                    agent_client_id=identity.agent_client_id,
                    certificate_id=identity.certificate_id,
                    action=AgentActionEnum.CONFIRM_AGENT_CERTIFICATE_ROTATION,
                    queue_item_id=None,
                    matrix_item_id=None,
                    request_id=params.rotation_id,
                    result=AgentAuditResultEnum.SUCCESS,
                    input_digest=params.input_digest(),
                    created_at=params.confirmed_at,
                ),
            )
            return rotation
        confirmed_rotation = await self.storage.confirm_certificate_rotation(
            rotation_id=rotation.rotation_id,
            current_certificate_id=rotation.current_certificate_id,
            confirmed_at=params.confirmed_at,
        )
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.CONFIRM_AGENT_CERTIFICATE_ROTATION,
                queue_item_id=None,
                matrix_item_id=None,
                request_id=params.rotation_id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=params.input_digest(),
                created_at=params.confirmed_at,
            ),
        )
        return confirmed_rotation


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixAgentUseCase:
    storage: MatrixAgentStorage
    matrix_storage: CompetencyMatrixStorage
    id_generator: HexUuidIdGenerator

    async def get_matrix_authoring_context(
        self,
        *,
        identity: AgentIdentity,
        request_id: str,
        input_digest: str,
        requested_at: datetime,
        policy: MatrixAgentPolicy,
    ) -> MatrixAuthoringContext:
        identity.ensure_scope(scope=AgentScopeEnum.MATRIX_CONTEXT_READ)
        context = MatrixAuthoringContext(
            structure=await self.matrix_storage.list_structure(),
            grades=tuple(GradeEnum),
            interview_frequencies=tuple(InterviewFrequencyEnum),
            minimum_resource_count=policy.minimum_resource_count,
            maximum_resource_count=policy.maximum_resource_count,
        )
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.GET_MATRIX_AUTHORING_CONTEXT,
                queue_item_id=None,
                matrix_item_id=None,
                request_id=request_id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=input_digest,
                created_at=requested_at,
            ),
        )
        return context

    async def search_matrix_resources(
        self,
        *,
        identity: AgentIdentity,
        params: CompetencyMatrixResourceSearchParams,
        request_id: str,
        input_digest: str,
        requested_at: datetime,
    ) -> ExternalResources:
        identity.ensure_scope(scope=AgentScopeEnum.MATRIX_RESOURCES_READ)
        resources = await self.matrix_storage.search_competency_matrix_resources(
            search_name=params.search_name.cleaned,
            limit=params.limit,
            language=params.language,
        )
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.SEARCH_MATRIX_RESOURCES,
                queue_item_id=None,
                matrix_item_id=None,
                request_id=request_id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=input_digest,
                created_at=requested_at,
            ),
        )
        return resources

    async def claim_next_matrix_question(
        self,
        *,
        identity: AgentIdentity,
        claimed_at: datetime,
        input_digest: str,
        policy: MatrixAgentPolicy,
    ) -> MatrixQuestionClaim:
        identity.ensure_scope(scope=AgentScopeEnum.MATRIX_QUEUE_CLAIM)
        claim = await self.storage.claim_next_matrix_question(
            agent_client_id=identity.agent_client_id,
            claimed_at=claimed_at,
            expires_at=claimed_at + timedelta(seconds=policy.claim_ttl_seconds),
        )
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.CLAIM_NEXT_MATRIX_QUESTION,
                queue_item_id=claim.question.id,
                matrix_item_id=None,
                request_id=claim.id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=input_digest,
                created_at=claimed_at,
            ),
        )
        return claim

    async def save_matrix_question_draft(
        self,
        *,
        identity: AgentIdentity,
        params: MatrixQuestionDraftSaveParams,
        completed_at: datetime,
        policy: MatrixAgentPolicy,
    ) -> MatrixQuestionDraftSaveResult:
        identity.ensure_scope(scope=AgentScopeEnum.MATRIX_DRAFT_CREATE)
        params.ensure_valid(
            minimum_resource_count=policy.minimum_resource_count,
            maximum_resource_count=policy.maximum_resource_count,
        )
        canonical_input_digest = params.canonical_digest()
        completion = await self.storage.get_matrix_question_draft_completion(
            claim_id=params.claim_id,
            agent_client_id=identity.agent_client_id,
        )
        if completion is not None:
            return completion.to_result(input_digest=canonical_input_digest)
        claim = await self.storage.lock_matrix_question_claim(
            agent_client_id=identity.agent_client_id,
            claim_id=params.claim_id,
        )
        completion = await self.storage.get_matrix_question_draft_completion(
            claim_id=params.claim_id,
            agent_client_id=identity.agent_client_id,
        )
        if completion is not None:
            return completion.to_result(input_digest=canonical_input_digest)
        if claim is None:
            raise MatrixQuestionClaimNotFoundError
        claim.ensure_completable(
            agent_client_id=identity.agent_client_id,
            completed_at=completed_at,
        )
        item_id = self.id_generator.get_next()
        attachments: list[ExistingExternalResourceAttachment | NewExternalResourceAttachment] = []
        for resource in params.resources:
            if isinstance(resource, ExistingMatrixQuestionDraftResourceParams):
                attachments.append(resource.to_attachment())
            elif isinstance(resource, MatrixQuestionDraftResourceParams):
                attachments.append(
                    resource.to_attachment(resource_id=self.id_generator.get_next()),
                )
        item_params = CompetencyMatrixItemCreateParams(
            id=item_id,
            slug=params.slug,
            question_ru=params.question_ru,
            question_en=params.question_en,
            publish_status=PublishStatusEnum.DRAFT,
            answer_ru=params.answer_ru,
            answer_en=params.answer_en,
            interview_answer_explanation_ru=params.interview_answer_explanation_ru,
            interview_answer_explanation_en=params.interview_answer_explanation_en,
            subsection_id=params.subsection_id,
            grade=params.grade,
            interview_frequency=params.interview_frequency,
            resources=attachments,
        )
        resource_ids = item_params.get_resource_ids_to_assign()
        resources = (
            await self.matrix_storage.get_resources_by_ids(resource_ids=resource_ids)
            if resource_ids
            else ExternalResources(values=[])
        )
        if not resources.all_resources_exists_by_ids(ids=set(resource_ids)):
            raise CompetencyMatrixItemNotFoundError
        structure = await self.matrix_storage.get_item_structure_by_subsection_id(
            subsection_id=item_params.subsection_id,
        )
        item = item_params.to_item(
            resources=resources,
            structure=structure,
            published_at=None,
            suggested_by_username=claim.question.suggested_by_username,
        )
        created_item = await self.matrix_storage.create_competency_matrix_item(item=item)
        completion = MatrixQuestionDraftCompletion(
            claim_id=claim.id,
            agent_client_id=identity.agent_client_id,
            queue_item_id=claim.question.id,
            matrix_item_id=created_item.id,
            input_digest=canonical_input_digest,
            completed_at=completed_at,
        )
        await self.storage.create_matrix_question_draft_completion(completion=completion)
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
                queue_item_id=claim.question.id,
                matrix_item_id=created_item.id,
                request_id=claim.id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=canonical_input_digest,
                created_at=completed_at,
            ),
        )
        await self.storage.consume_matrix_question_claim(
            agent_client_id=identity.agent_client_id,
            claim_id=claim.id,
            queue_item_id=claim.question.id,
        )
        return MatrixQuestionDraftSaveResult(item_id=created_item.id, replayed=False)

    async def release_matrix_question_claim(
        self,
        *,
        identity: AgentIdentity,
        claim_id: str,
        input_digest: str,
        released_at: datetime,
    ) -> None:
        identity.ensure_scope(scope=AgentScopeEnum.MATRIX_QUEUE_CLAIM)
        queue_item_id = await self.storage.release_matrix_question_claim(
            agent_client_id=identity.agent_client_id,
            claim_id=claim_id,
            released_at=released_at,
        )
        await self.storage.create_audit_event(
            params=AgentAuditEventCreateParams(
                agent_client_id=identity.agent_client_id,
                certificate_id=identity.certificate_id,
                action=AgentActionEnum.RELEASE_MATRIX_QUESTION_CLAIM,
                queue_item_id=queue_item_id,
                matrix_item_id=None,
                request_id=claim_id,
                result=AgentAuditResultEnum.SUCCESS,
                input_digest=input_digest,
                created_at=released_at,
            ),
        )
