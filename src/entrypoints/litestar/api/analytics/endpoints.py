from datetime import UTC, datetime
from typing import Annotated

from backend_sdk import Principal, RoleEnum
from backend_sdk.integrations.litestar import RequireRole
from dishka import FromDishka
from dishka.integrations.litestar import DishkaRouter
from litestar import Controller, Request, get, post
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide

from core.analytics.schemas import AnalyticsConfig, AnalyticsFilters
from core.analytics.use_cases import AnalyticsUseCase
from entrypoints.litestar.api.analytics.dependencies import provide_analytics_filters
from entrypoints.litestar.api.analytics.schemas import (
    AnalyticsDailyResponse,
    AnalyticsReportResponse,
    AnalyticsVisitRequest,
)
from entrypoints.litestar.api.articles.schemas import ArticleReactionCountsResponseSchema
from entrypoints.litestar.api.parameters import api_json_body


class PublicAnalyticsController(Controller):
    path = "/analytics"
    tags = ["public analytics"]

    @post(
        "/visits",
        description="Record a bounded anonymous public page or matrix question visit.",
        status_code=204,
        opt={"auth_optional": True},
    )
    async def record_visit(
        self,
        data: Annotated[
            AnalyticsVisitRequest,
            api_json_body(
                title="Anonymous public visit",
                description=(
                    "A bounded page category or public matrix question "
                    "with random daily tokens and a coarse source."
                ),
                examples=(
                    {
                        "kind": "Site",
                        "targetId": "articles",
                        "event": "View",
                        "source": "Direct",
                        "visitorToken": "00000000-0000-4000-8000-000000000001",
                        "visitToken": "00000000-0000-4000-8000-000000000002",
                    },
                ),
            ),
        ],
        request: Request[Principal, object | None, State],
        use_case: FromDishka[AnalyticsUseCase],
        config: FromDishka[AnalyticsConfig],
    ) -> None:
        if request.user.can_manage_content or request.headers.get("dnt") == "1":
            return
        await use_case.record_visit(
            visit=data.to_domain_schema(), day=datetime.now(UTC).date(), config=config
        )


class AdminAnalyticsController(Controller):
    path = "/analytics"
    tags = ["admin analytics"]
    guards = [RequireRole(RoleEnum.MODERATOR)]

    @get(
        "/report",
        description="Get private aggregate statistics for an inclusive UTC date range.",
        dependencies={"filters": Provide(provide_analytics_filters, sync_to_thread=False)},
        opt={"pat_permissions": ("competency.articles.read", "competency.matrix.read")},
    )
    async def get_report(
        self,
        filters: NamedDependency[AnalyticsFilters],
        use_case: FromDishka[AnalyticsUseCase],
    ) -> AnalyticsReportResponse:
        report = await use_case.get_report(filters=filters)
        return AnalyticsReportResponse(
            date_from=filters.date_from,
            date_to=filters.date_to,
            kind=filters.kind,
            daily=[AnalyticsDailyResponse.from_domain_schema(schema=row) for row in report.daily],
            current_reactions={
                article_id: ArticleReactionCountsResponseSchema.from_domain_schema(schema=counts)
                for article_id, counts in report.current_reactions.items()
            },
        )


api_router = DishkaRouter("", route_handlers=[PublicAnalyticsController])
admin_router = DishkaRouter("", route_handlers=[AdminAnalyticsController])
