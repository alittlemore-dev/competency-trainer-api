from typing import Self

from core.enums import LabeledStrEnum


class RoleEnum(LabeledStrEnum):
    ANON = "anon", "Анонимный"
    USER = "user", "Пользователя"
    MODERATOR = "moderator", "Модератор"
    ADMIN = "admin", "Администратор"
    OWNER = "owner", "Владелец"


class AuthSessionAuthMethodEnum(LabeledStrEnum):
    PASSWORD = "password", "Пароль"


class AuthSessionDeviceTypeEnum(LabeledStrEnum):
    DESKTOP = "desktop", "Компьютер"
    MOBILE = "mobile", "Телефон"
    TABLET = "tablet", "Планшет"
    BOT = "bot", "Бот"
    UNKNOWN = "unknown", "Неизвестно"

    @classmethod
    def from_device_type(cls, value: str | None) -> Self:
        if value is None:
            return cls.UNKNOWN
        normalized = value.strip().casefold()
        if normalized == "":
            return cls.UNKNOWN
        device_types = {
            "computer": cls.DESKTOP,
            "desktop": cls.DESKTOP,
            "mac": cls.DESKTOP,
            "mobile": cls.MOBILE,
            "phone": cls.MOBILE,
            "smartphone": cls.MOBILE,
            "iphone": cls.MOBILE,
            "tablet": cls.TABLET,
            "ipad": cls.TABLET,
            "bot": cls.BOT,
            "crawler": cls.BOT,
            "spider": cls.BOT,
        }
        return device_types.get(normalized, cls.UNKNOWN)
