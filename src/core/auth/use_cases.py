from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta

from core.account.storages import UserAccountStorage
from core.auth.enums import AuthSessionAuthMethodEnum
from core.auth.event_dispatchers import AuthEventReporter
from core.auth.exceptions import (
    AuthSessionNotFoundError,
    ForbiddenError,
    UnauthorizedError,
    UserNotFoundError,
)
from core.auth.generators import AuthSessionSecretGenerator
from core.auth.password_hashers import PasswordHasher
from core.auth.schemas import (
    AccessTokenPayload,
    AccessTokenResult,
    AuthAuthenticateParams,
    AuthLoginParams,
    AuthLoginResult,
    AuthLogoutParams,
    AuthRefreshAccessTokenParams,
    AuthRefreshAccessTokenResult,
    AuthSessionCleanupParams,
    AuthSessionCleanupPolicy,
    AuthSessionCleanupResult,
    AuthSessionCleanupStatus,
    AuthSessionCreate,
    AuthSessionCredentials,
    AuthUseCaseConfig,
    User,
)
from core.auth.storages import AuthSessionStorage, AuthStorage, TokenRevocationStorage
from core.auth.token_handlers import TokenHandler
from core.auth.types import Token


@dataclass(kw_only=True, slots=True, frozen=True)
class AuthUseCase:
    hasher: PasswordHasher
    token_handler: TokenHandler
    auth_storage: AuthStorage
    token_revocation_storage: TokenRevocationStorage
    auth_session_storage: AuthSessionStorage
    user_storage: UserAccountStorage
    event_reporter: AuthEventReporter
    auth_session_secret_generator: AuthSessionSecretGenerator

    async def login(
        self,
        *,
        config: AuthUseCaseConfig,
        params: AuthLoginParams,
    ) -> AuthLoginResult:
        try:
            user = await self.user_storage.get_user_by_username(username=params.username)
        except UserNotFoundError as exc:
            self.event_reporter.report_login_user_not_found(username=params.username)
            raise UnauthorizedError from exc
        if not user.has_role(role=params.required_role):
            self.event_reporter.report_login_role_forbidden(
                username=user.username,
                required_role=params.required_role,
            )
            raise ForbiddenError
        if not user.is_active:
            self.event_reporter.report_login_inactive_user(username=user.username)
            raise UnauthorizedError
        verified, need_rehash = self.hasher.verify_password(
            plain_password=params.password,
            hashed_password=user.password_hash.get_secret_value(),
        )
        if not verified:
            self.event_reporter.report_login_password_verification_failed(username=user.username)
            raise UnauthorizedError
        if need_rehash:
            await self.auth_storage.update_user_password_hash(
                username=params.username,
                password_hash=self.hasher.hash_password(params.password),
            )
        session_secret = self.auth_session_secret_generator.generate_secret()
        session_absolute_expires_at = params.current_datetime + timedelta(
            seconds=config.session_absolute_expires_in_seconds,
        )
        session_expires_at = min(
            params.current_datetime + timedelta(seconds=config.session_expires_in_seconds),
            session_absolute_expires_at,
        )
        session = await self.auth_session_storage.create_session(
            session=AuthSessionCreate(
                username=user.username,
                secret_hash=self.auth_session_secret_generator.hash_secret(secret=session_secret),
                expires_at=session_expires_at,
                absolute_expires_at=session_absolute_expires_at,
                is_revoked=False,
                last_used_at=params.current_datetime,
                auth_method=AuthSessionAuthMethodEnum.PASSWORD,
                client_metadata=params.client_metadata,
            ),
        )
        return AuthLoginResult(
            access_token=self._issue_access_token(
                payload=AccessTokenPayload(username=user.username, session_id=session.id),
                expires_in_seconds=config.access_token_expires_in_seconds,
            ),
            session=AuthSessionCredentials(
                secret=session_secret,
                expires_in_seconds=int(
                    (session_expires_at - params.current_datetime).total_seconds(),
                ),
            ),
        )

    async def authenticate(self, *, params: AuthAuthenticateParams) -> User:
        if await self.token_revocation_storage.is_token_revoked(token=params.token):
            self.event_reporter.report_authentication_revoked_token_used()
            raise UnauthorizedError
        payload = self.token_handler.decode_token(params.token)
        try:
            session = await self.auth_session_storage.get_session_by_id(
                session_id=payload.session_id,
            )
        except AuthSessionNotFoundError as exc:
            raise UnauthorizedError from exc
        if not session.is_active_at(now=params.current_datetime):
            raise UnauthorizedError
        if session.username != payload.username:
            raise UnauthorizedError
        try:
            user = await self.user_storage.get_user_by_username(username=payload.username)
        except UserNotFoundError as exc:
            self.event_reporter.report_authentication_user_not_found(username=payload.username)
            raise UnauthorizedError from exc
        if not user.has_role(role=params.required_role):
            self.event_reporter.report_authentication_role_forbidden(
                username=user.username,
                required_role=params.required_role,
            )
            raise ForbiddenError
        if not user.is_active:
            self.event_reporter.report_authentication_inactive_user(username=user.username)
            raise UnauthorizedError
        return user

    async def refresh_access_token(
        self,
        *,
        config: AuthUseCaseConfig,
        params: AuthRefreshAccessTokenParams,
    ) -> AuthRefreshAccessTokenResult:
        try:
            session = await self.auth_session_storage.get_session_by_secret_hash(
                secret_hash=self.auth_session_secret_generator.hash_secret(
                    secret=params.session_secret,
                ),
            )
        except AuthSessionNotFoundError as exc:
            raise UnauthorizedError from exc
        if not session.is_active_at(now=params.current_datetime):
            raise UnauthorizedError
        try:
            user = await self.user_storage.get_user_by_username(username=session.username)
        except UserNotFoundError as exc:
            self.event_reporter.report_authentication_user_not_found(username=session.username)
            raise UnauthorizedError from exc
        if not user.has_role(role=params.required_role):
            self.event_reporter.report_authentication_role_forbidden(
                username=user.username,
                required_role=params.required_role,
            )
            raise ForbiddenError
        if not user.is_active:
            self.event_reporter.report_authentication_inactive_user(username=user.username)
            raise UnauthorizedError
        new_session_expires_at = session.refreshed_expires_at(
            now=params.current_datetime,
            idle_expires_in_seconds=config.session_expires_in_seconds,
        )
        try:
            await self.auth_session_storage.extend_session_expiry(
                session_id=session.id,
                expires_at=new_session_expires_at,
                last_used_at=params.current_datetime,
            )
        except AuthSessionNotFoundError as exc:
            raise UnauthorizedError from exc
        return AuthRefreshAccessTokenResult(
            access_token=self._issue_access_token(
                payload=AccessTokenPayload(username=user.username, session_id=session.id),
                expires_in_seconds=config.access_token_expires_in_seconds,
            ),
            session=AuthSessionCredentials(
                secret=params.session_secret,
                expires_in_seconds=int(
                    (new_session_expires_at - params.current_datetime).total_seconds(),
                ),
            ),
        )

    async def logout(self, *, params: AuthLogoutParams) -> None:
        if params.session_secret is not None:
            with suppress(AuthSessionNotFoundError):
                await self.auth_session_storage.revoke_session_by_secret_hash(
                    secret_hash=self.auth_session_secret_generator.hash_secret(
                        secret=params.session_secret
                    ),
                )
        try:
            remaining_seconds = self.token_handler.get_token_remaining_seconds(params.token)
        except UnauthorizedError:
            self.event_reporter.report_logout_invalid_token()
            return
        if remaining_seconds is None:
            self.event_reporter.report_logout_token_without_remaining_lifetime()
            return
        await self.token_revocation_storage.revoke_token(
            token=params.token,
            expires_in_seconds=remaining_seconds,
        )

    def _issue_access_token(
        self,
        *,
        payload: AccessTokenPayload,
        expires_in_seconds: int,
    ) -> AccessTokenResult:
        token = Token(
            self.token_handler.encode_token(
                payload=payload,
            ),
        )
        return AccessTokenResult(
            token=token,
            expires_in_seconds=expires_in_seconds,
        )


@dataclass(kw_only=True, slots=True, frozen=True)
class AuthSessionCleanupUseCase:
    auth_session_storage: AuthSessionStorage

    async def get_cleanup_status(
        self,
        *,
        policy: AuthSessionCleanupPolicy,
        params: AuthSessionCleanupParams,
    ) -> AuthSessionCleanupStatus:
        counts = await self.auth_session_storage.count_cleanup_sessions(
            expired_at=params.current_datetime,
            expiring_soon_at=params.current_datetime + timedelta(days=policy.expiring_soon_days),
        )
        return AuthSessionCleanupStatus(
            expired_count=counts.expired_count,
            expiring_soon_count=counts.expiring_soon_count,
            expiring_soon_days=policy.expiring_soon_days,
            scheduled_prune_interval_seconds=policy.scheduled_prune_interval_seconds,
        )

    async def prune_expired_sessions(
        self,
        *,
        policy: AuthSessionCleanupPolicy,
        params: AuthSessionCleanupParams,
    ) -> AuthSessionCleanupResult:
        deleted_count = await self.auth_session_storage.delete_expired_sessions(
            expires_at=params.current_datetime,
        )
        counts = await self.auth_session_storage.count_cleanup_sessions(
            expired_at=params.current_datetime,
            expiring_soon_at=params.current_datetime + timedelta(days=policy.expiring_soon_days),
        )
        return AuthSessionCleanupResult(
            deleted_count=deleted_count,
            expired_count=counts.expired_count,
            expiring_soon_count=counts.expiring_soon_count,
            expiring_soon_days=policy.expiring_soon_days,
            scheduled_prune_interval_seconds=policy.scheduled_prune_interval_seconds,
        )
