from dataclasses import dataclass

from core.enums import LabeledStrEnum
from core.exceptions import DomainError


class RoleEnum(LabeledStrEnum):
    ANON = "anon", "Анонимный"
    USER = "user", "Пользователя"
    MODERATOR = "moderator", "Модератор"
    ADMIN = "admin", "Администратор"
    OWNER = "owner", "Владелец"


@dataclass(frozen=True, slots=True, kw_only=True)
class UserIdentity:
    username: str
    role: RoleEnum

    @property
    def is_anon(self) -> bool:
        return self.role == RoleEnum.ANON

    @property
    def is_owner(self) -> bool:
        return self.role == RoleEnum.OWNER

    @property
    def is_admin(self) -> bool:
        return self.role == RoleEnum.ADMIN

    @property
    def can_manage_content(self) -> bool:
        return self.role in {RoleEnum.OWNER, RoleEnum.ADMIN, RoleEnum.MODERATOR}

    @property
    def can_manage_team(self) -> bool:
        return self.role in {RoleEnum.OWNER, RoleEnum.ADMIN}

    @classmethod
    def anonymous(cls) -> UserIdentity:
        return cls(username="anonymous", role=RoleEnum.ANON)


class UnauthorizedError(DomainError):
    message = "Unauthorized error"


class ForbiddenError(DomainError):
    message = "Forbidden error"
