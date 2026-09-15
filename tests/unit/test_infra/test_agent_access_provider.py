from typing import cast
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from infra.ioc.prodivers.agent_access_provider import AgentAccessProvider
from infra.ioc.prodivers.agent_admin_provider import AgentAdminProvider
from infra.ioc.prodivers.database_provider import DatabaseProvider
from infra.ioc.registry import get_providers
from infra.postgresql import meta
from infra.postgresql.transactions import DatabaseTransactionState


class SessionContextManager:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> AsyncSession:
        return self.session

    async def __aexit__(self, *_args: object) -> None:
        return None


class SessionFactory:
    def __init__(self, *, session: AsyncSession) -> None:
        self.session = session

    def __call__(self) -> SessionContextManager:
        return SessionContextManager(session=self.session)


class TestMergedAgentAccessProviders:
    def test_main_registry_contains_human_and_machine_agent_providers(self) -> None:
        provider_types = {type(provider) for provider in get_providers()}

        assert AgentAdminProvider in provider_types
        assert AgentAccessProvider in provider_types
        assert DatabaseProvider in provider_types


class TestDatabaseProviderTransactions:
    async def test_request_session_commits_on_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        session = AsyncMock(spec=AsyncSession)
        session_factory = cast(
            "async_sessionmaker[AsyncSession]",
            SessionFactory(session=session),
        )
        monkeypatch.setattr(meta, "sessionmaker", session_factory)
        provider = DatabaseProvider()
        transaction_state = DatabaseTransactionState(rollback_required=False)
        generator = provider.provide_async_session(
            transaction_state=transaction_state,
            post_commit_actions=provider.provide_post_commit_actions(),
            rollback_actions=provider.provide_rollback_actions(),
        )

        assert await anext(generator) is session
        with pytest.raises(StopAsyncIteration):
            await generator.asend(None)

        session.commit.assert_awaited_once_with()
        session.rollback.assert_not_awaited()

    async def test_request_session_rolls_back_on_escaped_exception(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        session = AsyncMock(spec=AsyncSession)
        session_factory = cast(
            "async_sessionmaker[AsyncSession]",
            SessionFactory(session=session),
        )
        monkeypatch.setattr(meta, "sessionmaker", session_factory)
        provider = DatabaseProvider()
        transaction_state = DatabaseTransactionState(rollback_required=False)
        error_message = "request failed"
        generator = provider.provide_async_session(
            transaction_state=transaction_state,
            post_commit_actions=provider.provide_post_commit_actions(),
            rollback_actions=provider.provide_rollback_actions(),
        )

        assert await anext(generator) is session
        with pytest.raises(StopAsyncIteration):
            await generator.asend(RuntimeError(error_message))

        session.rollback.assert_awaited_once_with()
        session.commit.assert_not_awaited()

    async def test_request_session_rolls_back_when_handled_failure_marks_state(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        session = AsyncMock(spec=AsyncSession)
        session_factory = cast(
            "async_sessionmaker[AsyncSession]",
            SessionFactory(session=session),
        )
        monkeypatch.setattr(meta, "sessionmaker", session_factory)
        provider = DatabaseProvider()
        transaction_state = DatabaseTransactionState(rollback_required=False)
        generator = provider.provide_async_session(
            transaction_state=transaction_state,
            post_commit_actions=provider.provide_post_commit_actions(),
            rollback_actions=provider.provide_rollback_actions(),
        )

        assert await anext(generator) is session
        transaction_state.rollback_required = True
        with pytest.raises(StopAsyncIteration):
            await generator.asend(None)

        session.rollback.assert_awaited_once_with()
        session.commit.assert_not_awaited()

    async def test_cli_request_scope_does_not_need_litestar_request(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        session = AsyncMock(spec=AsyncSession)
        session_factory = cast(
            "async_sessionmaker[AsyncSession]",
            SessionFactory(session=session),
        )
        monkeypatch.setattr(meta, "sessionmaker", session_factory)
        provider = DatabaseProvider()
        transaction_state = provider.provide_transaction_state()
        generator = provider.provide_async_session(
            transaction_state=transaction_state,
            post_commit_actions=provider.provide_post_commit_actions(),
            rollback_actions=provider.provide_rollback_actions(),
        )

        assert await anext(generator) is session
        with pytest.raises(StopAsyncIteration):
            await generator.asend(None)

        session.commit.assert_awaited_once_with()
