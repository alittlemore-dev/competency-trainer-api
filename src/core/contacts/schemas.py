from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class ContactMe:
    id: str
    name: str | None
    email: str | None
    telegram: str | None
    message: str
