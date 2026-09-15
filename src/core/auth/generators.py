import hashlib
import secrets
from dataclasses import dataclass

from core.auth.types import SessionSecret, SessionSecretHash


@dataclass(frozen=True, slots=True, kw_only=True)
class AuthSessionSecretGenerator:
    byte_count: int

    def generate_secret(self) -> SessionSecret:
        return SessionSecret(secrets.token_urlsafe(self.byte_count))

    def hash_secret(self, *, secret: SessionSecret) -> SessionSecretHash:
        return SessionSecretHash(hashlib.sha256(secret.encode()).hexdigest())
