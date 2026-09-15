import secrets
import uuid

from core.generators import AbstractGenerator
from core.types import IntId


class ItemIdGenerator(AbstractGenerator[IntId]):
    def get_next(self) -> IntId:
        value = IntId(int(uuid.uuid4().hex[:15], 16))
        sign = secrets.choice([-1, 1])
        return IntId(value * sign)


class ResourceIdGenerator(AbstractGenerator[IntId]):
    def get_next(self) -> IntId:
        return IntId(secrets.randbelow(1_000_000_000_000))
