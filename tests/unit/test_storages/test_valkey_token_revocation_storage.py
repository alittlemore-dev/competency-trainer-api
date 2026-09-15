import hashlib
from typing import cast

from litestar.stores.base import Store

from core.auth.types import Token
from infra.valkey.storages import ValkeyTokenRevocationStorage


class FakeStore:
    def __init__(self) -> None:
        self.set_calls: list[tuple[str, str | bytes, int]] = []
        self.exists_calls: list[str] = []
        self.existing_keys: set[str] = set()

    async def set(self, key: str, value: str | bytes, expires_in: int) -> None:
        self.set_calls.append((key, value, expires_in))

    async def exists(self, key: str) -> bool:
        self.exists_calls.append(key)
        return key in self.existing_keys


class TestValkeyTokenRevocationStorage:
    async def test_revoke_token_stores_digest_with_expiration(self) -> None:
        store = FakeStore()
        storage = ValkeyTokenRevocationStorage(store=cast("Store", store))
        token = Token(b"raw-token")

        await storage.revoke_token(token=token, expires_in_seconds=30)

        expected_key = hashlib.sha256(token).hexdigest()
        assert store.set_calls == [(expected_key, b"revoked", 30)]
        assert b"raw-token" not in {call[1] for call in store.set_calls}

    async def test_is_token_revoked_checks_digest(self) -> None:
        store = FakeStore()
        storage = ValkeyTokenRevocationStorage(store=cast("Store", store))
        token = Token(b"raw-token")
        expected_key = hashlib.sha256(token).hexdigest()
        store.existing_keys.add(expected_key)

        is_revoked = await storage.is_token_revoked(token=token)

        assert is_revoked is True
        assert store.exists_calls == [expected_key]
