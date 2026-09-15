from datetime import UTC, datetime

from argon2 import PasswordHasher as CryptContext
from dishka import Provider, Scope, provide
from litestar import Request
from litestar.stores.valkey import ValkeyStore
from sqlalchemy.ext.asyncio import AsyncSession
from ua_parser import parse

from core.account.storages import UserAccountStorage
from core.auth.generators import AuthSessionSecretGenerator
from core.auth.password_hashers import PasswordHasher
from core.auth.schemas import (
    AuthSessionCleanupPolicy,
    AuthSessionClientMetadata,
    AuthUseCaseConfig,
)
from core.auth.storages import AuthSessionStorage, AuthStorage, TokenRevocationStorage
from core.auth.token_handlers import TokenHandler
from core.auth.types import RawToken, Token
from core.auth.use_cases import AuthSessionCleanupUseCase, AuthUseCase
from infra.auth.event_dispatchers import StructlogAuthEventReporter
from infra.auth.password_hashers import Argon2PasswordHasher
from infra.auth.token_handlers import PasetoTokenHandler
from infra.config.constants import constants
from infra.config.settings import settings
from infra.postgresql.storages.auth import AuthDatabaseStorage, AuthSessionDatabaseStorage
from infra.valkey.storages import ValkeyTokenRevocationStorage


class AuthProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def raw_token(self, request: Request) -> RawToken:
        return RawToken(request.headers.get(settings.auth.token_header_name, ""))

    @provide(scope=Scope.REQUEST)
    async def token(self, raw_token: RawToken) -> Token:
        return Token(raw_token.split(settings.auth.token_prefix)[-1].strip().encode())

    @provide(scope=Scope.APP)
    async def provide_hasher(self) -> PasswordHasher:
        return Argon2PasswordHasher(context=CryptContext())

    @provide(scope=Scope.APP)
    async def provide_token_handler(self) -> TokenHandler:
        return PasetoTokenHandler(
            public_key_pem=settings.auth.public_key.to_domain_secret(),
            secret_key_pem=settings.auth.private_key.to_domain_secret(),
            token_expire_seconds=settings.auth.token_expire_seconds,
        )

    @provide(scope=Scope.REQUEST)
    async def provide_auth_storage(self, session: AsyncSession) -> AuthStorage:
        return AuthDatabaseStorage(session=session)

    @provide(scope=Scope.REQUEST)
    async def provide_auth_session_storage(self, session: AsyncSession) -> AuthSessionStorage:
        return AuthSessionDatabaseStorage(session=session)

    @provide(scope=Scope.REQUEST)
    async def provide_auth_session_client_metadata(
        self,
        request: Request,
    ) -> AuthSessionClientMetadata:
        user_agent = request.headers.get("user-agent")
        if user_agent is None or user_agent.strip() == "":
            return AuthSessionClientMetadata.empty()
        result = parse(user_agent)
        return AuthSessionClientMetadata.create(
            browser=result.user_agent.family if result.user_agent else None,
            operating_system=result.os.family if result.os else None,
            device_type=result.device.family if result.device else None,
        )

    @provide(scope=Scope.APP)
    async def provide_auth_session_secret_generator(self) -> AuthSessionSecretGenerator:
        return AuthSessionSecretGenerator(byte_count=constants.auth.session_secret_byte_count)

    @provide(scope=Scope.APP)
    async def provide_auth_use_case_config(self) -> AuthUseCaseConfig:
        return AuthUseCaseConfig(
            access_token_expires_in_seconds=settings.auth.token_expire_seconds,
            session_expires_in_seconds=settings.auth.session_expire_seconds,
            session_absolute_expires_in_seconds=settings.auth.session_absolute_expire_seconds,
        )

    @provide(scope=Scope.APP)
    async def provide_auth_session_cleanup_policy(self) -> AuthSessionCleanupPolicy:
        return AuthSessionCleanupPolicy(
            expiring_soon_days=constants.auth.session_expiring_soon_days,
            scheduled_prune_interval_seconds=settings.taskiq.auth_session_prune_interval_seconds,
        )

    @provide(scope=Scope.REQUEST, cache=False)
    async def provide_current_datetime(self) -> datetime:
        return datetime.now(tz=UTC)

    @provide(scope=Scope.APP)
    async def provide_token_revocation_storage(self) -> TokenRevocationStorage:
        return ValkeyTokenRevocationStorage(
            store=ValkeyStore.with_client(
                url=settings.valkey.get_url(
                    db=constants.valkey.databases.auth_revocations,
                ).get_secret_value(),
                db=constants.valkey.databases.auth_revocations,
                port=settings.valkey.port,
                namespace=constants.valkey.namespaces.auth_revocations,
            ),
        )

    @provide(scope=Scope.REQUEST)
    async def provide_auth_use_case(  # noqa: PLR0913
        self,
        hasher: PasswordHasher,
        token_handler: TokenHandler,
        auth_storage: AuthStorage,
        token_revocation_storage: TokenRevocationStorage,
        auth_session_storage: AuthSessionStorage,
        user_storage: UserAccountStorage,
        auth_session_secret_generator: AuthSessionSecretGenerator,
    ) -> AuthUseCase:
        return AuthUseCase(
            hasher=hasher,
            token_handler=token_handler,
            auth_storage=auth_storage,
            token_revocation_storage=token_revocation_storage,
            auth_session_storage=auth_session_storage,
            user_storage=user_storage,
            event_reporter=StructlogAuthEventReporter(),
            auth_session_secret_generator=auth_session_secret_generator,
        )

    @provide(scope=Scope.REQUEST)
    async def provide_auth_session_cleanup_use_case(
        self,
        auth_session_storage: AuthSessionStorage,
    ) -> AuthSessionCleanupUseCase:
        return AuthSessionCleanupUseCase(
            auth_session_storage=auth_session_storage,
        )
