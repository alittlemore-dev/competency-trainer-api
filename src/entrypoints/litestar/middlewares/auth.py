from collections.abc import Sequence
from datetime import datetime

from dishka import AsyncContainer
from litestar.connection import ASGIConnection
from litestar.middleware import (
    AbstractAuthenticationMiddleware,
    AuthenticationResult,
)
from litestar.types import ASGIApp, Method, Scopes

from core.auth.enums import RoleEnum
from core.auth.exceptions import UnauthorizedError
from core.auth.schemas import AuthAuthenticateParams, JwtUser
from core.auth.types import Token
from core.auth.use_cases import AuthUseCase


class AuthenticationMiddleware(AbstractAuthenticationMiddleware):
    __slots__ = (
        "app",
        "container",
        "exclude",
        "exclude_http_methods",
        "exclude_opt_key",
        "scopes",
        "token_header_name",
        "token_prefix",
    )

    def __init__(  # noqa: PLR0913
        self,
        app: ASGIApp,
        token_header_name: str,
        token_prefix: str,
        container: AsyncContainer,
        exclude: str | list[str] | None,
        exclude_from_auth_key: str,
        exclude_http_methods: Sequence[Method] | None,
        scopes: Scopes | None,
    ) -> None:
        super().__init__(
            app=app,
            exclude=exclude,
            exclude_from_auth_key=exclude_from_auth_key,
            exclude_http_methods=exclude_http_methods,
            scopes=scopes,
        )
        self.token_header_name = token_header_name
        self.token_prefix = token_prefix
        self.container = container

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        anon_result = AuthenticationResult(user=JwtUser.anonymous(), auth=None)
        token: str | None = connection.headers.get(self.token_header_name)
        if not token or not token.startswith(self.token_prefix):
            return anon_result
        clear_token = Token(token.split(self.token_prefix)[-1].strip().encode())
        async with self.container() as request_container:
            use_case = await request_container.get(AuthUseCase)
            try:
                user = await use_case.authenticate(
                    params=AuthAuthenticateParams(
                        token=clear_token,
                        required_role=RoleEnum.MODERATOR,
                        current_datetime=await request_container.get(datetime),
                    ),
                )
            except UnauthorizedError:
                return anon_result
        return AuthenticationResult(user=JwtUser.from_user(user), auth=clear_token)
