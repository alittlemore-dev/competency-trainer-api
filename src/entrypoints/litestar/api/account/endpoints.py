from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, Request, get
from litestar.datastructures import State

from core.auth.schemas import JwtUser
from core.auth.types import Token
from entrypoints.litestar.api.account.schemas import GetBaseCurrentUserAccountResponseSchema


class AccountApiController(Controller):
    path = "/account"
    tags = ["account"]

    @get(
        "/base",
        name="current-user-account-api-handler",
        description="Get current user information plus basic account information.",
    )
    async def get_base_current_user_account(
        self,
        request: Request[JwtUser, Token | None, State],
    ) -> GetBaseCurrentUserAccountResponseSchema:
        return GetBaseCurrentUserAccountResponseSchema.from_domain_schema(schema=request.user)


api_router = DishkaRouter("", route_handlers=[AccountApiController])
