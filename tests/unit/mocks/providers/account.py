from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.account.storages import ManagedAccountStorage, UserAccountStorage
from core.account.use_cases import AccountsUseCase


class MockUserAccountProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_user_storage(self) -> UserAccountStorage:
        return Mock(spec=UserAccountStorage)

    @provide(scope=Scope.APP)
    async def provide_managed_account_storage(self) -> ManagedAccountStorage:
        return Mock(spec=ManagedAccountStorage)

    @provide(scope=Scope.APP)
    async def provide_accounts_use_case(self) -> AccountsUseCase:
        return Mock(spec=AccountsUseCase)
