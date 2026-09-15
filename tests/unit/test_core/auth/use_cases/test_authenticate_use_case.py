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
    AuthAuthenticateParams,
    AuthSession,
    AuthSessionClientMetadata,
)
from core.auth.storages import AuthSessionStorage, TokenRevocationStorage
from core.auth.types import SessionSecretHash, Token
from core.auth.use_cases import AuthUseCase
from tests.test_cases import ContainerTestCase


class TestLoginUseCase(ContainerTestCase):
    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def setup(self) -> None:
        self.token_handler = await self.container.get_token_handler()
        self.user_storage = await self.container.get_user_storage()
        self.token_revocation_storage = Mock(spec=TokenRevocationStorage)
        self.token_revocation_storage.is_token_revoked.return_value = False
        self.auth_session_storage = Mock(spec=AuthSessionStorage)
        self.auth_event_reporter = Mock(spec=AuthEventReporter)
        self.now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
        self.use_case = AuthUseCase(
            hasher=await self.container.get_hasher(),
            auth_storage=await self.container.get_auth_storage(),
            token_handler=self.token_handler,
            token_revocation_storage=self.token_revocation_storage,
            auth_session_storage=self.auth_session_storage,
            user_storage=self.user_storage,
            event_reporter=self.auth_event_reporter,
            auth_session_secret_generator=AuthSessionSecretGenerator(byte_count=32),
        )

    def _set_active_session(self, *, username: str = "test") -> None:
        self.auth_session_storage.get_session_by_id.return_value = AuthSession(
            id="session-id",
            username=username,
            secret_hash=SessionSecretHash("session-secret-hash"),
            expires_at=self.now + timedelta(days=1),
            absolute_expires_at=self.now + timedelta(days=30),
            is_revoked=False,
            created_at=self.now,
            last_used_at=self.now,
            auth_method=AuthSessionAuthMethodEnum.PASSWORD,
            client_metadata=auth_session_client(),
        )

    async def test_authenticate_revoked_token(self) -> None:
        token = Token(b"revoked_token")
        self.token_revocation_storage.is_token_revoked.return_value = True

        with pytest.raises(UnauthorizedError):
            await self.use_case.authenticate(
                params=AuthAuthenticateParams(
                    token=token,
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                ),
            )

        self.token_revocation_storage.is_token_revoked.assert_called_once_with(token=token)
        self.token_handler.decode_token.assert_not_called()
        self.user_storage.get_user_by_username.assert_not_called()
        self.auth_event_reporter.report_authentication_revoked_token_used.assert_called_once_with()

    async def test_authenticate_token_decode_error(self) -> None:
        self.token_handler.decode_token.side_effect = UnauthorizedError
        with pytest.raises(UnauthorizedError):
            await self.use_case.authenticate(
                params=AuthAuthenticateParams(
                    token=Token(b"invalid_token"),
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                ),
            )
        self.token_revocation_storage.is_token_revoked.assert_called_once_with(
            token=Token(b"invalid_token"),
        )
        self.token_handler.decode_token.assert_called_once_with(b"invalid_token")

    async def test_authenticate_user_not_found(self) -> None:
        self.user_storage.get_user_by_username.side_effect = UserNotFoundError
        self.token_handler.decode_token.return_value = AccessTokenPayload(
            username="test",
            session_id="session-id",
        )
        self._set_active_session()
        with pytest.raises(UnauthorizedError):
            await self.use_case.authenticate(
                params=AuthAuthenticateParams(
                    token=Token(b"valid_token"),
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                ),
            )
        self.user_storage.get_user_by_username.assert_called_once_with(username="test")
        self.auth_event_reporter.report_authentication_user_not_found.assert_called_once_with(
            username="test",
        )

    async def test_authenticate_user_not_has_role(self) -> None:
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.USER,
        )
        self.token_handler.decode_token.return_value = AccessTokenPayload(
            username="test",
            session_id="session-id",
        )
        self._set_active_session()
        with pytest.raises(ForbiddenError):
            await self.use_case.authenticate(
                params=AuthAuthenticateParams(
                    token=Token(b"valid_token"),
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                ),
            )
        self.auth_event_reporter.report_authentication_role_forbidden.assert_called_once_with(
            username="test",
            required_role=RoleEnum.ADMIN,
        )

    async def test_authenticate_inactive_user(self) -> None:
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
            is_active=False,
        )
        self.token_handler.decode_token.return_value = AccessTokenPayload(
            username="test",
            session_id="session-id",
        )
        self._set_active_session()

        with pytest.raises(UnauthorizedError):
            await self.use_case.authenticate(
                params=AuthAuthenticateParams(
                    token=Token(b"valid_token"),
                    required_role=RoleEnum.ADMIN,
                    current_datetime=self.now,
                ),
            )

        self.auth_event_reporter.report_authentication_inactive_user.assert_called_once_with(
            username="test",
        )

    async def test_authenticate(self) -> None:
        self.user_storage.get_user_by_username.return_value = self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
        )
        self.token_handler.decode_token.return_value = AccessTokenPayload(
            username="test",
            session_id="session-id",
        )
        self._set_active_session()
        self.token_handler.encode_token.return_value = b"NEW_TOKEN"
        user = await self.use_case.authenticate(
            params=AuthAuthenticateParams(
                token=Token(b"valid_token"),
                required_role=RoleEnum.ADMIN,
                current_datetime=self.now,
            ),
        )
        assert user == self.factory.core.user(
            username="test",
            password_hash="test",
            role=RoleEnum.ADMIN,
        )


def auth_session_client() -> AuthSessionClientMetadata:
    return AuthSessionClientMetadata(
        user_agent_display="Firefox on Linux",
        user_agent_browser="Firefox",
        user_agent_os="Linux",
        user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
    )
