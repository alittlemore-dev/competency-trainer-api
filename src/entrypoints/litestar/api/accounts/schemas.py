from typing import Annotated

from pydantic import Field, field_validator

from core.account.schemas import (
    ManagedAccount,
    ManagedAccountCreateParams,
    ManagedAccountPasswordUpdateParams,
    ManagedAccountRoleUpdateParams,
    ManagedAccounts,
    ManagedAccountSession,
    ManagedAccountSessionRevocationResult,
    ManagedAccountSessions,
)
from core.auth.enums import RoleEnum
from core.schemas import Secret
from entrypoints.litestar.api.schemas import CamelCaseSchema
from entrypoints.litestar.api.validation import AccountPasswordString, AccountUsernameString


class ManagedAccountRoleMixin(CamelCaseSchema):
    role: Annotated[RoleEnum, Field(title="Managed account role")]

    @field_validator("role")
    @classmethod
    def validate_managed_role(cls, value: RoleEnum) -> RoleEnum:
        if value not in {RoleEnum.ADMIN, RoleEnum.MODERATOR}:
            msg = "role must be admin or moderator"
            raise ValueError(msg)
        return value


class ManagedAccountCreateRequestSchema(ManagedAccountRoleMixin):
    username: Annotated[AccountUsernameString, Field(title="Username")]
    password: Annotated[AccountPasswordString, Field(title="Password")]
    is_active: Annotated[bool, Field(title="Active")]

    def to_domain_schema(self) -> ManagedAccountCreateParams:
        return ManagedAccountCreateParams(
            username=self.username,
            role=self.role,
            password=Secret(self.password),
            is_active=self.is_active,
        )


class ManagedAccountRoleUpdateRequestSchema(ManagedAccountRoleMixin):
    def to_domain_schema(self) -> ManagedAccountRoleUpdateParams:
        return ManagedAccountRoleUpdateParams(role=self.role)


class ManagedAccountPasswordUpdateRequestSchema(CamelCaseSchema):
    password: Annotated[AccountPasswordString, Field(title="Password")]

    def to_domain_schema(self) -> ManagedAccountPasswordUpdateParams:
        return ManagedAccountPasswordUpdateParams(password=Secret(self.password))


class ManagedAccountResponseSchema(CamelCaseSchema):
    username: Annotated[str, Field(title="Username")]
    role: Annotated[RoleEnum, Field(title="Role")]
    is_active: Annotated[bool, Field(title="Active")]

    @classmethod
    def from_domain_schema(cls, *, schema: ManagedAccount) -> ManagedAccountResponseSchema:
        return cls.model_construct(
            username=schema.username,
            role=schema.role,
            is_active=schema.is_active,
        )


class ManagedAccountsResponseSchema(CamelCaseSchema):
    total_count: Annotated[int, Field(title="Total count")]
    total_pages: Annotated[int, Field(title="Total pages")]
    accounts: Annotated[list[ManagedAccountResponseSchema], Field(title="Accounts")]

    @classmethod
    def from_domain_schema(cls, *, schema: ManagedAccounts) -> ManagedAccountsResponseSchema:
        return cls.model_construct(
            total_count=schema.total_count,
            total_pages=schema.total_pages,
            accounts=[
                ManagedAccountResponseSchema.from_domain_schema(schema=account)
                for account in schema.values
            ],
        )


class ManagedAccountSessionResponseSchema(CamelCaseSchema):
    id: Annotated[str, Field(title="Session ID")]
    user_agent_display: Annotated[str, Field(title="User-agent display")]
    user_agent_browser: Annotated[str, Field(title="User-agent browser")]
    user_agent_os: Annotated[str, Field(title="User-agent OS")]
    user_agent_device: Annotated[str, Field(title="User-agent device")]
    auth_method: Annotated[str, Field(title="Authentication method")]
    created_at: Annotated[str, Field(title="Created at")]
    last_used_at: Annotated[str, Field(title="Last used at")]
    expires_at: Annotated[str, Field(title="Expires at")]
    is_current: Annotated[bool, Field(title="Current session")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: ManagedAccountSession,
    ) -> ManagedAccountSessionResponseSchema:
        return cls.model_construct(
            id=schema.id,
            user_agent_display=schema.client_metadata.user_agent_display,
            user_agent_browser=schema.client_metadata.user_agent_browser,
            user_agent_os=schema.client_metadata.user_agent_os,
            user_agent_device=schema.client_metadata.user_agent_device.value,
            auth_method=schema.auth_method.value,
            created_at=schema.created_at.isoformat(),
            last_used_at=schema.last_used_at.isoformat(),
            expires_at=schema.expires_at.isoformat(),
            is_current=schema.is_current,
        )


class ManagedAccountSessionsResponseSchema(CamelCaseSchema):
    sessions: Annotated[list[ManagedAccountSessionResponseSchema], Field(title="Sessions")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: ManagedAccountSessions,
    ) -> ManagedAccountSessionsResponseSchema:
        return cls.model_construct(
            sessions=[
                ManagedAccountSessionResponseSchema.from_domain_schema(schema=session)
                for session in schema.values
            ],
        )


class ManagedAccountSessionRevocationResponseSchema(CamelCaseSchema):
    current_session_revoked: Annotated[bool, Field(title="Current session revoked")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: ManagedAccountSessionRevocationResult,
    ) -> ManagedAccountSessionRevocationResponseSchema:
        return cls.model_construct(current_session_revoked=schema.current_session_revoked)
