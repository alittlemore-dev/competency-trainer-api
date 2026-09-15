# ruff: noqa: SLF001
import binascii
import datetime
from unittest.mock import Mock, patch
from zoneinfo import ZoneInfo

import pyseto
import pytest
import pytest_asyncio

from core.auth.exceptions import UnauthorizedError
from core.auth.schemas import AccessTokenPayload
from core.auth.types import Token
from core.schemas import Secret
from infra.auth.token_handlers import PasetoTokenHandler
from tests.unit.mocks.providers.auth import test_private_key_pem, test_public_key_pem


class TestPasetoTokenHandler:
    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def setup(self) -> None:
        self.auth_handler = PasetoTokenHandler(
            public_key_pem=Secret(test_public_key_pem),
            secret_key_pem=Secret(test_private_key_pem),
            token_expire_seconds=1,
        )

    def test_decode_token_rejects_invalid_payload_and_logs_validation_message(self) -> None:
        token = pyseto.encode(key=self.auth_handler._create_secret_key(), payload={"test": "test"})
        with (
            patch("infra.auth.token_handlers.logger") as mock_logger,
            pytest.raises(UnauthorizedError),
        ):
            self.auth_handler.decode_token(Token(token))
        mock_logger.error.assert_called_once_with(
            event="Token payload is missing required fields: session_id, username.",
        )

    def test_decode_token_rejects_non_dict_payload_without_logging_payload(self) -> None:
        with (
            patch("pyseto.decode", return_value=Mock(payload=["token-data"])),
            patch("infra.auth.token_handlers.logger") as mock_logger,
            pytest.raises(UnauthorizedError),
        ):
            self.auth_handler.decode_token(Token(b"token"))
        mock_logger.error.assert_called_once_with(event="Decoded payload is not a dict")

    @pytest.mark.parametrize(
        "error",
        [pyseto.DecryptError, pyseto.VerifyError, binascii.Error, ValueError],
    )
    def test_decode_token_rejects_pyseto_decode_errors(self, error: type[Exception]) -> None:
        token = pyseto.encode(
            key=self.auth_handler._create_secret_key(),
            payload=AccessTokenPayload(username="TEST", session_id="session-id").to_dict(),
        )
        with patch("pyseto.decode", side_effect=error), pytest.raises(UnauthorizedError):
            self.auth_handler.decode_token(Token(token))

    def test_decode_token_returns_domain_user_payload(self) -> None:
        expires_at = datetime.datetime.now(tz=ZoneInfo("Etc/UTC")) + datetime.timedelta(minutes=1)
        token = pyseto.encode(
            key=self.auth_handler._create_secret_key(),
            payload={
                **AccessTokenPayload(username="TEST", session_id="session-id").to_dict(),
                "exp": expires_at.isoformat(),
            },
        )
        decoded_token = self.auth_handler.decode_token(Token(token))
        assert decoded_token.to_dict() == {
            "username": "TEST",
            "session_id": "session-id",
        }

    def test_decode_token_rejects_payload_without_expiration(self) -> None:
        token = pyseto.encode(
            key=self.auth_handler._create_secret_key(),
            payload=AccessTokenPayload(username="TEST", session_id="session-id").to_dict(),
        )

        with pytest.raises(UnauthorizedError):
            self.auth_handler.decode_token(Token(token))

    def test_decode_token_rejects_expired_token(self) -> None:
        expired_at = datetime.datetime.now(tz=ZoneInfo("Etc/UTC")) - datetime.timedelta(seconds=1)
        token = pyseto.encode(
            key=self.auth_handler._create_secret_key(),
            payload={
                **AccessTokenPayload(username="TEST", session_id="session-id").to_dict(),
                "exp": expired_at.isoformat(),
            },
        )

        with pytest.raises(UnauthorizedError):
            self.auth_handler.decode_token(Token(token))

    def test_get_token_remaining_seconds_returns_positive_lifetime(self) -> None:
        token = self.auth_handler.encode_token(
            payload=AccessTokenPayload(username="TEST", session_id="session-id"),
        )

        remaining_seconds = self.auth_handler.get_token_remaining_seconds(token)

        assert remaining_seconds is not None
        assert 0 < remaining_seconds <= self.auth_handler.token_expire_seconds

    def test_get_token_remaining_seconds_returns_none_without_exp(self) -> None:
        token = pyseto.encode(
            key=self.auth_handler._create_secret_key(),
            payload=AccessTokenPayload(username="TEST", session_id="session-id").to_dict(),
        )

        remaining_seconds = self.auth_handler.get_token_remaining_seconds(Token(token))

        assert remaining_seconds is None

    def test_get_token_remaining_seconds_returns_none_for_expired_token(self) -> None:
        expired_at = datetime.datetime.now(tz=ZoneInfo("Etc/UTC")) - datetime.timedelta(seconds=1)
        token = pyseto.encode(
            key=self.auth_handler._create_secret_key(),
            payload={
                **AccessTokenPayload(username="TEST", session_id="session-id").to_dict(),
                "exp": expired_at.isoformat(),
            },
        )

        remaining_seconds = self.auth_handler.get_token_remaining_seconds(Token(token))

        assert remaining_seconds is None
