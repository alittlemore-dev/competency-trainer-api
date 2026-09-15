from abc import ABC, abstractmethod

from core.articles.schemas import Article


class ArticleAnalyticsErrorReporter(ABC):
    @abstractmethod
    def report_public_view_tracking_failure(self, *, article: Article, error: Exception) -> None:
        raise NotImplementedError
