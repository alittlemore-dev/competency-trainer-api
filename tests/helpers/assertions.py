from typing import Any, cast

from httpx import Response


class AssertsHelper:
    def equals(self, actual: object, expected: object) -> None:
        assert actual == expected

    def status(self, response: Response, expected_status: int) -> None:
        assert response.status_code == expected_status, response.content

    def json_body(self, response: Response, expected_status: int, expected_body: object) -> None:
        self.status(response=response, expected_status=expected_status)
        self.equals(
            actual=response.json(),
            expected=expected_body,
        )

    def error_message(
        self,
        response: Response,
        expected_status: int,
        expected_message: str,
    ) -> dict[str, Any]:
        self.status(response=response, expected_status=expected_status)
        body = cast("dict[str, Any]", response.json())
        assert body["message"] == expected_message
        return body

    def hex_id(self, value: object) -> None:
        assert isinstance(value, str)
        assert len(value) == 32
        assert value == value.lower()
        assert all(character in "0123456789abcdef" for character in value)
