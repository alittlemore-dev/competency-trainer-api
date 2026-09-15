# ruff: noqa: S106
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from dishka import make_async_container
from litestar.connection import ASGIConnection
from litestar.middleware import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
    DefineMiddleware,
)
from litestar.testing import TestClient
from litestar.types import ASGIApp
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.schemas import AuthSessionClientMetadata, AuthSessionCreate, JwtUser
from core.auth.types import SessionSecretHash, Token
from entrypoints.litestar.initializers.main import create_litestar_app
from infra.ioc.registry import get_providers
from infra.postgresql.models import AuthSessionModel, UserModel
from infra.postgresql.storages.auth import AuthSessionDatabaseStorage


class IntegrationOwnerAuthenticationMiddleware(AbstractAuthenticationMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(
            app=app,
            exclude=None,
            exclude_from_auth_key="exclude_from_auth",
            exclude_http_methods=None,
            scopes=None,
        )

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        _ = connection
        return AuthenticationResult(
            user=JwtUser(username="owner", role=RoleEnum.OWNER),
            auth=Token(b"integration-owner"),
        )


@pytest_asyncio.fixture
async def full_stack_admin_tools_client(
    session: AsyncSession,
) -> AsyncGenerator[TestClient]:
    now = datetime.now(tz=UTC)
    session.add(
        UserModel(
            username="owner",
            password_hash="unused-password-hash",
            role=RoleEnum.OWNER,
            is_active=True,
        ),
    )
    await session.flush()
    storage = AuthSessionDatabaseStorage(session=session)
    for secret_hash, expires_at in (
        ("a" * 64, now - timedelta(seconds=1)),
        ("b" * 64, now + timedelta(days=1)),
        ("c" * 64, now + timedelta(days=8)),
    ):
        await storage.create_session(
            session=AuthSessionCreate(
                username="owner",
                secret_hash=SessionSecretHash(secret_hash),
                expires_at=expires_at,
                absolute_expires_at=now + timedelta(days=30),
                is_revoked=False,
                last_used_at=now,
                auth_method=AuthSessionAuthMethodEnum.PASSWORD,
                client_metadata=AuthSessionClientMetadata(
                    user_agent_display="Integration browser on Linux",
                    user_agent_browser="Integration browser",
                    user_agent_os="Linux",
                    user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
                ),
            ),
        )
    await session.commit()

    container = make_async_container(*get_providers())
    app = create_litestar_app(
        lifespan=[],
        container=container,
        extra_plugins=[],
        extra_middlewares=[DefineMiddleware(IntegrationOwnerAuthenticationMiddleware)],
    )
    with TestClient(app) as client:
        yield client
    await container.close()


async def test_auth_session_admin_tools_full_stack_status_and_prune(
    full_stack_admin_tools_client: TestClient,
    session: AsyncSession,
) -> None:
    status_response = full_stack_admin_tools_client.get("/api/admin/tools/auth-sessions")

    assert status_response.status_code == 200
    assert status_response.json() == {
        "expiredCount": 1,
        "expiringSoonCount": 1,
        "expiringSoonDays": 7,
        "scheduledPruneIntervalSeconds": 86_400,
    }

    prune_response = full_stack_admin_tools_client.post(
        "/api/admin/tools/auth-sessions/prune",
    )

    assert prune_response.status_code == 200
    assert prune_response.json() == {
        "deletedCount": 1,
        "expiredCount": 0,
        "expiringSoonCount": 1,
        "expiringSoonDays": 7,
        "scheduledPruneIntervalSeconds": 86_400,
    }
    session.expire_all()
    remaining_count = await session.scalar(select(func.count()).select_from(AuthSessionModel))
    assert remaining_count == 2
