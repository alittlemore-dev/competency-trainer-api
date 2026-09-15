from dataclasses import dataclass

from core.articles.event_dispatchers import ArticleAnalyticsErrorReporter
from core.articles.schemas import Article
from infra.config.loggers import logger


@dataclass(frozen=True, slots=True)
class StructlogArticleAnalyticsErrorReporter(ArticleAnalyticsErrorReporter):
    def report_public_view_tracking_failure(self, *, article: Article, error: Exception) -> None:
        logger.exception(
            "Could not track public article view",
            article_id=str(article.id),
            article_slug=article.slug,
            exc_info=(type(error), error, error.__traceback__),
        )
