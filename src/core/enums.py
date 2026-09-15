from enum import Enum
from typing import Any, Self


class BaseEnum(Enum):
    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return str(self.value)

    @classmethod
    def from_value(cls, value: Any) -> Self:  # noqa: ANN401
        for member in cls:
            if member.value == value:
                return member
        msg = f"{value!r} is not a valid {cls.__name__}"
        raise ValueError(msg)


class StrEnum(str, BaseEnum):
    pass


class LabeledStrEnum(StrEnum):
    label: str

    def __new__(cls, value: str, label: str) -> Self:
        member = str.__new__(cls, value)
        member._value_ = value
        member.label = label
        return member


class PublishStatusEnum(LabeledStrEnum):
    DRAFT = "Draft", "Черновик"
    PUBLISHED = "Published", "Опубликовано"

    @classmethod
    def from_storage_value(cls, value: Self | str) -> Self:
        if isinstance(value, cls):
            return value
        try:
            return cls.from_value(value)
        except ValueError:
            return cls[value]
