# ruff: noqa: S106
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.exceptions import AuthSessionNotFoundError, UserNotFoundError
from core.auth.schemas import (
    AuthSession,
    AuthSessionCleanupCounts,
    AuthSessionClientMetadata,
    AuthSessionCreate,
)
from core.auth.types import SessionSecretHash
from infra.postgresql.storages.auth import AuthDatabaseStorage, AuthSessionDatabaseStorage
from infra.postgresql.storages.users import UserAccountDatabaseStorage
from tests.test_cases import StorageTestCase


class TestAuthStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.user_storage = UserAccountDatabaseStorage(session=session)
        self.storage = AuthDatabaseStorage(session=session)
        await self.storage_helper.create_users(
            users=[
                self.factory.core.user(
                    username="user1",
                    password_hash="password1",
                    role=RoleEnum.USER,
                ),
                self.factory.core.user(
                    username="user2",
                    password_hash="password2",
                    role=RoleEnum.ADMIN,
                ),
            ],
        )

    async def test_update_user_password_not_found(self) -> None:
        with pytest.raises(UserNotFoundError):
            await self.storage.update_user_password_hash(
                username="user3",
                password_hash="NEW_PASSWORD",
            )

    async def test_update_user_password(self) -> None:
        await self.storage.update_user_password_hash(username="user1", password_hash="NEW_PASSWORD")
        user = await self.user_storage.get_user_by_username(username="user1")
        assert user == self.factory.core.user(
            username="user1",
            password_hash="NEW_PASSWORD",
            role=RoleEnum.USER,
        )


class TestAuthSessionStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.session = session
        self.storage = AuthSessionDatabaseStorage(session=session)
        self.now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
        await self.storage_helper.create_users(
            users=[
                self.factory.core.user(
                    username="admin",
                    password_hash="password1",
                    role=RoleEnum.ADMIN,
                ),
                self.factory.core.user(
                    username="moderator",
                    password_hash="password2",
                    role=RoleEnum.MODERATOR,
                ),
            ],
        )

    async def test_get_session_by_secret_hash_not_found(self) -> None:
        with pytest.raises(AuthSessionNotFoundError):
            await self.storage.get_session_by_secret_hash(
                secret_hash=SessionSecretHash("missing"),
            )

    async def test_create_and_get_session(self) -> None:
        session = AuthSessionCreate(
            username="admin",
            secret_hash=SessionSecretHash(
                "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            ),
            expires_at=self.now + timedelta(days=30),
            absolute_expires_at=self.now + timedelta(days=30),
            is_revoked=False,
            last_used_at=self.now,
            auth_method=AuthSessionAuthMethodEnum.PASSWORD,
            client_metadata=auth_session_client(),
        )

        created = await self.storage.create_session(session=session)
        stored = await self.storage.get_session_by_secret_hash(
            secret_hash=session.secret_hash,
        )
        expected = AuthSession(
            id=created.id,
            username=session.username,
            secret_hash=session.secret_hash,
            expires_at=session.expires_at,
            absolute_expires_at=session.absolute_expires_at,
            is_revoked=session.is_revoked,
            created_at=created.created_at,
            last_used_at=session.last_used_at,
            auth_method=session.auth_method,
            client_metadata=session.client_metadata,
        )

        assert len(created.id) == 32
        assert created == expected
        assert stored == expected
        assert await self.storage.get_session_by_id(session_id=created.id) == expected

    async def test_list_user_sessions_returns_active_sessions_newest_first(self) -> None:
        older_active = await self.storage.create_session(
            session=auth_session_create(
                username="admin",
                secret_hash="1" * 64,
                last_used_at=self.now - timedelta(hours=2),
            ),
        )
        newest_active = await self.storage.create_session(
            session=auth_session_create(
                username="admin",
                secret_hash="2" * 64,
                last_used_at=self.now,
            ),
        )
        await self.storage.create_session(
            session=auth_session_create(
                username="admin",
                secret_hash="3" * 64,
                expires_at=self.now - timedelta(seconds=1),
            ),
        )
        await self.storage.create_session(
            session=replace(
                auth_session_create(
                    username="admin",
                    secret_hash="4" * 64,
                ),
                is_revoked=True,
            ),
        )
        await self.storage.create_session(
            session=auth_session_create(
                username="admin",
                secret_hash="5" * 64,
                expires_at=self.now + timedelta(days=1),
                absolute_expires_at=self.now,
                last_used_at=self.now + timedelta(hours=1),
            ),
        )

        sessions = await self.storage.list_user_sessions(
            username="admin",
            active_at=self.now,
        )

        assert [session.id for session in sessions] == [newest_active.id, older_active.id]

    async def test_revoke_user_session_scopes_by_username_case_insensitively(self) -> None:
        admin_session = await self.storage.create_session(
            session=auth_session_create(username="admin", secret_hash="5" * 64),
        )
        moderator_session = await self.storage.create_session(
            session=auth_session_create(username="moderator", secret_hash="6" * 64),
        )

        await self.storage.revoke_user_session(username="ADMIN", session_id=admin_session.id)

        assert (await self.storage.get_session_by_id(session_id=admin_session.id)).is_revoked
        assert not (
            await self.storage.get_session_by_id(session_id=moderator_session.id)
        ).is_revoked

    async def test_revoke_user_sessions_except_preserves_current_session(self) -> None:
        current_session = await self.storage.create_session(
            session=auth_session_create(username="admin", secret_hash="7" * 64),
        )
        other_session = await self.storage.create_session(
            session=auth_session_create(username="admin", secret_hash="8" * 64),
        )

        await self.storage.revoke_user_sessions_except(
            username="ADMIN",
            except_session_id=current_session.id,
        )

        assert not (await self.storage.get_session_by_id(session_id=current_session.id)).is_revoked
        assert (await self.storage.get_session_by_id(session_id=other_session.id)).is_revoked

    async def test_revoke_session_by_secret_hash(self) -> None:
        session = auth_session_create(
            username="admin",
            secret_hash="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        created = await self.storage.create_session(session=session)

        await self.storage.revoke_session_by_secret_hash(secret_hash=session.secret_hash)

        stored = await self.storage.get_session_by_id(session_id=created.id)
        assert stored == AuthSession(
            id=created.id,
            username=session.username,
            secret_hash=session.secret_hash,
            expires_at=session.expires_at,
            absolute_expires_at=session.absolute_expires_at,
            is_revoked=True,
            created_at=created.created_at,
            last_used_at=session.last_used_at,
            auth_method=session.auth_method,
            client_metadata=session.client_metadata,
        )

    async def test_extend_session_expiry(self) -> None:
        session = auth_session_create(
            username="admin",
            secret_hash="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        )
        created = await self.storage.create_session(session=session)
        new_expires_at = self.now + timedelta(days=45)
        new_last_used_at = self.now + timedelta(minutes=5)

        await self.storage.extend_session_expiry(
            session_id=created.id,
            expires_at=new_expires_at,
            last_used_at=new_last_used_at,
        )

        stored = await self.storage.get_session_by_id(session_id=created.id)
        assert stored == AuthSession(
            id=created.id,
            username=session.username,
            secret_hash=session.secret_hash,
            expires_at=new_expires_at,
            absolute_expires_at=session.absolute_expires_at,
            is_revoked=False,
            created_at=created.created_at,
            last_used_at=new_last_used_at,
            auth_method=session.auth_method,
            client_metadata=session.client_metadata,
        )

    async def test_extend_session_expiry_not_found(self) -> None:
        with pytest.raises(AuthSessionNotFoundError):
            await self.storage.extend_session_expiry(
                session_id="10000000000040008000000000000001",
                expires_at=self.now + timedelta(days=45),
                last_used_at=self.now,
            )

    async def test_delete_expired_sessions(self) -> None:
        expired_session = auth_session_create(
            username="admin",
            secret_hash="1111111111111111111111111111111111111111111111111111111111111111",
            expires_at=self.now,
        )
        active_session = auth_session_create(
            username="admin",
            secret_hash="2222222222222222222222222222222222222222222222222222222222222222",
            expires_at=self.now + timedelta(seconds=1),
        )
        revoked_active_session = replace(
            auth_session_create(
                username="moderator",
                secret_hash="3333333333333333333333333333333333333333333333333333333333333333",
                expires_at=self.now + timedelta(days=1),
            ),
            is_revoked=True,
        )
        created_expired_session = await self.storage.create_session(session=expired_session)
        created_active_session = await self.storage.create_session(session=active_session)
        created_revoked_active_session = await self.storage.create_session(
            session=revoked_active_session,
        )
        absolute_expired_session = auth_session_create(
            username="admin",
            secret_hash="4444444444444444444444444444444444444444444444444444444444444444",
            expires_at=self.now + timedelta(days=1),
            absolute_expires_at=self.now,
        )
        created_absolute_expired_session = await self.storage.create_session(
            session=absolute_expired_session,
        )

        deleted_count = await self.storage.delete_expired_sessions(expires_at=self.now)

        assert deleted_count == 2
        with pytest.raises(AuthSessionNotFoundError):
            await self.storage.get_session_by_id(session_id=created_expired_session.id)
        with pytest.raises(AuthSessionNotFoundError):
            await self.storage.get_session_by_id(
                session_id=created_absolute_expired_session.id,
            )
        assert await self.storage.get_session_by_id(session_id=created_active_session.id)
        assert await self.storage.get_session_by_id(session_id=created_revoked_active_session.id)

    async def test_count_cleanup_sessions_uses_effective_expiry_and_excludes_revoked_soon(
        self,
    ) -> None:
        sessions = [
            auth_session_create(
                username="admin",
                secret_hash="a" * 64,
                expires_at=self.now,
            ),
            replace(
                auth_session_create(
                    username="moderator",
                    secret_hash="b" * 64,
                    expires_at=self.now + timedelta(days=1),
                    absolute_expires_at=self.now,
                ),
                is_revoked=True,
            ),
            auth_session_create(
                username="admin",
                secret_hash="c" * 64,
                expires_at=self.now + timedelta(days=7),
                absolute_expires_at=self.now + timedelta(days=30),
            ),
            auth_session_create(
                username="moderator",
                secret_hash="d" * 64,
                expires_at=self.now + timedelta(days=30),
                absolute_expires_at=self.now + timedelta(days=7),
            ),
            auth_session_create(
                username="admin",
                secret_hash="e" * 64,
                expires_at=self.now + timedelta(days=7, seconds=1),
                absolute_expires_at=self.now + timedelta(days=30),
            ),
            replace(
                auth_session_create(
                    username="moderator",
                    secret_hash="f" * 64,
                    expires_at=self.now + timedelta(days=1),
                ),
                is_revoked=True,
            ),
        ]
        for session in sessions:
            await self.storage.create_session(session=session)

        counts = await self.storage.count_cleanup_sessions(
            expired_at=self.now,
            expiring_soon_at=self.now + timedelta(days=7),
        )

        assert counts == AuthSessionCleanupCounts(expired_count=2, expiring_soon_count=2)

    async def test_revoke_user_sessions_case_insensitively(self) -> None:
        admin_session = auth_session_create(
            username="admin",
            secret_hash="cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        )
        moderator_session = auth_session_create(
            username="moderator",
            secret_hash="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        )
        created_admin_session = await self.storage.create_session(session=admin_session)
        created_moderator_session = await self.storage.create_session(session=moderator_session)

        await self.storage.revoke_user_sessions(username="ADMIN")

        assert (
            await self.storage.get_session_by_id(session_id=created_admin_session.id)
        ).is_revoked
        assert not (
            await self.storage.get_session_by_id(session_id=created_moderator_session.id)
        ).is_revoked


def auth_session_create(
    *,
    username: str,
    secret_hash: str,
    expires_at: datetime | None = None,
    absolute_expires_at: datetime | None = None,
    last_used_at: datetime | None = None,
) -> AuthSessionCreate:
    now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
    return AuthSessionCreate(
        username=username,
        secret_hash=SessionSecretHash(secret_hash),
        expires_at=expires_at or now + timedelta(days=30),
        absolute_expires_at=absolute_expires_at or now + timedelta(days=30),
        is_revoked=False,
        last_used_at=last_used_at or now,
        auth_method=AuthSessionAuthMethodEnum.PASSWORD,
        client_metadata=auth_session_client(),
    )


def auth_session_client() -> AuthSessionClientMetadata:
    return AuthSessionClientMetadata(
        user_agent_display="Firefox on Linux",
        user_agent_browser="Firefox",
        user_agent_os="Linux",
        user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
    )
