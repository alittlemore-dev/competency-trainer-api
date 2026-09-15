from abc import ABC, abstractmethod

from core.contacts.schemas import ContactMe


class ContactMeStorage(ABC):
    @abstractmethod
    async def create_contact_me_request(self, form: ContactMe) -> None:
        raise NotImplementedError
