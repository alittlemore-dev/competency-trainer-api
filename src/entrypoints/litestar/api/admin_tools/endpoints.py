from datetime import datetime

from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, get, post, status_codes

from core.auth.schemas import AuthSessionCleanupParams, AuthSessionCleanupPolicy
from core.auth.use_cases import AuthSessionCleanupUseCase
from core.cache_tools.schemas import CacheToolsPolicy
from core.cache_tools.use_cases import CacheToolsUseCase
from entrypoints.litestar.api.admin_tools.dependencies import CacheWarmOperationIdPath
from entrypoints.litestar.api.admin_tools.schemas import (
    AuthSessionsPruneResponseSchema,
    AuthSessionsStatusResponseSchema,
    CacheStatusResponseSchema,
    CacheWarmOperationResponseSchema,
)
from entrypoints.litestar.guards import team_manager_guard


class AdminToolsApiController(Controller):
    path = "/tools"
    tags = ["admin tools"]
    guards = [team_manager_guard]

    @get(
        "/auth-sessions",
        description="Get expired and soon-expiring auth session counts.",
        name="admin-tools-auth-sessions-status-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=False,
    )
    async def get_auth_sessions_status(
        self,
        current_datetime: FromDishka[datetime],
        use_case: FromDishka[AuthSessionCleanupUseCase],
        policy: FromDishka[AuthSessionCleanupPolicy],
    ) -> AuthSessionsStatusResponseSchema:
        status = await use_case.get_cleanup_status(
            policy=policy,
            params=AuthSessionCleanupParams(current_datetime=current_datetime),
        )
        return AuthSessionsStatusResponseSchema.from_domain_schema(schema=status)

    @post(
        "/auth-sessions/prune",
        description="Delete expired auth sessions and return refreshed counts.",
        name="admin-tools-auth-sessions-prune-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=False,
    )
    async def prune_auth_sessions(
        self,
        current_datetime: FromDishka[datetime],
        use_case: FromDishka[AuthSessionCleanupUseCase],
        policy: FromDishka[AuthSessionCleanupPolicy],
    ) -> AuthSessionsPruneResponseSchema:
        result = await use_case.prune_expired_sessions(
            policy=policy,
            params=AuthSessionCleanupParams(current_datetime=current_datetime),
        )
        return AuthSessionsPruneResponseSchema.from_domain_schema(schema=result)

    @get(
        "/cache",
        description="Get response cache configuration, domain metrics, and last manual warm.",
        name="admin-tools-cache-status-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=False,
    )
    async def get_cache_status(
        self,
        use_case: FromDishka[CacheToolsUseCase],
        policy: FromDishka[CacheToolsPolicy],
    ) -> CacheStatusResponseSchema:
        return CacheStatusResponseSchema.from_domain_schema(
            schema=await use_case.get_status(policy=policy),
        )

    @post(
        "/cache/clear",
        description="Clear response cache domains without enqueueing a warm.",
        name="admin-tools-cache-clear-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=False,
    )
    async def clear_cache(
        self,
        use_case: FromDishka[CacheToolsUseCase],
        policy: FromDishka[CacheToolsPolicy],
    ) -> CacheStatusResponseSchema:
        return CacheStatusResponseSchema.from_domain_schema(
            schema=await use_case.clear(policy=policy),
        )

    @post(
        "/cache/warm",
        description="Enqueue a manual response cache warm operation.",
        name="admin-tools-cache-warm-api-handler",
        status_code=status_codes.HTTP_202_ACCEPTED,
        cache=False,
    )
    async def warm_cache(
        self,
        current_datetime: FromDishka[datetime],
        use_case: FromDishka[CacheToolsUseCase],
    ) -> CacheWarmOperationResponseSchema:
        return CacheWarmOperationResponseSchema.from_domain_schema(
            schema=await use_case.enqueue_manual_warm(
                current_datetime=current_datetime,
            ),
        )

    @get(
        "/cache/warm/{operation_id:str}",
        description="Get a manual response cache warm operation for polling.",
        name="admin-tools-cache-warm-operation-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=False,
    )
    async def get_cache_warm_operation(
        self,
        operation_id: CacheWarmOperationIdPath,
        use_case: FromDishka[CacheToolsUseCase],
    ) -> CacheWarmOperationResponseSchema:
        return CacheWarmOperationResponseSchema.from_domain_schema(
            schema=await use_case.get_manual_warm_operation(operation_id=operation_id),
        )


admin_router = DishkaRouter("", route_handlers=[AdminToolsApiController])
