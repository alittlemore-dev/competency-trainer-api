from typing import cast
from unittest.mock import AsyncMock

from backend_sdk import Principal, RoleEnum
from dishka import Provider, Scope, provide
from litestar.types import ASGIApp, Receive, Send
from litestar.types import Scope as ASGIScope

from core.identity import UserIdentity


class TestIdentityController:
    __test__ = False

    def __init__(self, user: UserIdentity) -> None:
        self.authenticate = AsyncMock(return_value=user)

    @property
    def user(self) -> UserIdentity:
        return cast("UserIdentity", self.authenticate.return_value)


class TestIdentityMiddleware:
    __test__ = False

    def __init__(self, app: ASGIApp, controller: TestIdentityController) -> None:
        self.app = app
        self.controller = controller

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        user = self.controller.user
        scope["user"] = Principal(
            username=user.username,
            role=RoleEnum(user.role.value),
        )
        scope["auth"] = None
        await self.app(scope, receive, send)


class TestIdentityProvider(Provider):
    __test__ = False

    def __init__(self, controller: TestIdentityController) -> None:
        super().__init__()
        self.controller = controller

    @provide(scope=Scope.APP)
    async def provide_identity_controller(self) -> TestIdentityController:
        return self.controller
