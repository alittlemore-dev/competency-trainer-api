import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from ipaddress import ip_address
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

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
    AgentClientValidationError,
    AgentIdempotencyConflictError,
    AgentKnownAuthenticationError,
    AgentScopeDeniedError,
    MatrixQuestionClaimNotFoundError,
    MatrixQuestionDraftValidationError,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import (
    CompetencyMatrixStructure,
    ExistingExternalResourceAttachment,
    ExternalResource,
    NewExternalResourceAttachment,
    QueuedCompetencyMatrixQuestion,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificatePolicy:
    lifetime_seconds: int
    rotation_window_seconds: int
    normal_access_overlap_seconds: int

    def __post_init__(self) -> None:
        if not (
            0
            < self.normal_access_overlap_seconds
            < self.rotation_window_seconds
            < self.lifetime_seconds
        ):
            msg = "certificate policy values must satisfy 0 < overlap < window < lifetime"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditPolicy:
    page_size_max: int
    retention_seconds: int

    def __post_init__(self) -> None:
        if self.page_size_max <= 0 or self.retention_seconds <= 0:
            msg = "audit policy values must be positive"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixAgentPolicy:
    claim_ttl_seconds: int
    minimum_resource_count: int
    maximum_resource_count: int

    def __post_init__(self) -> None:
        if (
            self.claim_ttl_seconds <= 0
            or self.minimum_resource_count <= 0
            or self.minimum_resource_count > self.maximum_resource_count
        ):
            msg = "matrix agent policy values must be positive and ordered"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class LocalAgentCredentialRotationPolicy:
    rotation_window_seconds: int

    def __post_init__(self) -> None:
        if self.rotation_window_seconds <= 0:
            msg = "local credential rotation window must be positive"
            raise ValueError(msg)

    def rotation_is_due(
        self,
        *,
        certificate_expires_at: datetime,
        current_datetime: datetime,
    ) -> bool:
        return certificate_expires_at <= current_datetime + timedelta(
            seconds=self.rotation_window_seconds,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClient:
    id: str
    name: str
    status: AgentClientStatusEnum
    scopes: frozenset[AgentScopeEnum]
    created_at: datetime
    revoked_at: datetime | None

    def ensure_active(self) -> None:
        if self.status != AgentClientStatusEnum.ACTIVE or self.revoked_at is not None:
            raise AgentAuthenticationError

    def ensure_scope(self, *, scope: AgentScopeEnum) -> None:
        if scope not in self.scopes:
            raise AgentScopeDeniedError


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificate:
    id: str
    agent_client_id: str
    fingerprint_sha256: str
    serial_number: str
    certificate_pem: str
    valid_from: datetime
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None

    def ensure_active(self, *, authenticated_at: datetime) -> None:
        if (
            self.revoked_at is not None
            or self.valid_from > authenticated_at
            or self.expires_at <= authenticated_at
        ):
            raise AgentAuthenticationError

    def ensure_rotation_allowed(
        self,
        *,
        rotated_at: datetime,
        rotation_window_seconds: int,
    ) -> None:
        self.ensure_active(authenticated_at=rotated_at)
        if self.expires_at > rotated_at + timedelta(seconds=rotation_window_seconds):
            raise AgentClientValidationError


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCredential:
    client: AgentClient
    certificate: AgentCertificate
    normal_access_until: datetime | None

    def authenticate_client(
        self,
        *,
        fingerprint_sha256: str,
        authenticated_at: datetime,
    ) -> AgentIdentity:
        try:
            self.client.ensure_active()
            self.certificate.ensure_active(authenticated_at=authenticated_at)
        except AgentAuthenticationError as error:
            raise AgentKnownAuthenticationError(
                agent_client_id=self.client.id,
                certificate_id=self.certificate.id,
            ) from error
        if (
            self.certificate.agent_client_id != self.client.id
            or self.certificate.fingerprint_sha256 != fingerprint_sha256
        ):
            raise AgentKnownAuthenticationError(
                agent_client_id=self.client.id,
                certificate_id=self.certificate.id,
            )
        return AgentIdentity(
            agent_client_id=self.client.id,
            agent_client_name=self.client.name,
            certificate_id=self.certificate.id,
            scopes=self.client.scopes,
        )

    def authenticate_business_client(
        self,
        *,
        fingerprint_sha256: str,
        authenticated_at: datetime,
    ) -> AgentIdentity:
        identity = self.authenticate_client(
            fingerprint_sha256=fingerprint_sha256,
            authenticated_at=authenticated_at,
        )
        if self.normal_access_until is not None and self.normal_access_until <= authenticated_at:
            raise AgentKnownAuthenticationError(
                agent_client_id=self.client.id,
                certificate_id=self.certificate.id,
            )
        return identity


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentIdentity:
    agent_client_id: str
    agent_client_name: str
    certificate_id: str
    scopes: frozenset[AgentScopeEnum]

    def ensure_scope(self, *, scope: AgentScopeEnum) -> None:
        if scope not in self.scopes:
            raise AgentScopeDeniedError


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClientAuthenticationParams:
    fingerprint_sha256: str
    authenticated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixQuestionClaim:
    id: str
    agent_client_id: str
    question: QueuedCompetencyMatrixQuestion
    claimed_at: datetime
    expires_at: datetime

    def ensure_completable(self, *, agent_client_id: str, completed_at: datetime) -> None:
        if self.agent_client_id != agent_client_id or self.expires_at <= completed_at:
            raise MatrixQuestionClaimNotFoundError


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentMatrixQuestionClaim:
    claim_id: str
    queue_item_id: str
    question: str
    grade: GradeEnum | None
    sheet: str | None
    section: str | None
    subsection: str | None
    suggested_by_username: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixQuestionDraftResourceParams:
    name_ru: str
    name_en: str
    url: str
    context_ru: str
    context_en: str

    def ensure_valid(self) -> None:
        if not all(
            value.strip()
            for value in (self.name_ru, self.name_en, self.context_ru, self.context_en)
        ):
            raise MatrixQuestionDraftValidationError
        parsed_url = urlsplit(self.url)
        try:
            parsed_port = parsed_url.port
        except ValueError as error:
            raise MatrixQuestionDraftValidationError from error
        if (
            parsed_url.scheme != "https"
            or parsed_url.hostname is None
            or parsed_url.username is not None
            or parsed_url.password is not None
            or (parsed_port is not None and parsed_port <= 0)
        ):
            raise MatrixQuestionDraftValidationError
        try:
            ip_address(parsed_url.hostname)
        except ValueError:
            return
        raise MatrixQuestionDraftValidationError

    def canonical_payload(self) -> dict[str, str]:
        return {
            "kind": "new",
            "name_en": self.name_en,
            "name_ru": self.name_ru,
            "url": self.url,
            "context_en": self.context_en,
            "context_ru": self.context_ru,
        }

    def to_attachment(self, *, resource_id: str) -> NewExternalResourceAttachment:
        return NewExternalResourceAttachment(
            resource=ExternalResource(
                id=resource_id,
                name_ru=self.name_ru,
                name_en=self.name_en,
                url=self.url,
            ),
            context_ru=self.context_ru,
            context_en=self.context_en,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExistingMatrixQuestionDraftResourceParams:
    resource_id: str
    context_ru: str
    context_en: str

    def ensure_valid(self) -> None:
        if (
            not self.resource_id.strip()
            or not self.context_ru.strip()
            or not self.context_en.strip()
        ):
            raise MatrixQuestionDraftValidationError

    def canonical_payload(self) -> dict[str, str]:
        return {
            "kind": "existing",
            "resource_id": self.resource_id,
            "context_en": self.context_en,
            "context_ru": self.context_ru,
        }

    def to_attachment(self) -> ExistingExternalResourceAttachment:
        return ExistingExternalResourceAttachment(
            resource_id=self.resource_id,
            context_ru=self.context_ru,
            context_en=self.context_en,
        )


MatrixQuestionDraftResourceAttachmentParams = (
    ExistingMatrixQuestionDraftResourceParams | MatrixQuestionDraftResourceParams
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixQuestionDraftSaveParams:
    claim_id: str
    slug: str
    subsection_id: str
    grade: GradeEnum
    interview_frequency: InterviewFrequencyEnum
    question_ru: str
    question_en: str
    answer_ru: str
    answer_en: str
    interview_answer_explanation_ru: str
    interview_answer_explanation_en: str
    resources: tuple[MatrixQuestionDraftResourceAttachmentParams, ...]

    def ensure_valid(self, *, minimum_resource_count: int, maximum_resource_count: int) -> None:
        if not minimum_resource_count <= len(self.resources) <= maximum_resource_count:
            raise MatrixQuestionDraftValidationError
        if not all(
            value.strip()
            for value in (
                self.claim_id,
                self.slug,
                self.subsection_id,
                self.question_ru,
                self.question_en,
                self.answer_ru,
                self.answer_en,
                self.interview_answer_explanation_ru,
                self.interview_answer_explanation_en,
            )
        ):
            raise MatrixQuestionDraftValidationError
        for resource in self.resources:
            resource.ensure_valid()
        existing_resource_ids = [
            resource.resource_id
            for resource in self.resources
            if isinstance(resource, ExistingMatrixQuestionDraftResourceParams)
        ]
        if len(existing_resource_ids) != len(set(existing_resource_ids)):
            raise MatrixQuestionDraftValidationError

    def canonical_digest(self) -> str:
        payload: dict[str, Any] = {
            "answer_en": self.answer_en,
            "answer_ru": self.answer_ru,
            "claim_id": self.claim_id,
            "grade": self.grade.value,
            "interview_answer_explanation_en": self.interview_answer_explanation_en,
            "interview_answer_explanation_ru": self.interview_answer_explanation_ru,
            "interview_frequency": self.interview_frequency.value,
            "question_en": self.question_en,
            "question_ru": self.question_ru,
            "resources": sorted(
                (resource.canonical_payload() for resource in self.resources),
                key=lambda resource: json.dumps(
                    resource,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
            "slug": self.slug,
            "subsection_id": self.subsection_id,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixQuestionDraftSaveResult:
    item_id: str
    replayed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixQuestionDraftCompletion:
    claim_id: str
    agent_client_id: str
    queue_item_id: str
    matrix_item_id: str
    input_digest: str
    completed_at: datetime

    def to_result(self, *, input_digest: str) -> MatrixQuestionDraftSaveResult:
        if self.input_digest != input_digest:
            raise AgentIdempotencyConflictError
        return MatrixQuestionDraftSaveResult(item_id=self.matrix_item_id, replayed=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class MatrixAuthoringContext:
    structure: CompetencyMatrixStructure
    grades: tuple[GradeEnum, ...]
    interview_frequencies: tuple[InterviewFrequencyEnum, ...]
    minimum_resource_count: int
    maximum_resource_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditEvent:
    id: str
    agent_client_id: str
    certificate_id: str
    action: AgentActionEnum
    queue_item_id: str | None
    matrix_item_id: str | None
    request_id: str
    result: AgentAuditResultEnum
    input_digest: str
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditEventCreateParams:
    agent_client_id: str
    certificate_id: str
    action: AgentActionEnum
    queue_item_id: str | None
    matrix_item_id: str | None
    request_id: str
    result: AgentAuditResultEnum
    input_digest: str
    created_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditCursor:
    created_at: datetime
    event_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditEventPageParams:
    agent_client_id: str
    page_size: int
    cursor: AgentAuditCursor | None

    def ensure_valid(self, *, maximum_page_size: int) -> None:
        if not self.agent_client_id.strip() or not 1 <= self.page_size <= maximum_page_size:
            raise AgentAuditPaginationError
        if self.cursor is not None and not self.cursor.event_id.strip():
            raise AgentAuditPaginationError


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditEventPageQuery:
    agent_client_id: str
    limit: int
    cursor: AgentAuditCursor | None
    created_at_from: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditEventPage:
    events: tuple[AgentAuditEvent, ...]
    next_cursor: AgentAuditCursor | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentAuditCleanupResult:
    deleted_count: int

    def as_dict(self) -> dict[str, int]:
        return {"deletedCount": self.deleted_count}


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateIssueParams:
    agent_client_id: str
    csr_pem: str
    valid_from: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedAgentCertificate:
    certificate_pem: str
    certificate_chain_pem: str
    fingerprint_sha256: str
    serial_number: str
    valid_from: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClientRegisterParams:
    name: str
    scopes: frozenset[AgentScopeEnum]
    csr_pem: str
    registered_at: datetime

    def ensure_valid(self) -> None:
        if not self.name.strip() or not self.csr_pem.strip() or not self.scopes:
            raise AgentClientValidationError

    @property
    def normalized_name(self) -> str:
        return self.name.strip().casefold()


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClientRegistrationResult:
    client: AgentClient
    certificate: AgentCertificate
    certificate_chain_pem: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotationParams:
    rotation_id: str
    csr_pem: str
    rotated_at: datetime

    def ensure_valid(self) -> None:
        if not self.rotation_id.strip() or not self.csr_pem.strip():
            raise AgentClientValidationError

    def csr_digest(self) -> str:
        return hashlib.sha256(self.csr_pem.encode()).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotation:
    rotation_id: str
    agent_client_id: str
    current_certificate_id: str
    replacement_certificate_id: str
    csr_digest: str
    created_at: datetime
    normal_access_until: datetime
    confirmed_at: datetime | None

    def ensure_request_matches(
        self,
        *,
        agent_client_id: str,
        current_certificate_id: str,
        csr_digest: str,
    ) -> None:
        if (
            self.agent_client_id != agent_client_id
            or self.current_certificate_id != current_certificate_id
            or self.csr_digest != csr_digest
        ):
            raise AgentIdempotencyConflictError

    def ensure_confirmed_by(self, *, identity: AgentIdentity) -> None:
        if (
            identity.agent_client_id != self.agent_client_id
            or identity.certificate_id != self.replacement_certificate_id
        ):
            raise AgentCertificateRotationConfirmationError


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotationConfirmParams:
    rotation_id: str
    confirmed_at: datetime

    def ensure_valid(self) -> None:
        if not self.rotation_id.strip():
            raise AgentClientValidationError

    def input_digest(self) -> str:
        return hashlib.sha256(self.rotation_id.encode()).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotationResult:
    certificate: AgentCertificate
    certificate_chain_pem: str
    replayed: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotationStartParams:
    rotation_id: str
    csr_pem: str

    def __post_init__(self) -> None:
        if (
            len(self.rotation_id) != len(UUID(int=0).hex)
            or any(character not in "0123456789abcdef" for character in self.rotation_id)
            or not self.csr_pem.strip()
        ):
            msg = "local certificate rotation request is invalid"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClientCertificateRotation:
    certificate_pem: str
    certificate_chain_pem: str
    fingerprint_sha256: str
    serial_number: str
    valid_from: datetime
    expires_at: datetime
    replayed: bool

    def __post_init__(self) -> None:
        if (
            not self.certificate_pem.strip()
            or not self.certificate_chain_pem.strip()
            or len(self.fingerprint_sha256) != len(hashlib.sha256().hexdigest())
            or any(character not in "0123456789abcdef" for character in self.fingerprint_sha256)
            or not self.serial_number
            or any(character not in "0123456789abcdef" for character in self.serial_number)
            or self.valid_from >= self.expires_at
        ):
            msg = "issued local certificate rotation is invalid"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentCertificateRotationConfirmation:
    rotation_id: str
    confirmed_at: datetime

    def __post_init__(self) -> None:
        if len(self.rotation_id) != len(UUID(int=0).hex) or any(
            character not in "0123456789abcdef" for character in self.rotation_id
        ):
            msg = "local certificate rotation confirmation is invalid"
            raise ValueError(msg)

    def ensure_matches(self, *, rotation_id: str) -> None:
        if self.rotation_id != rotation_id:
            raise AgentCertificateRotationConfirmationError


@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedLocalAgentCredentialRotation:
    rotation_id: str
    previous_version_id: str
    csr_pem: str

    def __post_init__(self) -> None:
        if (
            len(self.rotation_id) != len(UUID(int=0).hex)
            or any(character not in "0123456789abcdef" for character in self.rotation_id)
            or len(self.previous_version_id) != len(UUID(int=0).hex)
            or any(character not in "0123456789abcdef" for character in self.previous_version_id)
            or self.rotation_id == self.previous_version_id
            or not self.csr_pem.strip()
        ):
            msg = "prepared local credential rotation is invalid"
            raise ValueError(msg)

    def to_start_params(self) -> AgentCertificateRotationStartParams:
        return AgentCertificateRotationStartParams(
            rotation_id=self.rotation_id,
            csr_pem=self.csr_pem,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class IssuedLocalAgentCredentialRotation:
    rotation_id: str
    previous_version_id: str
    csr_pem: str
    fingerprint_sha256: str
    serial_number: str
    valid_from: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        PreparedLocalAgentCredentialRotation(
            rotation_id=self.rotation_id,
            previous_version_id=self.previous_version_id,
            csr_pem=self.csr_pem,
        )
        if (
            len(self.fingerprint_sha256) != len(hashlib.sha256().hexdigest())
            or any(character not in "0123456789abcdef" for character in self.fingerprint_sha256)
            or not self.serial_number
            or any(character not in "0123456789abcdef" for character in self.serial_number)
            or self.valid_from >= self.expires_at
        ):
            msg = "persisted local credential rotation is invalid"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClientRevokeParams:
    agent_client_id: str
    revoked_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AgentClientDetails:
    client: AgentClient
    certificates: tuple[AgentCertificate, ...]
