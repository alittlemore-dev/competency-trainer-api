from datetime import datetime
from typing import Annotated

from pydantic import Field

from core.agent_access.enums import (
    AgentActionEnum,
    AgentAuditResultEnum,
    AgentClientStatusEnum,
    AgentScopeEnum,
)
from core.agent_access.schemas import (
    AgentAuditCursor,
    AgentAuditEvent,
    AgentAuditEventPage,
    AgentCertificate,
    AgentClientDetails,
    AgentClientRegisterParams,
    AgentClientRegistrationResult,
)
from entrypoints.litestar.api.schemas import CamelCaseSchema
from entrypoints.litestar.api.validation import RequiredShortText
from infra.config.constants import constants


class AgentCertificateResponseSchema(CamelCaseSchema):
    id: Annotated[str, Field(title="Certificate ID")]
    fingerprint_sha256: Annotated[str, Field(title="SHA-256 fingerprint")]
    serial_number: Annotated[str, Field(title="Serial number")]
    valid_from: Annotated[str, Field(title="Valid from")]
    expires_at: Annotated[str, Field(title="Expires at")]
    created_at: Annotated[str, Field(title="Created at")]
    revoked_at: Annotated[str | None, Field(title="Revoked at")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentCertificate,
    ) -> AgentCertificateResponseSchema:
        return cls.model_construct(
            id=schema.id,
            fingerprint_sha256=schema.fingerprint_sha256,
            serial_number=schema.serial_number,
            valid_from=schema.valid_from.isoformat(),
            expires_at=schema.expires_at.isoformat(),
            created_at=schema.created_at.isoformat(),
            revoked_at=schema.revoked_at.isoformat() if schema.revoked_at is not None else None,
        )


class AgentClientResponseSchema(CamelCaseSchema):
    id: Annotated[str, Field(title="Agent client ID")]
    name: Annotated[str, Field(title="Name")]
    status: Annotated[AgentClientStatusEnum, Field(title="Status")]
    scopes: Annotated[frozenset[AgentScopeEnum], Field(title="Scopes")]
    created_at: Annotated[str, Field(title="Created at")]
    revoked_at: Annotated[str | None, Field(title="Revoked at")]
    certificates: Annotated[list[AgentCertificateResponseSchema], Field(title="Certificates")]

    @classmethod
    def from_domain_schema(cls, *, schema: AgentClientDetails) -> AgentClientResponseSchema:
        return cls.model_construct(
            id=schema.client.id,
            name=schema.client.name,
            status=schema.client.status,
            scopes=schema.client.scopes,
            created_at=schema.client.created_at.isoformat(),
            revoked_at=(
                schema.client.revoked_at.isoformat()
                if schema.client.revoked_at is not None
                else None
            ),
            certificates=[
                AgentCertificateResponseSchema.from_domain_schema(schema=certificate)
                for certificate in schema.certificates
            ],
        )


class AgentClientsResponseSchema(CamelCaseSchema):
    clients: Annotated[list[AgentClientResponseSchema], Field(title="Agent clients")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schemas: list[AgentClientDetails],
    ) -> AgentClientsResponseSchema:
        return cls.model_construct(
            clients=[
                AgentClientResponseSchema.from_domain_schema(schema=schema) for schema in schemas
            ],
        )


class AgentClientRegisterRequestSchema(CamelCaseSchema):
    name: Annotated[RequiredShortText, Field(title="Name")]
    scopes: Annotated[
        frozenset[AgentScopeEnum],
        Field(title="Scopes", min_length=1, max_length=len(AgentScopeEnum)),
    ]
    csr_pem: Annotated[
        str,
        Field(
            title="PKCS#10 certificate signing request",
            min_length=1,
            max_length=constants.agent_access.csr_pem_max_length,
        ),
    ]

    def to_domain_schema(self, *, registered_at: datetime) -> AgentClientRegisterParams:
        return AgentClientRegisterParams(
            name=self.name,
            scopes=self.scopes,
            csr_pem=self.csr_pem,
            registered_at=registered_at,
        )


class AgentClientRegistrationResponseSchema(CamelCaseSchema):
    client: Annotated[AgentClientResponseSchema, Field(title="Agent client")]
    certificate_pem: Annotated[str, Field(title="Issued client certificate")]
    certificate_chain_pem: Annotated[str, Field(title="Certificate chain")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentClientRegistrationResult,
    ) -> AgentClientRegistrationResponseSchema:
        return cls.model_construct(
            client=AgentClientResponseSchema.from_domain_schema(
                schema=AgentClientDetails(
                    client=schema.client,
                    certificates=(schema.certificate,),
                ),
            ),
            certificate_pem=schema.certificate.certificate_pem,
            certificate_chain_pem=schema.certificate_chain_pem,
        )


class AgentAuditEventResponseSchema(CamelCaseSchema):
    id: Annotated[str, Field(title="Audit event ID")]
    agent_client_id: Annotated[str, Field(title="Agent client ID")]
    certificate_id: Annotated[str, Field(title="Certificate ID")]
    action: Annotated[AgentActionEnum, Field(title="Action")]
    queue_item_id: Annotated[str | None, Field(title="Queue item ID")]
    matrix_item_id: Annotated[str | None, Field(title="Matrix item ID")]
    request_id: Annotated[str, Field(title="Request ID")]
    result: Annotated[AgentAuditResultEnum, Field(title="Result")]
    input_digest: Annotated[str, Field(title="Input digest")]
    created_at: Annotated[str, Field(title="Created at")]

    @classmethod
    def from_domain_schema(cls, *, schema: AgentAuditEvent) -> AgentAuditEventResponseSchema:
        return cls.model_construct(
            id=schema.id,
            agent_client_id=schema.agent_client_id,
            certificate_id=schema.certificate_id,
            action=schema.action,
            queue_item_id=schema.queue_item_id,
            matrix_item_id=schema.matrix_item_id,
            request_id=schema.request_id,
            result=schema.result,
            input_digest=schema.input_digest,
            created_at=schema.created_at.isoformat(),
        )


class AgentAuditCursorResponseSchema(CamelCaseSchema):
    created_at: Annotated[str, Field(title="Cursor timestamp")]
    event_id: Annotated[str, Field(title="Cursor event ID")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentAuditCursor,
    ) -> AgentAuditCursorResponseSchema:
        return cls.model_construct(
            created_at=schema.created_at.isoformat(),
            event_id=schema.event_id,
        )


class AgentAuditEventsResponseSchema(CamelCaseSchema):
    events: Annotated[list[AgentAuditEventResponseSchema], Field(title="Audit events")]
    next_cursor: Annotated[
        AgentAuditCursorResponseSchema | None,
        Field(title="Next page cursor"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentAuditEventPage,
    ) -> AgentAuditEventsResponseSchema:
        return cls.model_construct(
            events=[
                AgentAuditEventResponseSchema.from_domain_schema(schema=event)
                for event in schema.events
            ],
            next_cursor=(
                AgentAuditCursorResponseSchema.from_domain_schema(schema=schema.next_cursor)
                if schema.next_cursor is not None
                else None
            ),
        )
