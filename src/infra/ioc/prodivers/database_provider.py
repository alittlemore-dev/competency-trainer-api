from collections.abc import AsyncGenerator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from infra.post_commit_actions import PostCommitActions, RollbackActions
from infra.postgresql import meta
from infra.postgresql.transactions import DatabaseTransactionState


class DatabaseProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def provide_transaction_state(self) -> DatabaseTransactionState:
        return DatabaseTransactionState(rollback_required=False)

    @provide(scope=Scope.REQUEST)
    def provide_post_commit_actions(self) -> PostCommitActions:
        return PostCommitActions(actions=[])

    @provide(scope=Scope.REQUEST)
    def provide_rollback_actions(self) -> RollbackActions:
        return RollbackActions(actions=[])

    @provide(scope=Scope.REQUEST)
    async def provide_async_session(
        self,
        transaction_state: DatabaseTransactionState,
        post_commit_actions: PostCommitActions,
        rollback_actions: RollbackActions,
    ) -> AsyncGenerator[AsyncSession, BaseException | None]:
        async with meta.sessionmaker() as session:
            request_exception = yield session
            if request_exception is not None or transaction_state.rollback_required:
                try:
                    await session.rollback()
                finally:
                    await rollback_actions.run()
            else:
                try:
                    await session.commit()
                except BaseException:
                    try:
                        await session.rollback()
                    finally:
                        await rollback_actions.run()
                    raise
                else:
                    await post_commit_actions.run()
