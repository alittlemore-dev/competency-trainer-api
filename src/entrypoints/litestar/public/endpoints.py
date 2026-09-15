from dishka.integrations.litestar import DishkaRouter, FromDishka
from litestar import Controller, Response, get
from verbose_http_exceptions import status

from core.articles.use_cases import ArticlesUseCase
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from entrypoints.litestar.public.discovery import PublicDiscoveryUrls, RobotsTxt, SitemapXml


class PublicDiscoveryController(Controller):
    include_in_schema = False

    @get("/sitemap.xml")
    async def sitemap(
        self,
        articles_use_case: FromDishka[ArticlesUseCase],
        matrix_use_case: FromDishka[CompetencyMatrixUseCase],
    ) -> Response:
        articles = await articles_use_case.list_published_articles_for_seo()
        matrix_items = await matrix_use_case.list_published_items_for_seo()
        sitemap = SitemapXml(
            urls=PublicDiscoveryUrls(articles=articles, matrix_items=matrix_items).build(),
        ).render()
        return Response(
            content=sitemap,
            media_type="application/xml",
            status_code=status.HTTP_200_OK,
        )

    @get("/robots.txt")
    async def robots(self) -> Response:
        return Response(
            content=RobotsTxt().render(),
            media_type="text/plain",
            status_code=status.HTTP_200_OK,
        )


public_router = DishkaRouter(
    "",
    route_handlers=[PublicDiscoveryController],
    include_in_schema=False,
)
