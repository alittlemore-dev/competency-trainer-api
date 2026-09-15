from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from core.articles.event_dispatchers import ArticleAnalyticsErrorReporter
from core.articles.schemas import ArticleAnalyticsConfig
from core.articles.storages import ArticleAnalyticsStorage, ArticlesStorage
from core.articles.use_cases import (
    ArticleAnalyticsUseCase,
    ArticlesUseCase,
)
from core.files.clients import FileClient
from core.files.services import FileService
from infra.articles.event_dispatchers import StructlogArticleAnalyticsErrorReporter
from infra.config.settings import settings
from infra.postgresql.storages.articles import (
    ArticleAnalyticsDatabaseStorage,
    ArticlesDatabaseStorage,
)


class ArticlesProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def provide_articles_storage(
        self,
        session: AsyncSession,
    ) -> ArticlesStorage:
        return ArticlesDatabaseStorage(session=session)

    @provide(scope=Scope.REQUEST)
    async def provide_article_analytics_storage(
        self,
        session: AsyncSession,
    ) -> ArticleAnalyticsStorage:
        return ArticleAnalyticsDatabaseStorage(session=session)

    @provide(scope=Scope.APP)
    async def provide_article_analytics_error_reporter(self) -> ArticleAnalyticsErrorReporter:
        return StructlogArticleAnalyticsErrorReporter()

    @provide(scope=Scope.APP)
    async def provide_article_analytics_config(self) -> ArticleAnalyticsConfig:
        return ArticleAnalyticsConfig(
            reaction_secret=settings.app.secret_key.to_domain_secret(),
            app_domain=settings.app.domain,
        )

    @provide(scope=Scope.REQUEST)
    async def provide_articles_use_case(
        self,
        storage: ArticlesStorage,
        file_service: FileService,
        file_client: FileClient,
    ) -> ArticlesUseCase:
        return ArticlesUseCase(
            storage=storage,
            file_service=file_service,
            file_client=file_client,
        )

    @provide(scope=Scope.REQUEST)
    async def provide_article_analytics_use_case(
        self,
        storage: ArticlesStorage,
        analytics_storage: ArticleAnalyticsStorage,
        error_reporter: ArticleAnalyticsErrorReporter,
    ) -> ArticleAnalyticsUseCase:
        return ArticleAnalyticsUseCase(
            articles_storage=storage,
            analytics_storage=analytics_storage,
            error_reporter=error_reporter,
        )
