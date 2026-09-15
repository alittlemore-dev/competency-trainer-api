import pytest_asyncio
from httpx import codes

from core.auth.enums import RoleEnum
from core.auth.schemas import (
    AccessTokenResult,
    AuthRefreshAccessTokenParams,
    AuthRefreshAccessTokenResult,
    AuthSessionCredentials,
    AuthUseCaseConfig,
)
from core.auth.types import SessionSecret, Token
from tests.test_cases import ApiTestCase
from tests.unit.mocks.providers.auth import test_current_datetime


class TestRefreshAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_auth_use_case()
        self.use_case.refresh_access_token.return_value = AuthRefreshAccessTokenResult(
            access_token=AccessTokenResult(
                token=Token(b"NEW_ACCESS"),
                expires_in_seconds=900,
            ),
            session=AuthSessionCredentials(
                secret=SessionSecret("session-secret"),
                expires_in_seconds=60,
            ),
        )

    def test_refresh_requires_csrf_guard_header(self) -> None:
        response = self.api.post_refresh(
            cookies={"__Secure-msid": "session-secret"},
            csrf_guard=False,
        )

        assert response.status_code == codes.FORBIDDEN
        self.use_case.refresh_access_token.assert_not_called()

    def test_refresh_rejects_cross_site_fetch_metadata(self) -> None:
        response = self.api.post_refresh(
            cookies={"__Secure-msid": "session-secret"},
            headers={"Sec-Fetch-Site": "cross-site"},
        )

        assert response.status_code == codes.FORBIDDEN
        self.use_case.refresh_access_token.assert_not_called()

    def test_refresh_returns_new_access_token_from_session_cookie(self) -> None:
        response = self.api.post_refresh(cookies={"__Secure-msid": "session-secret"})

        assert response.status_code == codes.OK
        assert response.json() == {
            "accessToken": "NEW_ACCESS",
            "accessTokenExpiresInSeconds": 900,
        }
        set_cookie = response.headers["set-cookie"]
        assert "__Secure-msid=session-secret" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "Secure" in set_cookie
        assert "SameSite=lax" in set_cookie
        assert "Path=/api/auth" in set_cookie
        assert "Max-Age=60" in set_cookie
        self.use_case.refresh_access_token.assert_called_once_with(
            config=AuthUseCaseConfig(
                access_token_expires_in_seconds=900,
                session_expires_in_seconds=2_592_000,
                session_absolute_expires_in_seconds=2_592_000,
            ),
            params=AuthRefreshAccessTokenParams(
                session_secret=SessionSecret("session-secret"),
                required_role=RoleEnum.MODERATOR,
                current_datetime=test_current_datetime,
            ),
        )
