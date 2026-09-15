# ruff: noqa: S106
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

import pytest
import pytest_asyncio

from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.event_dispatchers import AuthEventReporter
from core.auth.exceptions import ForbiddenError, UnauthorizedError, UserNotFoundError
from core.auth.generators import AuthSessionSecretGenerator
from core.auth.schemas import (
    AccessTokenPayload,
    AccessTokenResult,
    AuthLoginParams,
    AuthLoginResult,
    AuthSession,
    AuthSessionClientMetadata,
    AuthSessionCreate,
    AuthSessionCredentials,
    AuthUseCaseConfig,
)
from core.auth.storages import AuthSessionStorage, TokenRevocationStorage
from core.auth.types import SessionSecret, SessionSecretHash
from core.auth.use_cases import AuthUseCase
from tests.test_cases import ContainerTestCase


class TestAuthUseCase(ContainerTestCase):
    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def setup(self) -> None:
        self.hasher = await self.container.get_hasher()
        self.token_handler = await self.container.get_token_handler()
        self.auth_storage = await self.container.get_auth_storage()
        self.token_revocation_storage = Mock(spec=TokenRevocationStorage)
        self.auth_session_storage = Mock(spec=AuthSessionStorage)
        self.user_storage = await self.container.get_user_storage()
        self.auth_event_reporter = Mock(spec=AuthEventReporter)
        self.now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
        self.auth_session_secret_generator = Mock(spec=AuthSessionSecretGenerator)
        self.auth_session_secret_generator.generate_secret.return_value = SessionSecret(
            "session-secret",
        )
        self.auth_session_secret_generator.hash_secret.return_value = SessionSecretHash(
            "session-secret-hash",
        )
        self.config = AuthUseCaseConfig(
            access_token_expires_in_seconds=900,
            session_expires_in_seconds=2_592_000,
            session_absolute_expires_in_seconds=2_592_000,
        )
        self.auth_session_storage.create_session.return_value = AuthSession(
            id="session-id",
            username="test",
            secret_hash=SessionSecretHash("session-secret-hash"),
            expires_at=self.now + timedelta(seconds=2_592_000),
            absolute_expires_at=self.now + timedelta(seconds=2_592_000),
            is_revoked=False,
            created_at=self.now,
            last_used_at=self.now,
            auth_method=AuthSessionAuthMethodEnum.PASSWORD,
            client_metadata=auth_session_client(),
        )
        self.use_case = AuthUseCase(
            hasher=self.hasher,
            token_handler=self.token_handler,
            auth_storage=self.auth_storage,
            token_revocation_storage=self.token_revocation_storage,
            auth_session_storage=self.auth_session_storage,
            user_storage=self.user_storage,
            event_reporter=self.auth_event_reporter,
            auth_session_secret_generator=self.auth_session_secret_generator,
        )

    async def test_login_user_not_found(self) -> None:
        self.user_storage.get_user_by_username.side_effect = UserNotFoundError
        with pytest.raises(UnauthorizedError):
            await self.use_case.login(
                config=self.config,
                params=AuthLoginParams(
                    username="test",
                    password="test",
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                    client_metadata=auth_session_client(),
                ),
            )
        self.auth_event_reporter.report_login_user_not_found.assert_called_once_with(
            username="test",
        )

    async def test_login_user_role_not_has_role(self) -> None:
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.USER,
        )
        with pytest.raises(ForbiddenError):
            await self.use_case.login(
                config=self.config,
                params=AuthLoginParams(
                    username="test",
                    password="test",
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                    client_metadata=auth_session_client(),
                ),
            )
        self.auth_event_reporter.report_login_role_forbidden.assert_called_once_with(
            username="test",
            required_role=RoleEnum.ADMIN,
        )

    async def test_login_inactive_user(self) -> None:
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
            is_active=False,
        )
        with pytest.raises(UnauthorizedError):
            await self.use_case.login(
                config=self.config,
                params=AuthLoginParams(
                    username="test",
                    password="test",
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                    client_metadata=auth_session_client(),
                ),
            )
        self.auth_event_reporter.report_login_inactive_user.assert_called_once_with(
            username="test",
        )
        self.hasher.verify_password.assert_not_called()

    async def test_login_not_verified_password(self) -> None:
        self.hasher.verify_password.return_value = (False, False)
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
        )
        with pytest.raises(UnauthorizedError):
            await self.use_case.login(
                config=self.config,
                params=AuthLoginParams(
                    username="test",
                    password="test",
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                    client_metadata=auth_session_client(),
                ),
            )
        self.auth_event_reporter.report_login_password_verification_failed.assert_called_once_with(
            username="test",
        )

    async def test_login_rehash_on_password_expire(self) -> None:
        self.token_handler.encode_token.return_value = b"TOKEN"
        self.hasher.verify_password.return_value = (True, True)
        self.hasher.hash_password.return_value = "new_password"
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
        )
        result = await self.use_case.login(
            config=self.config,
            params=AuthLoginParams(
                username="test",
                password="test",
                required_role=RoleEnum.ADMIN,
                current_datetime=self.now,
                client_metadata=auth_session_client(),
            ),
        )
        assert result.access_token.token == self.factory.core.token(b"TOKEN")
        self.auth_storage.update_user_password_hash.assert_called_once_with(
            username="test",
            password_hash="new_password",
        )

    async def test_login(self) -> None:
        self.token_handler.encode_token.return_value = b"TOKEN"
        self.hasher.verify_password.return_value = (True, False)
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
        )
        result = await self.use_case.login(
            config=self.config,
            params=AuthLoginParams(
                username="test",
                password="test",
                required_role=RoleEnum.ADMIN,
                current_datetime=self.now,
                client_metadata=auth_session_client(),
            ),
        )
        assert result == AuthLoginResult(
            access_token=AccessTokenResult(
                token=self.factory.core.token(b"TOKEN"),
                expires_in_seconds=900,
            ),
            session=AuthSessionCredentials(
                secret=SessionSecret("session-secret"),
                expires_in_seconds=2_592_000,
            ),
        )
        self.user_storage.get_user_by_username.assert_called_once_with(username="test")
        self.hasher.verify_password.assert_called_once_with(
            plain_password="test",
            hashed_password="test",
        )
        self.auth_session_storage.create_session.assert_called_once_with(
            session=AuthSessionCreate(
                username="test",
                secret_hash=SessionSecretHash("session-secret-hash"),
                expires_at=self.now + timedelta(seconds=2_592_000),
                absolute_expires_at=self.now + timedelta(seconds=2_592_000),
                is_revoked=False,
                last_used_at=self.now,
                auth_method=AuthSessionAuthMethodEnum.PASSWORD,
                client_metadata=auth_session_client(),
            ),
        )
        self.token_handler.encode_token.assert_called_once_with(
            payload=AccessTokenPayload(username="test", session_id="session-id"),
        )


def auth_session_client() -> AuthSessionClientMetadata:
    return AuthSessionClientMetadata(
        user_agent_display="Firefox on Linux",
        user_agent_browser="Firefox",
        user_agent_os="Linux",
        user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
    )
