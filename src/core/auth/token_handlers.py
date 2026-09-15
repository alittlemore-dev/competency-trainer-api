from abc import ABC, abstractmethod
from typing import Any

from core.auth.schemas import AccessTokenPayload, TokenPayloadValidationResult
from core.auth.types import Token


class TokenHandler(ABC):
    @abstractmethod
    def decode_token(self, token: Token) -> AccessTokenPayload:
        raise NotImplementedError

    @abstractmethod
    def encode_token(self, payload: AccessTokenPayload) -> Token:
        raise NotImplementedError

    @abstractmethod
    def get_token_remaining_seconds(self, token: Token) -> int | None:
        raise NotImplementedError

    @staticmethod
    def validate_payload_dict(payload: dict[str, Any]) -> TokenPayloadValidationResult:
        payload_keys = set(payload.keys())
        required_keys = {"username", "session_id"}
        missing_keys = required_keys - payload_keys
        if missing_keys != set():
            missing_key_names = ", ".join(sorted(missing_keys))
            return TokenPayloadValidationResult(
                is_valid=False,
                message=f"Token payload is missing required fields: {missing_key_names}.",
            )
        if not isinstance(payload["username"], str):
            return TokenPayloadValidationResult(
                is_valid=False,
                message="Token payload field `username` must be a string.",
            )
        if not isinstance(payload["session_id"], str):
            return TokenPayloadValidationResult(
                is_valid=False,
                message="Token payload field `session_id` must be a string.",
            )
        return TokenPayloadValidationResult(
            is_valid=True,
            message="Token payload is valid.",
        )
