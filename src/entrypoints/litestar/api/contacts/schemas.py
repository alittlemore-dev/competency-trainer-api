from typing import Annotated, Self

from pydantic import Field, ValidationInfo, field_validator, model_validator

from core.contacts.schemas import ContactMe
from entrypoints.litestar.api.schemas import CamelCaseSchema
from entrypoints.litestar.api.validation import OptionalEmailString


class ContactMeRequest(CamelCaseSchema):
    name: Annotated[
        str | None,
        Field(
            min_length=1,
            max_length=255,
            description="User name. A full name may be provided.",
            examples=["Dmitriy Lunev"],
        ),
    ]
    email: Annotated[
        OptionalEmailString,
        Field(
            description="User email address.",
            examples=["example@mail.ru"],
        ),
    ]
    telegram: Annotated[
        str | None,
        Field(
            min_length=2,
            max_length=256,
            description="Telegram account for contacting the user.",
            examples=["@alm_dmitriy_dev"],
        ),
    ]
    message: Annotated[
        str,
        Field(
            min_length=1,
            max_length=10000,
            description="Contact message.",
            examples=["I would like to discuss a project."],
        ),
    ]

    @field_validator("telegram", mode="after")
    @classmethod
    def check_telegram(cls, value: str | None, _: ValidationInfo) -> str | None:
        if value is None:
            return value
        max_length = 256
        if value[0] != "@":
            value = "@" + value
        if len(value) > max_length:
            msg = "telegram name too long"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def check_contact_data_filled(self) -> Self:  # noqa: N804
        if all(item is None for item in [self.name, self.email, self.telegram]):
            msg = "name or email or telegram should be filled"
            raise ValueError(msg)
        return self

    def to_schema(self, contact_me_id: str) -> ContactMe:
        return ContactMe(
            id=contact_me_id,
            name=self.name,
            email=self.email,
            telegram=self.telegram,
            message=self.message,
        )
