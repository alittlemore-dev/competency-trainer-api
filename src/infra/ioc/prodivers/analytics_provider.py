from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from core.analytics.schemas import AnalyticsConfig
from core.analytics.storages import AnalyticsStorage
from core.analytics.use_cases import AnalyticsUseCase
from core.articles.storages import ArticleAnalyticsStorage
from core.competency_matrix.storages import CompetencyMatrixStorage
from infra.config.constants import constants
from infra.config.settings import settings
from infra.postgresql.storages.analytics import AnalyticsDatabaseStorage


class AnalyticsProvider(Provider):
    @provide(scope=Scope.REQUEST)
    def provide_storage(self, session: AsyncSession) -> AnalyticsStorage:
        return AnalyticsDatabaseStorage(session=session)

    @provide(scope=Scope.APP)
    def provide_config(self) -> AnalyticsConfig:
        return AnalyticsConfig(
            secret=settings.app.secret_key.to_domain_secret(),
            receipt_retention_days=constants.analytics.receipt_retention_days,
        )

    @provide(scope=Scope.REQUEST)
    def provide_use_case(
        self,
        storage: AnalyticsStorage,
        matrix_storage: CompetencyMatrixStorage,
        article_storage: ArticleAnalyticsStorage,
    ) -> AnalyticsUseCase:
        return AnalyticsUseCase(
            storage=storage, matrix_storage=matrix_storage, article_storage=article_storage
        )
