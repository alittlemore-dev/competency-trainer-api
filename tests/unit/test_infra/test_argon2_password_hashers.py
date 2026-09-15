# ruff: noqa: S106
from unittest.mock import Mock

import pytest
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from infra.auth.password_hashers import Argon2PasswordHasher


class TestArgon2PasswordHasher:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.context_mock = Mock(spec=PasswordHasher)
        self.hasher = Argon2PasswordHasher(context=self.context_mock)

    def test_hash_password(self) -> None:
        self.context_mock.hash.return_value = "hashed_password"
        hash_ = self.hasher.hash_password("password")
        assert hash_ == "hashed_password"

    def test_verify_password_returns_false_and_rehash_on_verification_error(self) -> None:
        self.context_mock.verify.side_effect = VerificationError
        verified, need_rehash = self.hasher.verify_password(
            plain_password="password",
            hashed_password="hashed_password",
        )
        assert (verified, need_rehash) == (False, True)

    def test_verify_password_returns_verification_and_rehash_flags(self) -> None:
        self.context_mock.verify.return_value = True
        self.context_mock.check_needs_rehash.return_value = True
        verified, need_rehash = self.hasher.verify_password(
            plain_password="password",
            hashed_password="hashed_password",
        )
        assert (verified, need_rehash) == (True, True)
