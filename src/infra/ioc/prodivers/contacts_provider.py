from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from core.contacts.storages import ContactMeStorage
from core.contacts.use_cases import ContactsUseCase
from infra.postgresql.storages.contacts import ContactMeDatabaseStorage


class ContactsProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def provide_contact_me_storage(
        self,
        session: AsyncSession,
    ) -> ContactMeStorage:
        return ContactMeDatabaseStorage(session=session)

    @provide(scope=Scope.REQUEST)
    async def provide_contacts_use_case(
        self,
        storage: ContactMeStorage,
    ) -> ContactsUseCase:
        return ContactsUseCase(storage=storage)
