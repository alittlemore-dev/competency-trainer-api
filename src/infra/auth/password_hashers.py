from dataclasses import dataclass

from argon2 import PasswordHasher as Argon2CryptContext
from argon2.exceptions import VerificationError

from core.auth.password_hashers import NeedRehash, PasswordHasher, PasswordVerified


@dataclass(frozen=True, slots=True, kw_only=True)
class Argon2PasswordHasher(PasswordHasher):
    context: Argon2CryptContext

    def verify_password(
        self,
        plain_password: str | bytes,
        hashed_password: str | bytes,
    ) -> tuple[PasswordVerified, NeedRehash]:
        hashed_password_str = (
            hashed_password if isinstance(hashed_password, str) else hashed_password.decode()
        )
        try:
            return (
                self.context.verify(hashed_password, plain_password),
                self.context.check_needs_rehash(hashed_password_str),
            )
        except VerificationError:
            return False, True

    def hash_password(self, password: str | bytes) -> str:
        return self.context.hash(password)
