from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Self

from core.account.enums import ManagedAccountActionEnum
from core.account.exceptions import (
    ManagedAccountActionForbiddenError,
    SelfAccountActionForbiddenError,
)
from core.auth.enums import AuthSessionAuthMethodEnum, RoleEnum
from core.auth.schemas import AuthSession, AuthSessionClientMetadata
from core.schemas import Secret, ValuedDataclass

SELF_FORBIDDEN_MANAGED_ACCOUNT_ACTIONS = (
    ManagedAccountActionEnum.UPDATE_ROLE,
    ManagedAccountActionEnum.ACTIVATE,
    ManagedAccountActionEnum.DEACTIVATE,
    ManagedAccountActionEnum.DELETE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccount:
    username: str
    role: RoleEnum
    is_active: bool

    @property
    def is_active_admin(self) -> bool:
        return self.is_active and self.role == RoleEnum.ADMIN

    @property
    def is_active_owner(self) -> bool:
        return self.is_active and self.role == RoleEnum.OWNER

    def ensure_can_manage_account(
        self,
        *,
        target: Self,
        action: ManagedAccountActionEnum,
    ) -> None:
        if (
            action in SELF_FORBIDDEN_MANAGED_ACCOUNT_ACTIONS
            and self.username.casefold() == target.username.casefold()
        ):
            raise SelfAccountActionForbiddenError
        if self.username.casefold() == target.username.casefold():
            return
        if self.role == RoleEnum.OWNER:
            return
        if self.role == RoleEnum.ADMIN and target.role == RoleEnum.MODERATOR:
            return
        raise ManagedAccountActionForbiddenError

    def ensure_can_create_account_with_role(self, *, role: RoleEnum) -> None:
        if self.role == RoleEnum.OWNER and role in {RoleEnum.ADMIN, RoleEnum.MODERATOR}:
            return
        if self.role == RoleEnum.ADMIN and role == RoleEnum.MODERATOR:
            return
        raise ManagedAccountActionForbiddenError

    def ensure_can_update_account_role(self, *, target: Self, role: RoleEnum) -> None:
        self.ensure_can_manage_account(
            target=target,
            action=ManagedAccountActionEnum.UPDATE_ROLE,
        )
        if self.role != RoleEnum.OWNER:
            raise ManagedAccountActionForbiddenError
        if role not in {RoleEnum.ADMIN, RoleEnum.MODERATOR}:
            raise ManagedAccountActionForbiddenError


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccounts(ValuedDataclass[ManagedAccount]):
    total_count: int
    total_pages: int

    @classmethod
    def from_page(
        cls,
        *,
        values: list[ManagedAccount],
        total_count: int,
        page_size: int,
    ) -> Self:
        return cls(
            values=values,
            total_count=total_count,
            total_pages=ceil(total_count / page_size) if total_count > 0 else 0,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountFilters:
    page: int
    page_size: int

    @property
    def limit(self) -> int:
        return self.page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountCreateParams:
    username: str
    role: RoleEnum
    password: Secret[str]
    is_active: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountCreateOperationParams:
    create_params: ManagedAccountCreateParams
    current_username: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountRoleUpdateParams:
    role: RoleEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountRoleUpdateOperationParams:
    target_username: str
    role_params: ManagedAccountRoleUpdateParams
    current_username: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountPasswordUpdateParams:
    password: Secret[str]


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountPasswordUpdateOperationParams:
    target_username: str
    password_params: ManagedAccountPasswordUpdateParams
    current_username: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountTargetOperationParams:
    target_username: str
    current_username: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountSessionsOperationParams:
    target_username: str
    current_username: str
    current_session_id: str
    current_datetime: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountSessionRevokeOperationParams:
    target_username: str
    current_username: str
    target_session_id: str
    current_session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountSessionsRevokeOthersOperationParams:
    target_username: str
    current_username: str
    current_session_id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountSession:
    id: str
    client_metadata: AuthSessionClientMetadata
    auth_method: AuthSessionAuthMethodEnum
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    is_current: bool

    @classmethod
    def from_auth_session(cls, *, session: AuthSession, current_session_id: str) -> Self:
        return cls(
            id=session.id,
            client_metadata=session.client_metadata,
            auth_method=session.auth_method,
            created_at=session.created_at,
            last_used_at=session.last_used_at,
            expires_at=session.expires_at,
            is_current=session.id == current_session_id,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountSessions(ValuedDataclass[ManagedAccountSession]):
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ManagedAccountSessionRevocationResult:
    current_session_revoked: bool
