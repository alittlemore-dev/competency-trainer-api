from datetime import datetime
from typing import Self

from sqlalchemy import Boolean, Enum, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy_dev_utils.mixins.audit import AuditMixin
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

from core.account.schemas import ManagedAccount
from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.schemas import AuthSession, AuthSessionClientMetadata, User
from core.auth.types import SessionSecretHash
from core.schemas import Secret
from infra.postgresql.models.base import BaseModel, TableArgs
from infra.postgresql.models.mixins.ids import HexUuidIDMixin


class UserModel(BaseModel):
    username: Mapped[str] = mapped_column(
        String(255),
        doc="Username",
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(
        String(127),
        doc="User password hash",
    )
    role: Mapped[RoleEnum] = mapped_column(
        Enum(RoleEnum, native_enum=True, name="role_enum"),
        doc="User role",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        doc="Whether the user may authenticate",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index("users_username_idx", cls.username),
            Index(
                "users_username_lower_uniq",
                func.lower(cls.username).label("username_lower"),
                unique=True,
            ),
            Index(
                "users_managed_accounts_list_idx",
                cls.role,
                func.lower(cls.username).label("username_lower"),
                cls.username,
            ),
            Index(
                "users_single_owner_uniq",
                cls.role,
                unique=True,
                postgresql_where=cls.role == RoleEnum.OWNER,
            ),
        )

    def to_domain_schema(self) -> User:
        return User(
            username=self.username,
            password_hash=Secret(self.password_hash),
            role=self.role,
            is_active=self.is_active,
        )

    def to_managed_account_schema(self) -> ManagedAccount:
        return ManagedAccount(
            username=self.username,
            role=self.role,
            is_active=self.is_active,
        )

    @classmethod
    def from_domain_schema(cls, schema: User) -> UserModel:
        return cls(
            username=schema.username,
            password_hash=schema.password_hash.get_secret_value(),
            role=schema.role,
            is_active=schema.is_active,
        )


class AuthSessionModel(HexUuidIDMixin, AuditMixin, BaseModel):
    username: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("auth__user_model.username", ondelete="CASCADE"),
        doc="Username owning this server-side auth session",
    )
    secret_hash: Mapped[str] = mapped_column(
        String(length=64),
        doc="SHA-256 hash of the browser session secret",
    )
    expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Current effective session expiration timestamp",
    )
    absolute_expires_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Original absolute session expiration timestamp",
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean,
        doc="Whether this auth session was explicitly revoked",
    )
    last_used_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Last successful login or refresh timestamp",
    )
    auth_method: Mapped[AuthSessionAuthMethodEnum] = mapped_column(
        Enum(
            AuthSessionAuthMethodEnum,
            native_enum=True,
            name="auth_session_auth_method_enum",
        ),
        doc="Authentication method that created the session",
    )
    user_agent_display: Mapped[str] = mapped_column(
        String(255),
        doc="Privacy-safe coarse user-agent display label",
    )
    user_agent_browser: Mapped[str] = mapped_column(
        String(63),
        doc="Privacy-safe browser family label",
    )
    user_agent_os: Mapped[str] = mapped_column(
        String(63),
        doc="Privacy-safe operating-system family label",
    )
    user_agent_device: Mapped[AuthSessionDeviceTypeEnum] = mapped_column(
        Enum(
            AuthSessionDeviceTypeEnum,
            native_enum=True,
            name="auth_session_device_type_enum",
        ),
        doc="Privacy-safe coarse device type",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(cls.secret_hash, name="auth_sessions_secret_hash_uniq"),
            Index(
                "auth_sessions_username_lower_active_expiry_idx",
                func.lower(cls.username).label("username_lower"),
                cls.is_revoked,
                cls.expires_at,
                cls.absolute_expires_at,
            ),
            Index("auth_sessions_expiry_idx", cls.expires_at),
            Index("auth_sessions_absolute_expiry_idx", cls.absolute_expires_at),
            Index(
                "auth_sessions_username_lower_active_last_used_idx",
                func.lower(cls.username).label("username_lower"),
                cls.is_revoked,
                cls.expires_at,
                cls.absolute_expires_at,
                cls.last_used_at.desc(),
                cls.id,
            ),
        )

    @classmethod
    def from_domain_schema(cls, schema: AuthSession) -> Self:
        return cls(
            id=schema.id,
            username=schema.username,
            secret_hash=schema.secret_hash,
            expires_at=schema.expires_at,
            absolute_expires_at=schema.absolute_expires_at,
            is_revoked=schema.is_revoked,
            last_used_at=schema.last_used_at,
            auth_method=schema.auth_method,
            user_agent_display=schema.client_metadata.user_agent_display,
            user_agent_browser=schema.client_metadata.user_agent_browser,
            user_agent_os=schema.client_metadata.user_agent_os,
            user_agent_device=schema.client_metadata.user_agent_device,
        )

    def to_domain_schema(self) -> AuthSession:
        return AuthSession(
            id=self.id,
            username=self.username,
            secret_hash=SessionSecretHash(self.secret_hash),
            expires_at=self.expires_at,
            absolute_expires_at=self.absolute_expires_at,
            is_revoked=self.is_revoked,
            created_at=self.created_at,
            last_used_at=self.last_used_at,
            auth_method=self.auth_method,
            client_metadata=AuthSessionClientMetadata(
                user_agent_display=self.user_agent_display,
                user_agent_browser=self.user_agent_browser,
                user_agent_os=self.user_agent_os,
                user_agent_device=self.user_agent_device,
            ),
        )
