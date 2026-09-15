from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from core.account.storages import ManagedAccountStorage, UserAccountStorage
from core.account.use_cases import AccountsUseCase
from core.auth.password_hashers import PasswordHasher
from core.auth.storages import AuthSessionStorage
from infra.postgresql.storages.users import UserAccountDatabaseStorage


class UserAccountProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def provide_user_storage(self, session: AsyncSession) -> UserAccountStorage:
        return UserAccountDatabaseStorage(session=session)

    @provide(scope=Scope.REQUEST)
    async def provide_managed_account_storage(
        self,
        session: AsyncSession,
    ) -> ManagedAccountStorage:
        return UserAccountDatabaseStorage(session=session)

    @provide(scope=Scope.REQUEST)
    async def provide_accounts_use_case(
        self,
        storage: ManagedAccountStorage,
        hasher: PasswordHasher,
        auth_session_storage: AuthSessionStorage,
    ) -> AccountsUseCase:
        return AccountsUseCase(
            storage=storage,
            hasher=hasher,
            auth_session_storage=auth_session_storage,
        )
