from typing import Self

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from core.contacts.schemas import ContactMe
from infra.postgresql.models.base import BaseModel
from infra.postgresql.models.mixins.ids import HexUuidIDMixin


class ContactMeModel(HexUuidIDMixin, BaseModel):
    name: Mapped[str | None] = mapped_column(String(length=255))
    email: Mapped[str | None] = mapped_column(String(length=255))
    telegram: Mapped[str | None] = mapped_column(String(length=256))
    message: Mapped[str] = mapped_column()

    @classmethod
    def from_domain_schema(cls, form: ContactMe) -> Self:
        return cls(
            id=form.id,
            name=form.name,
            email=form.email,
            telegram=form.telegram,
            message=form.message,
        )

    def to_domain_schema(self) -> ContactMe:
        return ContactMe(
            id=self.id,
            name=self.name,
            email=self.email,
            telegram=self.telegram,
            message=self.message,
        )
