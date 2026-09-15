from datetime import datetime
from typing import Self

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.schemas import (
    AgentAuditEvent,
    AgentCertificate,
    AgentCertificateRotation,
    AgentClient,
    MatrixQuestionClaim,
    MatrixQuestionDraftCompletion,
)
from core.competency_matrix.schemas import MatrixQuestionClaimSummary
from infra.postgresql.models.base import BaseModel, TableArgs
from infra.postgresql.models.competency_matrix import QueuedQuestionModel
from infra.postgresql.models.mixins.ids import HexUuidIDMixin


class AgentClientModel(HexUuidIDMixin, BaseModel):
    name: Mapped[str] = mapped_column(String(length=255), doc="Human-readable agent client name")
    status: Mapped[AgentClientStatusEnum] = mapped_column(
        Enum(AgentClientStatusEnum, native_enum=True, name="agent_client_status_enum"),
        doc="Permanent lifecycle status",
    )
    scopes: Mapped[list[AgentScopeEnum]] = mapped_column(
        ARRAY(Enum(AgentScopeEnum, native_enum=True, name="agent_scope_enum")),
        doc="Explicit capabilities assigned to the client",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Client registration timestamp",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Permanent revocation timestamp",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "agent_client_name_lower_uniq",
                func.lower(cls.name).label("name_lower"),
                unique=True,
            ),
            Index("agent_client_status_created_idx", cls.status, cls.created_at, cls.id),
        )

    @classmethod
    def from_domain_schema(cls, schema: AgentClient) -> Self:
        return cls(
            id=schema.id,
            name=schema.name,
            status=schema.status,
            scopes=list(schema.scopes),
            created_at=schema.created_at,
            revoked_at=schema.revoked_at,
        )

    def to_domain_schema(self) -> AgentClient:
        return AgentClient(
            id=self.id,
            name=self.name,
            status=self.status,
            scopes=frozenset(self.scopes),
            created_at=self.created_at,
            revoked_at=self.revoked_at,
        )


class AgentCertificateModel(HexUuidIDMixin, BaseModel):
    agent_client_id: Mapped[str] = mapped_column(
        ForeignKey(AgentClientModel.id, ondelete="RESTRICT"),
        doc="Owning agent client identifier",
    )
    fingerprint_sha256: Mapped[str] = mapped_column(
        String(length=64),
        unique=True,
        doc="Lowercase SHA-256 certificate fingerprint",
    )
    serial_number: Mapped[str] = mapped_column(
        String(length=64),
        unique=True,
        doc="CA-issued certificate serial number",
    )
    certificate_pem: Mapped[str] = mapped_column(Text(), doc="Public client certificate PEM")
    valid_from: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Certificate validity start",
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Certificate expiry timestamp",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Certificate issuance timestamp",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Certificate revocation timestamp",
    )

    client: Mapped[AgentClientModel] = relationship(doc="Owning agent client")

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "agent_certificate_client_expiry_idx",
                cls.agent_client_id,
                cls.expires_at,
                cls.id,
            ),
            Index(
                "agent_certificate_revoked_expiry_idx",
                cls.revoked_at,
                cls.expires_at,
                cls.id,
            ),
        )

    @classmethod
    def from_domain_schema(cls, schema: AgentCertificate) -> Self:
        return cls(
            id=schema.id,
            agent_client_id=schema.agent_client_id,
            fingerprint_sha256=schema.fingerprint_sha256,
            serial_number=schema.serial_number,
            certificate_pem=schema.certificate_pem,
            valid_from=schema.valid_from,
            expires_at=schema.expires_at,
            created_at=schema.created_at,
            revoked_at=schema.revoked_at,
        )

    def to_domain_schema(self) -> AgentCertificate:
        return AgentCertificate(
            id=self.id,
            agent_client_id=self.agent_client_id,
            fingerprint_sha256=self.fingerprint_sha256,
            serial_number=self.serial_number,
            certificate_pem=self.certificate_pem,
            valid_from=self.valid_from,
            expires_at=self.expires_at,
            created_at=self.created_at,
            revoked_at=self.revoked_at,
        )


class MatrixQuestionClaimModel(HexUuidIDMixin, BaseModel):
    agent_client_id: Mapped[str] = mapped_column(
        ForeignKey(AgentClientModel.id, ondelete="CASCADE"),
        doc="Claiming agent client identifier",
    )
    queue_item_id: Mapped[str] = mapped_column(
        ForeignKey(QueuedQuestionModel.id, ondelete="CASCADE"),
        doc="Claimed queue item identifier",
    )
    claimed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Lease creation timestamp",
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Lease expiry timestamp",
    )

    question: Mapped[QueuedQuestionModel] = relationship(doc="Claimed queue item")

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(cls.agent_client_id, name="matrix_question_claim_client_uniq"),
            UniqueConstraint(cls.queue_item_id, name="matrix_question_claim_queue_item_uniq"),
            Index("matrix_question_claim_expiry_idx", cls.expires_at, cls.id),
        )

    def to_domain_schema(self) -> MatrixQuestionClaim:
        return MatrixQuestionClaim(
            id=self.id,
            agent_client_id=self.agent_client_id,
            question=self.question.to_domain_schema(claim=None),
            claimed_at=self.claimed_at,
            expires_at=self.expires_at,
        )

    def to_summary(self, *, agent_client_name: str) -> MatrixQuestionClaimSummary:
        return MatrixQuestionClaimSummary(
            id=self.id,
            agent_client_id=self.agent_client_id,
            agent_client_name=agent_client_name,
            claimed_at=self.claimed_at,
            expires_at=self.expires_at,
        )


class MatrixQuestionDraftCompletionModel(BaseModel):
    claim_id: Mapped[str] = mapped_column(
        String(length=32),
        primary_key=True,
        doc="Immutable completed claim snapshot identifier",
    )
    agent_client_id: Mapped[str] = mapped_column(
        ForeignKey(AgentClientModel.id, ondelete="RESTRICT"),
        doc="Completing agent client identifier",
    )
    queue_item_id: Mapped[str] = mapped_column(
        String(length=32),
        doc="Consumed queue item snapshot identifier",
    )
    matrix_item_id: Mapped[str] = mapped_column(
        String(length=32),
        doc="Created Draft snapshot identifier",
    )
    input_digest: Mapped[str] = mapped_column(
        String(length=64),
        doc="Canonical Draft input digest",
    )
    completed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Draft completion timestamp",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "matrix_question_draft_completion_client_completed_idx",
                cls.agent_client_id,
                cls.completed_at,
                cls.claim_id,
            ),
        )

    @classmethod
    def from_domain_schema(cls, schema: MatrixQuestionDraftCompletion) -> Self:
        return cls(
            claim_id=schema.claim_id,
            agent_client_id=schema.agent_client_id,
            queue_item_id=schema.queue_item_id,
            matrix_item_id=schema.matrix_item_id,
            input_digest=schema.input_digest,
            completed_at=schema.completed_at,
        )

    def to_domain_schema(self) -> MatrixQuestionDraftCompletion:
        return MatrixQuestionDraftCompletion(
            claim_id=self.claim_id,
            agent_client_id=self.agent_client_id,
            queue_item_id=self.queue_item_id,
            matrix_item_id=self.matrix_item_id,
            input_digest=self.input_digest,
            completed_at=self.completed_at,
        )


class AgentCertificateRotationModel(BaseModel):
    rotation_id: Mapped[str] = mapped_column(
        String(length=255),
        primary_key=True,
        doc="Client-generated recoverable rotation identifier",
    )
    agent_client_id: Mapped[str] = mapped_column(
        ForeignKey(AgentClientModel.id, ondelete="RESTRICT"),
        doc="Rotating agent client identifier",
    )
    current_certificate_id: Mapped[str] = mapped_column(
        ForeignKey(AgentCertificateModel.id, ondelete="RESTRICT"),
        doc="Certificate authorizing the rotation",
    )
    replacement_certificate_id: Mapped[str] = mapped_column(
        ForeignKey(AgentCertificateModel.id, ondelete="RESTRICT"),
        doc="Recoverable replacement certificate identifier",
    )
    csr_digest: Mapped[str] = mapped_column(
        String(length=64),
        doc="SHA-256 digest of the replacement CSR",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Rotation creation timestamp",
    )
    normal_access_until: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Current certificate business-access overlap deadline",
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Replacement installation confirmation timestamp",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.replacement_certificate_id,
                name="agent_certificate_rotation_replacement_uniq",
            ),
            CheckConstraint(
                cls.current_certificate_id != cls.replacement_certificate_id,
                name="agent_certificate_rotation_distinct_certificates_check",
            ),
            Index(
                "agent_certificate_rotation_pending_current_uniq",
                cls.current_certificate_id,
                unique=True,
                postgresql_where=cls.confirmed_at.is_(None),
            ),
            Index(
                "agent_certificate_rotation_client_created_idx",
                cls.agent_client_id,
                cls.created_at,
                cls.rotation_id,
            ),
        )

    @classmethod
    def from_domain_schema(cls, schema: AgentCertificateRotation) -> Self:
        return cls(
            rotation_id=schema.rotation_id,
            agent_client_id=schema.agent_client_id,
            current_certificate_id=schema.current_certificate_id,
            replacement_certificate_id=schema.replacement_certificate_id,
            csr_digest=schema.csr_digest,
            created_at=schema.created_at,
            normal_access_until=schema.normal_access_until,
            confirmed_at=schema.confirmed_at,
        )

    def to_domain_schema(self) -> AgentCertificateRotation:
        return AgentCertificateRotation(
            rotation_id=self.rotation_id,
            agent_client_id=self.agent_client_id,
            current_certificate_id=self.current_certificate_id,
            replacement_certificate_id=self.replacement_certificate_id,
            csr_digest=self.csr_digest,
            created_at=self.created_at,
            normal_access_until=self.normal_access_until,
            confirmed_at=self.confirmed_at,
        )


class AgentAuditEventModel(HexUuidIDMixin, BaseModel):
    agent_client_id: Mapped[str] = mapped_column(
        ForeignKey(AgentClientModel.id, ondelete="RESTRICT"),
        doc="Acting agent client identifier",
    )
    certificate_id: Mapped[str] = mapped_column(
        ForeignKey(AgentCertificateModel.id, ondelete="RESTRICT"),
        doc="Authenticated certificate identifier when available",
    )
    action: Mapped[AgentActionEnum] = mapped_column(
        Enum(AgentActionEnum, native_enum=True, name="agent_action_enum"),
        doc="Closed-world agent action name",
    )
    queue_item_id: Mapped[str | None] = mapped_column(
        String(length=32),
        doc="Queue item snapshot identifier",
    )
    matrix_item_id: Mapped[str | None] = mapped_column(
        String(length=32),
        doc="Created matrix Draft identifier snapshot",
    )
    request_id: Mapped[str] = mapped_column(String(length=255), doc="Request or claim identifier")
    result: Mapped[AgentAuditResultEnum] = mapped_column(
        Enum(AgentAuditResultEnum, native_enum=True, name="agent_audit_result_enum"),
        doc="Action result",
    )
    input_digest: Mapped[str] = mapped_column(
        String(length=64),
        doc="SHA-256 digest of normalized input",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Audit event timestamp",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "agent_audit_client_created_idx",
                cls.agent_client_id,
                cls.created_at,
                cls.id,
            ),
            Index(
                "agent_audit_action_result_created_idx",
                cls.action,
                cls.result,
                cls.created_at,
                cls.id,
            ),
            Index("agent_audit_created_idx", cls.created_at, cls.id),
        )

    def to_domain_schema(self) -> AgentAuditEvent:
        return AgentAuditEvent(
            id=self.id,
            agent_client_id=self.agent_client_id,
            certificate_id=self.certificate_id,
            action=self.action,
            queue_item_id=self.queue_item_id,
            matrix_item_id=self.matrix_item_id,
            request_id=self.request_id,
            result=self.result,
            input_digest=self.input_digest,
            created_at=self.created_at,
        )
