from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from core.contacts.schemas import ContactMe
from core.contacts.storages import ContactMeStorage
from infra.postgresql.models import ContactMeModel


@dataclass(kw_only=True)
class ContactMeDatabaseStorage(ContactMeStorage):
    session: AsyncSession

    async def create_contact_me_request(self, form: ContactMe) -> None:
        contact_me_model = ContactMeModel.from_domain_schema(form=form)
        self.session.add(contact_me_model)
        await self.session.flush()
