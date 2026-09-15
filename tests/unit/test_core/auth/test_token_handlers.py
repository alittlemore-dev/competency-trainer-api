from core.auth.token_handlers import TokenHandler


class TestTokenHandler:
    def test_valid_payload_not_valid_payload_fields(self) -> None:
        payload_dict = {"password": "test", "field": "test"}
        result = TokenHandler.validate_payload_dict(payload_dict)
        assert result.is_valid is False
        assert result.message == "Token payload is missing required fields: session_id, username."

    def test_valid_payload_username_not_str(self) -> None:
        payload_dict = {"username": 25, "session_id": "session-id"}
        result = TokenHandler.validate_payload_dict(payload_dict)
        assert result.is_valid is False
        assert result.message == "Token payload field `username` must be a string."

    def test_valid_payload_session_id_not_str(self) -> None:
        payload_dict = {"username": "test", "session_id": 25}
        result = TokenHandler.validate_payload_dict(payload_dict)
        assert result.is_valid is False
        assert result.message == "Token payload field `session_id` must be a string."

    def test_valid_payload(self) -> None:
        payload_dict = {"username": "test", "session_id": "session-id"}
        result = TokenHandler.validate_payload_dict(payload_dict)
        assert result.is_valid is True
        assert result.message == "Token payload is valid."
