from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.articles.schemas import ArticleAnalyticsConfig, ArticlePublicStatsCollection
from core.articles.use_cases import ArticleAnalyticsUseCase, ArticlesUseCase
from core.schemas import Secret


class MockArticlesProvider(Provider):
    @provide(scope=Scope.APP)
    async def provide_article_analytics_config(self) -> ArticleAnalyticsConfig:
        return ArticleAnalyticsConfig(
            reaction_secret=Secret("article-analytics-test-secret"),
            app_domain="example.com",
        )

    @provide(scope=Scope.APP)
    async def provide_articles_use_case(self) -> ArticlesUseCase:
        return Mock(spec=ArticlesUseCase)

    @provide(scope=Scope.APP)
    async def provide_article_analytics_use_case(self) -> ArticleAnalyticsUseCase:
        mock = Mock(spec=ArticleAnalyticsUseCase)
        mock.get_public_stats.return_value = ArticlePublicStatsCollection(values=[])
        return mock
