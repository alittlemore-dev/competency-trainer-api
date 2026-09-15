# ruff: noqa: S106
from unittest.mock import Mock

import pytest
from litestar.middleware import AuthenticationResult

from core.auth.enums import RoleEnum
from core.auth.schemas import AuthAuthenticateParams, JwtUser
from core.auth.types import Token
from entrypoints.litestar.middlewares.auth import AuthenticationMiddleware
from tests.test_cases import ContainerTestCase
from tests.unit.mocks.providers.auth import test_current_datetime


class TestAuthenticationMiddleware(ContainerTestCase):
    @pytest.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_auth_use_case()
        self.middleware = AuthenticationMiddleware(
            app=Mock(),
            token_header_name="Authorization",
            token_prefix="Bearer",
            container=self.container.container,
            exclude=None,
            exclude_from_auth_key="exclude_from_auth",
            exclude_http_methods=None,
            scopes=None,
        )

    async def test_authenticate_no_token(self) -> None:
        connection_mock = Mock()
        connection_mock.headers = {}
        result = await self.middleware.authenticate_request(connection=connection_mock)
        assert result == AuthenticationResult(user=JwtUser.anonymous(), auth=None)

    async def test_authenticate_token_not_startswith_prefix(self) -> None:
        connection_mock = Mock()
        connection_mock.headers = {"Authorization": "INVALID token"}
        result = await self.middleware.authenticate_request(connection=connection_mock)
        assert result == AuthenticationResult(user=JwtUser.anonymous(), auth=None)

    async def test_authenticate(self) -> None:
        self.use_case.authenticate.return_value = self.factory.core.jwt_user(
            username="test",
            role=RoleEnum.MODERATOR,
        )
        connection_mock = Mock()
        connection_mock.headers = {"Authorization": "Bearer token"}
        result = await self.middleware.authenticate_request(connection=connection_mock)
        assert result == AuthenticationResult(
            user=self.factory.core.jwt_user(username="test", role=RoleEnum.MODERATOR),
            auth=Token(b"token"),
        )
        self.use_case.authenticate.assert_called_once_with(
            params=AuthAuthenticateParams(
                token=Token(b"token"),
                required_role=RoleEnum.MODERATOR,
                current_datetime=test_current_datetime,
            ),
        )
