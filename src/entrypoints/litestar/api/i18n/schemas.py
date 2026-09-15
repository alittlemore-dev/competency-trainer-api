from typing import Annotated, Self

from pydantic import Field

from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.schemas import CamelCaseSchema


class LanguageResponseSchema(CamelCaseSchema):
    code: Annotated[LanguageEnum, Field(title="Language code")]
    label: Annotated[str, Field(title="Language name")]

    @classmethod
    def from_language(cls, *, language: LanguageEnum, label: str) -> Self:
        return cls(code=language, label=label)


class LanguagesResponseSchema(CamelCaseSchema):
    default_language: Annotated[LanguageEnum, Field(title="Default language")]
    languages: Annotated[list[LanguageResponseSchema], Field(title="Available languages")]


class I18nBundleResponseSchema(CamelCaseSchema):
    language: Annotated[LanguageEnum, Field(title="Language")]
    messages: Annotated[dict[str, str], Field(title="Translations")]
