import time
import uuid
from abc import ABCMeta, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass


class FileNameGenerator(metaclass=ABCMeta):
    @abstractmethod
    def __call__(self, folder: str | None, file_extension: str) -> str:
        raise NotImplementedError

    @staticmethod
    def normalize_extension(extension: str) -> str:
        if not extension:
            return ""
        return extension if extension.startswith(".") else f".{extension}"


@dataclass(kw_only=True, slots=True, frozen=True)
class UUIDFileNameGenerator(FileNameGenerator):
    generator: Callable[[], uuid.UUID]

    def __call__(self, folder: str | None, file_extension: str) -> str:
        normalized_extension = self.normalize_extension(file_extension)
        path = "/".join([(folder or "").strip("/"), self.generator().hex + normalized_extension])
        return path.removeprefix("/")


@dataclass(kw_only=True, slots=True, frozen=True)
class TimestampFileNameGenerator(FileNameGenerator):
    random_suffix_length: int
    random_generator: Callable[[int], str]

    def __call__(self, folder: str | None, file_extension: str) -> str:
        timestamp = int(time.time() * 1_000_000)  # microseconds
        random_suffix = self.random_generator(self.random_suffix_length)
        normalized_extension = self.normalize_extension(file_extension)
        file_name = f"{timestamp}_{random_suffix}{normalized_extension}"
        path = "/".join([(folder or "").strip("/"), file_name])
        return path.removeprefix("/")
