from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock

import dishka
import pytest
from dishka import (
    AsyncContainer,
    Provider,
    make_async_container,
    provide,
)
from litestar.enums import ScopeType
from litestar.types import ASGIApp, Message, Receive, Scope, Send
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent_access.enums import AgentActionEnum
from core.agent_access.storages import AgentAuditStorage
from core.agent_access.use_cases import AgentAuditUseCase
from entrypoints.litestar.middlewares.agent_audit import AgentOutcomeAuditMiddleware
from entrypoints.litestar.middlewares.agent_transaction import AgentTransactionMiddleware
from infra.config.constants import constants
from infra.ioc.prodivers.database_provider import DatabaseProvider
from infra.postgresql import meta
from infra.postgresql.storages.agent_access import AgentAccessDatabaseStorage
from infra.postgresql.transactions import DatabaseTransactionState


class SessionContextManager:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *_args: object) -> None:
        return None


class DistinctSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[AsyncMock] = []

    def __call__(self) -> SessionContextManager:
        session = AsyncMock(spec=AsyncSession)
        self.sessions.append(session)
        return SessionContextManager(session=cast("AsyncSession", session))


class AuditMiddlewareProvider(Provider):
    @provide(scope=dishka.Scope.REQUEST)
    def provide_storage(self, session: AsyncSession) -> AgentAuditStorage:
        return AgentAccessDatabaseStorage(session=session)

    @provide(scope=dishka.Scope.REQUEST)
    def provide_use_case(self, storage: AgentAuditStorage) -> AgentAuditUseCase:
        return AgentAuditUseCase(storage=storage)


@pytest.mark.parametrize("status_code", [400, 401, 409, 500])
async def test_agent_error_response_requires_request_transaction_rollback(
    status_code: int,
) -> None:
    transaction_state = DatabaseTransactionState(rollback_required=False)
    request_container = AsyncMock(spec=AsyncContainer)
    request_container.get.return_value = transaction_state

    async def app(
        _scope: Scope,
        _receive: Receive,
        send: Send,
    ) -> None:
        await send(
            cast(
                "Message",
                {"type": "http.response.start", "status": status_code, "headers": []},
            ),
        )

    middleware = AgentTransactionMiddleware(app=app)
    await middleware(
        cast("Scope", {"state": {"dishka_container": request_container}}),
        AsyncMock(),
        AsyncMock(),
    )

    assert transaction_state.rollback_required is True


async def test_agent_success_response_keeps_request_transaction_committable() -> None:
    transaction_state = DatabaseTransactionState(rollback_required=False)
    request_container = AsyncMock(spec=AsyncContainer)
    request_container.get.return_value = transaction_state

    async def app(
        _scope: Scope,
        _receive: Receive,
        send: Send,
    ) -> None:
        await send(
            cast(
                "Message",
                {"type": "http.response.start", "status": 200, "headers": []},
            ),
        )

    middleware = AgentTransactionMiddleware(app=app)
    await middleware(
        cast("Scope", {"state": {"dishka_container": request_container}}),
        AsyncMock(),
        AsyncMock(),
    )

    assert transaction_state.rollback_required is False


async def test_failure_audit_commits_through_fresh_dishka_request_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = DistinctSessionFactory()
    monkeypatch.setattr(meta, "sessionmaker", session_factory)
    container = make_async_container(DatabaseProvider(), AuditMiddlewareProvider())

    async def app(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send(
            cast(
                "Message",
                {"type": "http.response.start", "status": 409, "headers": []},
            ),
        )

    middleware = AgentOutcomeAuditMiddleware(
        app=cast("ASGIApp", app),
        container=container,
    )
    state = {
        "agent_action": AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
        "agent_client_id": "a" * 32,
        "agent_certificate_id": "b" * 32,
        "agent_audit_request_id": "c" * 32,
        "agent_request_id": "request-id",
        "agent_requested_at": datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
    }
    scope = cast(
        "Scope",
        {
            "type": ScopeType.HTTP,
            "path": f"{constants.agent_access.api_path_prefix}/matrix/question-claims",
            "query_string": b"",
            "state": state,
        },
    )
    try:
        async with container() as current_request_container:
            current_use_case = await current_request_container.get(AgentAuditUseCase)

            await middleware(scope, AsyncMock(), AsyncMock())

            assert len(session_factory.sessions) == 2
            current_session, audit_session = session_factory.sessions
            assert isinstance(current_use_case.storage, AgentAccessDatabaseStorage)
            assert current_use_case.storage.session is current_session
            audit_session.add.assert_called_once()
            audit_session.flush.assert_awaited_once_with()
            audit_session.commit.assert_awaited_once_with()
            current_session.commit.assert_not_awaited()
    finally:
        await container.close()
