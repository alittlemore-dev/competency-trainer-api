from unittest.mock import Mock

import pytest_asyncio

from core.auth.event_dispatchers import AuthEventReporter
from core.auth.exceptions import UnauthorizedError
from core.auth.generators import AuthSessionSecretGenerator
from core.auth.schemas import AuthLogoutParams
from core.auth.storages import AuthSessionStorage, TokenRevocationStorage
from core.auth.types import Token
from core.auth.use_cases import AuthUseCase
from tests.test_cases import ContainerTestCase


class TestLogoutUseCase(ContainerTestCase):
    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def setup(self) -> None:
        self.token_handler = await self.container.get_token_handler()
        self.token_revocation_storage = Mock(spec=TokenRevocationStorage)
        self.auth_session_storage = Mock(spec=AuthSessionStorage)
        self.auth_event_reporter = Mock(spec=AuthEventReporter)
        self.use_case = AuthUseCase(
            hasher=await self.container.get_hasher(),
            auth_storage=await self.container.get_auth_storage(),
            token_handler=self.token_handler,
            token_revocation_storage=self.token_revocation_storage,
            auth_session_storage=self.auth_session_storage,
            user_storage=await self.container.get_user_storage(),
            event_reporter=self.auth_event_reporter,
            auth_session_secret_generator=AuthSessionSecretGenerator(byte_count=32),
        )

    async def test_logout_revokes_valid_token_until_it_expires(self) -> None:
        token = Token(b"valid_token")
        self.token_handler.get_token_remaining_seconds.return_value = 42

        await self.use_case.logout(params=AuthLogoutParams(token=token, session_secret=None))

        self.token_handler.get_token_remaining_seconds.assert_called_once_with(token)
        self.token_revocation_storage.revoke_token.assert_called_once_with(
            token=token,
            expires_in_seconds=42,
        )

    async def test_logout_ignores_invalid_token(self) -> None:
        token = Token(b"invalid_token")
        self.token_handler.get_token_remaining_seconds.side_effect = UnauthorizedError

        await self.use_case.logout(params=AuthLogoutParams(token=token, session_secret=None))

        self.token_revocation_storage.revoke_token.assert_not_called()
        self.auth_event_reporter.report_logout_invalid_token.assert_called_once_with()

    async def test_logout_ignores_token_without_remaining_lifetime(self) -> None:
        token = Token(b"expired_token")
        self.token_handler.get_token_remaining_seconds.return_value = None

        await self.use_case.logout(params=AuthLogoutParams(token=token, session_secret=None))

        self.token_revocation_storage.revoke_token.assert_not_called()
        self.auth_event_reporter.report_logout_token_without_remaining_lifetime.assert_called_once_with()
