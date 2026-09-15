from datetime import UTC, datetime
from unittest.mock import Mock

from dishka import BaseScope, Component, Provider, Scope, provide

from core.auth.enums import AuthSessionDeviceTypeEnum
from core.auth.password_hashers import PasswordHasher
from core.auth.schemas import (
    AccessTokenPayload,
    AccessTokenResult,
    AuthLoginResult,
    AuthRefreshAccessTokenResult,
    AuthSessionCleanupPolicy,
    AuthSessionClientMetadata,
    AuthSessionCredentials,
    AuthUseCaseConfig,
    JwtUser,
)
from core.auth.storages import AuthSessionStorage, AuthStorage
from core.auth.token_handlers import TokenHandler
from core.auth.types import RawToken, SessionSecret, Token
from core.auth.use_cases import AuthSessionCleanupUseCase, AuthUseCase
from infra.config.constants import constants
from infra.config.settings import Settings

test_public_key_pem = """\
-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAgiimqA4yuUL9ahhsRGooZXoO4XTDzmK+pu4mJnfdPIk=
-----END PUBLIC KEY-----
"""
test_private_key_pem = """\
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIHvAarrKpuBdN5qcsk7uVGwHA3HuzMr0j7ZGvIruVb+B
-----END PRIVATE KEY-----
"""
test_current_datetime = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)


class MockAuthProvider(Provider):
    def __init__(
        self,
        raw_token: RawToken,
        user: JwtUser,
        settings: Settings,
        scope: BaseScope | None = None,
        component: Component | None = None,
    ) -> None:
        super().__init__(scope=scope, component=component)
        self.settings = settings
        self.user = user
        self.raw_token = raw_token

    @provide(scope=Scope.APP)
    async def provide_raw_token(self) -> RawToken:
        return self.raw_token

    @provide(scope=Scope.APP)
    async def provide_token(self, raw_token: RawToken) -> Token:
        return Token(raw_token.split(self.settings.auth.token_prefix)[-1].strip().encode())

    @provide(scope=Scope.APP)
    async def provide_current_datetime(self) -> datetime:
        return test_current_datetime

    @provide(scope=Scope.APP)
    async def provide_auth_session_client_metadata(self) -> AuthSessionClientMetadata:
        return AuthSessionClientMetadata(
            user_agent_display="Firefox on Linux",
            user_agent_browser="Firefox",
            user_agent_os="Linux",
            user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
        )

    @provide(scope=Scope.APP)
    async def provide_auth_use_case_config(self) -> AuthUseCaseConfig:
        return AuthUseCaseConfig(
            access_token_expires_in_seconds=self.settings.auth.token_expire_seconds,
            session_expires_in_seconds=self.settings.auth.session_expire_seconds,
            session_absolute_expires_in_seconds=self.settings.auth.session_absolute_expire_seconds,
        )

    @provide(scope=Scope.APP)
    async def provide_auth_session_cleanup_policy(self) -> AuthSessionCleanupPolicy:
        return AuthSessionCleanupPolicy(
            expiring_soon_days=constants.auth.session_expiring_soon_days,
            scheduled_prune_interval_seconds=(
                self.settings.taskiq.auth_session_prune_interval_seconds
            ),
        )

    @provide(scope=Scope.APP)
    async def provide_hasher(self) -> PasswordHasher:
        mock = Mock(spec=PasswordHasher)
        mock.verify_password.return_value = True, False
        mock.hash_password.return_value = "1234"
        return mock

    @provide(scope=Scope.APP)
    async def provide_token_handler(self) -> TokenHandler:
        mock = Mock(spec=TokenHandler)
        mock.encode_token.return_value = Token(b"TOKEN")
        mock.decode_token.return_value = AccessTokenPayload(
            username=self.user.username,
            session_id="10000000000040008000000000000001",
        )
        return mock

    @provide(scope=Scope.APP)
    async def provide_auth_storage(self) -> AuthStorage:
        return Mock(spec=AuthStorage)

    @provide(scope=Scope.APP)
    async def provide_auth_session_storage(self) -> AuthSessionStorage:
        return Mock(spec=AuthSessionStorage)

    @provide(scope=Scope.APP)
    async def provide_auth_use_case(self) -> AuthUseCase:
        mock = Mock(spec=AuthUseCase)
        mock.login.return_value = AuthLoginResult(
            access_token=AccessTokenResult(token=Token(b"TOKEN"), expires_in_seconds=900),
            session=AuthSessionCredentials(
                secret=SessionSecret("session-secret"),
                expires_in_seconds=2_592_000,
            ),
        )
        mock.refresh_access_token.return_value = AuthRefreshAccessTokenResult(
            access_token=AccessTokenResult(
                token=Token(b"TOKEN"),
                expires_in_seconds=900,
            ),
            session=AuthSessionCredentials(
                secret=SessionSecret("session-secret"),
                expires_in_seconds=2_592_000,
            ),
        )
        mock.authenticate.return_value = self.user
        return mock

    @provide(scope=Scope.APP)
    async def provide_auth_session_cleanup_use_case(self) -> AuthSessionCleanupUseCase:
        return Mock(spec=AuthSessionCleanupUseCase)
