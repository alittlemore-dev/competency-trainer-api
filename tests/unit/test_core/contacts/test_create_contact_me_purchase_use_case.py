from unittest.mock import Mock

import pytest

from core.contacts.storages import ContactMeStorage
from core.contacts.use_cases import ContactsUseCase
from tests.test_cases import TestCase


class TestContactsUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=ContactMeStorage)
        self.use_case = ContactsUseCase(storage=self.storage)

    async def test(self) -> None:
        form = self.factory.core.contact_me(
            name="NAME",
            email="example@mail.ru",
            telegram="@telegram",
            message="MESSAGE",
        )
        await self.use_case.create_contact_me_request(form=form)
        self.storage.create_contact_me_request.assert_called_once_with(form=form)
