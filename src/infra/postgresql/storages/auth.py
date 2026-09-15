from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import and_, delete, func, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.exceptions import AuthSessionNotFoundError, UserNotFoundError
from core.auth.schemas import AuthSession, AuthSessionCleanupCounts, AuthSessionCreate
from core.auth.storages import AuthSessionStorage, AuthStorage
from core.auth.types import SessionSecretHash
from infra.postgresql.models import AuthSessionModel, UserModel


@dataclass(kw_only=True)
class AuthDatabaseStorage(AuthStorage):
    session: AsyncSession

    async def update_user_password_hash(self, username: str, password_hash: str) -> None:
        stmt = (
            update(UserModel)
            .values(password_hash=password_hash)
            .where(func.lower(UserModel.username) == username.lower())
            .returning(UserModel.username)
        )
        db_username = await self.session.scalar(stmt)
        if db_username is None:
            raise UserNotFoundError


@dataclass(kw_only=True)
class AuthSessionDatabaseStorage(AuthSessionStorage):
    session: AsyncSession

    async def create_session(self, *, session: AuthSessionCreate) -> AuthSession:
        statement = (
            insert(AuthSessionModel)
            .values(
                username=session.username,
                secret_hash=session.secret_hash,
                expires_at=session.expires_at,
                absolute_expires_at=session.absolute_expires_at,
                is_revoked=session.is_revoked,
                last_used_at=session.last_used_at,
                auth_method=session.auth_method,
                user_agent_display=session.client_metadata.user_agent_display,
                user_agent_browser=session.client_metadata.user_agent_browser,
                user_agent_os=session.client_metadata.user_agent_os,
                user_agent_device=session.client_metadata.user_agent_device,
            )
            .returning(AuthSessionModel)
        )
        model = await self.session.scalar(statement)
        if model is None:
            raise AuthSessionNotFoundError
        return model.to_domain_schema()

    async def get_session_by_secret_hash(self, *, secret_hash: SessionSecretHash) -> AuthSession:
        statement = select(AuthSessionModel).where(AuthSessionModel.secret_hash == secret_hash)
        model = await self.session.scalar(statement)
        if model is None:
            raise AuthSessionNotFoundError
        return model.to_domain_schema()

    async def get_session_by_id(self, *, session_id: str) -> AuthSession:
        statement = select(AuthSessionModel).where(AuthSessionModel.id == session_id)
        model = await self.session.scalar(statement)
        if model is None:
            raise AuthSessionNotFoundError
        return model.to_domain_schema()

    async def list_user_sessions(
        self,
        *,
        username: str,
        active_at: datetime,
    ) -> list[AuthSession]:
        statement = (
            select(AuthSessionModel)
            .where(
                func.lower(AuthSessionModel.username) == username.lower(),
                AuthSessionModel.is_revoked.is_(False),
                AuthSessionModel.expires_at > active_at,
                AuthSessionModel.absolute_expires_at > active_at,
            )
            .order_by(AuthSessionModel.last_used_at.desc(), AuthSessionModel.id)
        )
        models = await self.session.scalars(statement)
        return [model.to_domain_schema() for model in models]

    async def extend_session_expiry(
        self,
        *,
        session_id: str,
        expires_at: datetime,
        last_used_at: datetime,
    ) -> None:
        statement = (
            update(AuthSessionModel)
            .values(expires_at=expires_at, last_used_at=last_used_at)
            .where(AuthSessionModel.id == session_id)
            .returning(AuthSessionModel.id)
        )
        stored_session_id = await self.session.scalar(statement)
        if stored_session_id is None:
            raise AuthSessionNotFoundError

    async def delete_expired_sessions(
        self,
        *,
        expires_at: datetime,
    ) -> int:
        statement = delete(AuthSessionModel).where(
            or_(
                AuthSessionModel.expires_at <= expires_at,
                AuthSessionModel.absolute_expires_at <= expires_at,
            ),
        )
        result = await self.session.execute(statement)
        rowcount = cast("int | None", getattr(result, "rowcount", None))
        if rowcount is None:
            return 0
        return rowcount

    async def count_cleanup_sessions(
        self,
        *,
        expired_at: datetime,
        expiring_soon_at: datetime,
    ) -> AuthSessionCleanupCounts:
        expired_condition = or_(
            AuthSessionModel.expires_at <= expired_at,
            AuthSessionModel.absolute_expires_at <= expired_at,
        )
        expiring_soon_condition = and_(
            AuthSessionModel.is_revoked.is_(False),
            AuthSessionModel.expires_at > expired_at,
            AuthSessionModel.absolute_expires_at > expired_at,
            or_(
                AuthSessionModel.expires_at <= expiring_soon_at,
                AuthSessionModel.absolute_expires_at <= expiring_soon_at,
            ),
        )
        statement = select(
            func.count(AuthSessionModel.id).filter(expired_condition).label("expired_count"),
            func.count(AuthSessionModel.id)
            .filter(expiring_soon_condition)
            .label("expiring_soon_count"),
        )
        row = (await self.session.execute(statement)).one()
        return AuthSessionCleanupCounts(
            expired_count=row.expired_count,
            expiring_soon_count=row.expiring_soon_count,
        )

    async def revoke_session_by_secret_hash(self, *, secret_hash: SessionSecretHash) -> None:
        statement = (
            update(AuthSessionModel)
            .values(is_revoked=True)
            .where(AuthSessionModel.secret_hash == secret_hash)
            .returning(AuthSessionModel.id)
        )
        session_id = await self.session.scalar(statement)
        if session_id is None:
            raise AuthSessionNotFoundError

    async def revoke_user_session(self, *, username: str, session_id: str) -> None:
        statement = (
            update(AuthSessionModel)
            .values(is_revoked=True)
            .where(
                AuthSessionModel.id == session_id,
                func.lower(AuthSessionModel.username) == username.lower(),
            )
            .returning(AuthSessionModel.id)
        )
        revoked_session_id = await self.session.scalar(statement)
        if revoked_session_id is None:
            raise AuthSessionNotFoundError

    async def revoke_user_sessions(self, *, username: str) -> None:
        statement = (
            update(AuthSessionModel)
            .values(is_revoked=True)
            .where(func.lower(AuthSessionModel.username) == username.lower())
        )
        await self.session.execute(statement)

    async def revoke_user_sessions_except(self, *, username: str, except_session_id: str) -> None:
        statement = (
            update(AuthSessionModel)
            .values(is_revoked=True)
            .where(
                func.lower(AuthSessionModel.username) == username.lower(),
                AuthSessionModel.id != except_session_id,
            )
        )
        await self.session.execute(statement)
