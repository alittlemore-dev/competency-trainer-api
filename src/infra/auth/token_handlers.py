import binascii
import datetime
import json
import math
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

import pyseto

from core.auth.exceptions import UnauthorizedError
from core.auth.schemas import AccessTokenPayload
from core.auth.token_handlers import TokenHandler
from core.auth.types import Token
from core.schemas import Secret
from infra.config.loggers import logger


@dataclass(kw_only=True, frozen=True, slots=True)
class PasetoTokenHandler(TokenHandler):
    public_key_pem: Secret[str]
    secret_key_pem: Secret[str]
    token_expire_seconds: int

    def _create_public_key(self) -> pyseto.KeyInterface:
        return pyseto.Key.new(
            version=4,
            purpose="public",
            key=self.public_key_pem.get_secret_value(),
        )

    def _create_secret_key(self) -> pyseto.KeyInterface:
        return pyseto.Key.new(
            version=4,
            purpose="public",
            key=self.secret_key_pem.get_secret_value(),
        )

    def prepare_payload(self, payload: AccessTokenPayload) -> dict[str, Any]:
        payload_dict = payload.to_dict()
        payload_dict["exp"] = (
            datetime.datetime.now(tz=ZoneInfo("Etc/UTC"))
            + datetime.timedelta(seconds=self.token_expire_seconds)
        ).isoformat()
        return payload_dict

    def _decode_payload_dict(self, token: Token) -> dict[str, Any]:
        try:
            decoded = pyseto.decode(keys=self._create_public_key(), token=token).payload
        except (pyseto.DecryptError, pyseto.VerifyError, binascii.Error, ValueError) as err:
            logger.warning(event="Pyseto decode error", exc=err)
            raise UnauthorizedError from err
        try:
            payload_dict = json.loads(decoded) if isinstance(decoded, bytes) else decoded
        except json.JSONDecodeError as err:
            logger.warning(event="Pyseto payload JSON decode error", exc=err)
            raise UnauthorizedError from err
        if not isinstance(payload_dict, dict):
            logger.error(event="Decoded payload is not a dict")
            raise UnauthorizedError
        return payload_dict

    def _read_expires_at(self, payload_dict: dict[str, Any]) -> datetime.datetime | None:
        expires_at_raw = payload_dict.get("exp")
        if not isinstance(expires_at_raw, str):
            return None
        try:
            expires_at = datetime.datetime.fromisoformat(expires_at_raw)
        except ValueError:
            logger.warning(event="Token exp claim is invalid")
            return None
        if expires_at.tzinfo is None:
            return expires_at.replace(tzinfo=ZoneInfo("Etc/UTC"))
        return expires_at

    def _require_unexpired_payload(self, payload_dict: dict[str, Any]) -> None:
        expires_at = self._read_expires_at(payload_dict)
        if expires_at is None:
            logger.warning(event="Token exp claim is missing or invalid")
            raise UnauthorizedError
        if expires_at <= datetime.datetime.now(tz=ZoneInfo("Etc/UTC")):
            logger.warning(event="Token exp claim is expired")
            raise UnauthorizedError

    def decode_token(self, token: Token) -> AccessTokenPayload:
        payload_dict = self._decode_payload_dict(token)
        validation_result = self.validate_payload_dict(payload_dict)
        if validation_result.is_valid:
            self._require_unexpired_payload(payload_dict)
            return AccessTokenPayload.from_dict(payload_dict)
        logger.error(event=validation_result.message)
        raise UnauthorizedError

    def encode_token(self, payload: AccessTokenPayload) -> Token:
        return Token(
            pyseto.encode(
                key=self._create_secret_key(),
                payload=self.prepare_payload(payload),
            ),
        )

    def get_token_remaining_seconds(self, token: Token) -> int | None:
        payload_dict = self._decode_payload_dict(token)
        expires_at = self._read_expires_at(payload_dict)
        if expires_at is None:
            return None
        remaining_seconds = math.ceil(
            (expires_at - datetime.datetime.now(tz=ZoneInfo("Etc/UTC"))).total_seconds(),
        )
        if remaining_seconds <= 0:
            return None
        return remaining_seconds
