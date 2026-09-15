import pytest_asyncio

from core.auth.schemas import AuthLogoutParams
from core.auth.types import SessionSecret, Token
from tests.test_cases import ApiTestCase


class TestLogoutAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.uuid = await self.container.get_random_uuid()
        self.use_case = await self.container.get_auth_use_case()

    def test_logout_revokes_current_session_cookie(self) -> None:
        response = self.api.post_logout(cookies={"__Secure-msid": "session-secret"})

        set_cookie = response.headers["set-cookie"]
        assert "__Secure-msid=" in set_cookie
        assert "Max-Age=0" in set_cookie
        self.use_case.logout.assert_called_once_with(
            params=AuthLogoutParams(
                token=Token(b"token"),
                session_secret=SessionSecret("session-secret"),
            ),
        )

    def test_logout_requires_csrf_guard_header(self) -> None:
        response = self.api.post_logout(
            cookies={"__Secure-msid": "session-secret"},
            csrf_guard=False,
        )

        assert response.status_code == 403
        self.use_case.logout.assert_not_called()
