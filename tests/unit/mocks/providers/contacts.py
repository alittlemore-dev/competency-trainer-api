from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.contacts.use_cases import ContactsUseCase


class MockContactsProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_contacts_use_case(
        self,
    ) -> ContactsUseCase:
        return Mock(spec=ContactsUseCase)
