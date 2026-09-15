from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, Response, get
from verbose_http_exceptions import status

from entrypoints.litestar.response_cache import ResponseCacheDomain
from infra.config.settings import settings
from infra.healthcheck import ReadinessChecker


class HealthcheckController(Controller):
    path = "/healthcheck"

    @get(
        "",
        summary="Basic health check",
        description="Basic application health check. A 200 response means the app is alive.",
        cache=settings.app.get_cache_duration(1),  # 1 second
        cache_key_builder=ResponseCacheDomain.HEALTHCHECK.cache_key_builder,
    )
    async def health(self) -> Response:
        return Response(content="", status_code=status.HTTP_200_OK)

    @get(
        "/ready",
        summary="Readiness check",
        description="Checks application readiness and required dependencies.",
    )
    async def ready(self, checker: FromDishka[ReadinessChecker]) -> Response:
        await checker.check()
        return Response(content="", status_code=status.HTTP_200_OK)


api_router = DishkaRouter("", route_handlers=[HealthcheckController], include_in_schema=False)
