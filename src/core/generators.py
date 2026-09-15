import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable


class AbstractGenerator[T](ABC):
    @abstractmethod
    def get_next(self) -> T:
        raise NotImplementedError


def generate_uuid4_hex() -> str:
    return uuid.uuid4().hex


class HexUuidIdGenerator(AbstractGenerator[str]):
    def __init__(self, generator: Callable[[], str]) -> None:
        self.generator = generator

    def get_next(self) -> str:
        return self.generator()
