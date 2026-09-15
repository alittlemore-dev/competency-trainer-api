from abc import ABC, abstractmethod
from datetime import datetime

from core.auth.schemas import AuthSession, AuthSessionCleanupCounts, AuthSessionCreate
from core.auth.types import SessionSecretHash, Token


class TokenRevocationStorage(ABC):
    @abstractmethod
    async def revoke_token(self, token: Token, expires_in_seconds: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def is_token_revoked(self, token: Token) -> bool:
        raise NotImplementedError


class AuthStorage(ABC):
    @abstractmethod
    async def update_user_password_hash(self, username: str, password_hash: str) -> None:
        raise NotImplementedError


class AuthSessionStorage(ABC):
    @abstractmethod
    async def create_session(self, *, session: AuthSessionCreate) -> AuthSession:
        raise NotImplementedError

    @abstractmethod
    async def get_session_by_secret_hash(self, *, secret_hash: SessionSecretHash) -> AuthSession:
        raise NotImplementedError

    @abstractmethod
    async def get_session_by_id(self, *, session_id: str) -> AuthSession:
        raise NotImplementedError

    @abstractmethod
    async def list_user_sessions(
        self,
        *,
        username: str,
        active_at: datetime,
    ) -> list[AuthSession]:
        raise NotImplementedError

    @abstractmethod
    async def extend_session_expiry(
        self,
        *,
        session_id: str,
        expires_at: datetime,
        last_used_at: datetime,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete_expired_sessions(
        self,
        *,
        expires_at: datetime,
    ) -> int:
        raise NotImplementedError

    @abstractmethod
    async def count_cleanup_sessions(
        self,
        *,
        expired_at: datetime,
        expiring_soon_at: datetime,
    ) -> AuthSessionCleanupCounts:
        raise NotImplementedError

    @abstractmethod
    async def revoke_session_by_secret_hash(self, *, secret_hash: SessionSecretHash) -> None:
        raise NotImplementedError

    @abstractmethod
    async def revoke_user_session(self, *, username: str, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def revoke_user_sessions(self, *, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def revoke_user_sessions_except(self, *, username: str, except_session_id: str) -> None:
        raise NotImplementedError
