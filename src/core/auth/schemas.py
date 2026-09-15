from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.types import SessionSecret, SessionSecretHash, Token
from core.schemas import Secret, ValuedDataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class TokenPayloadValidationResult:
    is_valid: bool
    message: str


@dataclass(frozen=True, slots=True, kw_only=True)
class BaseUser:
    username: str
    role: RoleEnum

    @property
    def is_anon(self) -> bool:
        return self.role == RoleEnum.ANON

    @property
    def is_owner(self) -> bool:
        return self.role == RoleEnum.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role == RoleEnum.ADMIN

    @property
    def is_moderator(self) -> bool:
        return self.role == RoleEnum.MODERATOR

    @property
    def is_user(self) -> bool:
        return self.role == RoleEnum.USER

    @property
    def can_manage_content(self) -> bool:
        return self.role in {RoleEnum.OWNER, RoleEnum.ADMIN, RoleEnum.MODERATOR}

    @property
    def can_manage_team(self) -> bool:
        return self.role in {RoleEnum.OWNER, RoleEnum.ADMIN}

    def has_role(self, role: RoleEnum) -> bool:
        if self.role == RoleEnum.OWNER:
            return True
        if self.role == RoleEnum.ADMIN:
            return role in {RoleEnum.ANON, RoleEnum.USER, RoleEnum.MODERATOR, RoleEnum.ADMIN}
        if self.role == RoleEnum.MODERATOR:
            return role in {RoleEnum.ANON, RoleEnum.USER, RoleEnum.MODERATOR}
        if self.role == RoleEnum.USER:
            return role in {RoleEnum.ANON, RoleEnum.USER}
        return self.role == role


@dataclass(frozen=True, slots=True, kw_only=True)
class User(BaseUser):
    password_hash: Secret[str]
    is_active: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class JwtUser(BaseUser):
    def to_dict(self) -> dict[str, Any]:
        return {"username": self.username, "role": self.role.value}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> JwtUser:
        return cls(
            username=payload["username"],
            role=RoleEnum.from_value(payload["role"]),
        )

    @classmethod
    def from_user(cls, user: User) -> JwtUser:
        return cls(
            username=user.username,
            role=user.role,
        )

    @classmethod
    def anonymous(cls) -> JwtUser:
        return cls(username="anonymous", role=RoleEnum.ANON)


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessTokenPayload:
    username: str
    session_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"username": self.username, "session_id": self.session_id}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AccessTokenPayload:
        return cls(
            username=payload["username"],
            session_id=payload["session_id"],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AccessTokenResult:
    token: Token
    expires_in_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCredentials:
    secret: SessionSecret
    expires_in_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthLoginResult:
    access_token: AccessTokenResult
    session: AuthSessionCredentials


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthRefreshAccessTokenResult:
    access_token: AccessTokenResult
    session: AuthSessionCredentials


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCleanupParams:
    current_datetime: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCleanupPolicy:
    expiring_soon_days: int
    scheduled_prune_interval_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCleanupCounts:
    expired_count: int
    expiring_soon_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCleanupStatus:
    expired_count: int
    expiring_soon_count: int
    expiring_soon_days: int
    scheduled_prune_interval_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCleanupResult(AuthSessionCleanupStatus):
    deleted_count: int

    def as_dict(self) -> dict[str, int]:
        return {
            "deletedCount": self.deleted_count,
            "expiredCount": self.expired_count,
            "expiringSoonCount": self.expiring_soon_count,
            "expiringSoonDays": self.expiring_soon_days,
            "scheduledPruneIntervalSeconds": self.scheduled_prune_interval_seconds,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthUseCaseConfig:
    access_token_expires_in_seconds: int
    session_expires_in_seconds: int
    session_absolute_expires_in_seconds: int


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionClientMetadata:
    user_agent_display: str
    user_agent_browser: str
    user_agent_os: str
    user_agent_device: AuthSessionDeviceTypeEnum

    @classmethod
    def create(
        cls,
        *,
        browser: object,
        operating_system: object,
        device_type: str | None,
    ) -> AuthSessionClientMetadata:
        browser_label = cls._label(value=browser, unknown_label="Unknown browser")
        os_label = cls._label(value=operating_system, unknown_label="Unknown OS")
        return cls(
            user_agent_display=(
                f"{browser_label} on {os_label}"
                if browser_label != "Unknown browser" and os_label != "Unknown OS"
                else "Unknown device"
            ),
            user_agent_browser=browser_label,
            user_agent_os=os_label,
            user_agent_device=AuthSessionDeviceTypeEnum.from_device_type(device_type),
        )

    @classmethod
    def empty(cls) -> AuthSessionClientMetadata:
        return cls(
            user_agent_display="Unknown device",
            user_agent_browser="Unknown browser",
            user_agent_os="Unknown OS",
            user_agent_device=AuthSessionDeviceTypeEnum.UNKNOWN,
        )

    @classmethod
    def _label(cls, *, value: object, unknown_label: str) -> str:
        if not isinstance(value, str):
            return unknown_label
        label = value.strip()
        if label == "" or label.casefold() in {"other", "unknown"}:
            return unknown_label
        return label


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthLoginParams:
    username: str
    password: str
    required_role: RoleEnum
    current_datetime: datetime
    client_metadata: AuthSessionClientMetadata


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthAuthenticateParams:
    token: Token
    required_role: RoleEnum
    current_datetime: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthRefreshAccessTokenParams:
    session_secret: SessionSecret
    required_role: RoleEnum
    current_datetime: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthLogoutParams:
    token: Token
    session_secret: SessionSecret | None


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionCreate:
    username: str
    secret_hash: SessionSecretHash
    expires_at: datetime
    absolute_expires_at: datetime
    is_revoked: bool
    last_used_at: datetime
    auth_method: AuthSessionAuthMethodEnum
    client_metadata: AuthSessionClientMetadata


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSession:
    id: str
    username: str
    secret_hash: SessionSecretHash
    expires_at: datetime
    absolute_expires_at: datetime
    is_revoked: bool
    created_at: datetime
    last_used_at: datetime
    auth_method: AuthSessionAuthMethodEnum
    client_metadata: AuthSessionClientMetadata

    def is_active_at(self, *, now: datetime) -> bool:
        return not self.is_revoked and self.expires_at > now and self.absolute_expires_at > now

    def refreshed_expires_at(self, *, now: datetime, idle_expires_in_seconds: int) -> datetime:
        return min(
            now + timedelta(seconds=idle_expires_in_seconds),
            self.absolute_expires_at,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessions(ValuedDataclass[AuthSession]):
    pass
