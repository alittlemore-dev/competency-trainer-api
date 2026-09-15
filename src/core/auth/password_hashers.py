from abc import ABC, abstractmethod

type NeedRehash = bool
type PasswordVerified = bool


class PasswordHasher(ABC):
    @abstractmethod
    def verify_password(
        self,
        plain_password: str | bytes,
        hashed_password: str | bytes,
    ) -> tuple[PasswordVerified, NeedRehash]:
        raise NotImplementedError

    @abstractmethod
    def hash_password(self, password: str | bytes) -> str:
        raise NotImplementedError
