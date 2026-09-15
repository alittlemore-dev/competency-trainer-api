from abc import ABC, abstractmethod
from datetime import date

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.schemas import (
    Article,
    ArticleAnalyticsDailyStats,
    ArticleFilters,
    ArticleFolder,
    ArticleFolders,
    ArticlePublicStatsCollection,
    ArticleReactionCounts,
    ArticleTreeItemData,
    Tag,
    Tags,
)
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum


class ArticlesStorage(ABC):
    @abstractmethod
    async def get_article_by_slug(
        self,
        *,
        slug: str,
        lock: bool,
    ) -> Article:
        raise NotImplementedError

    @abstractmethod
    async def list_articles(self, *, filters: ArticleFilters) -> tuple[list[Article], int]:
        raise NotImplementedError

    @abstractmethod
    async def list_tree_items(
        self,
        *,
        only_published: bool,
        language: LanguageEnum,
    ) -> list[ArticleTreeItemData]:
        raise NotImplementedError

    @abstractmethod
    async def create_article(self, *, article: Article) -> Article:
        raise NotImplementedError

    @abstractmethod
    async def update_article(self, *, article: Article) -> Article:
        raise NotImplementedError

    @abstractmethod
    async def delete_article(self, *, slug: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update_article_publish_status(
        self,
        *,
        slug: str,
        publish_status: PublishStatusEnum,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_folder_by_id(self, *, folder_id: str) -> ArticleFolder:
        raise NotImplementedError

    @abstractmethod
    async def list_folders(self, *, language: LanguageEnum) -> ArticleFolders:
        raise NotImplementedError

    @abstractmethod
    async def next_folder_priority(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def folder_key_exists(self, *, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_folder(self, *, folder: ArticleFolder) -> ArticleFolder:
        raise NotImplementedError

    @abstractmethod
    async def update_folder_priorities(self, *, ordered_ids: tuple[str, ...]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_tags_by_ids(
        self,
        *,
        tag_ids: list[str],
    ) -> Tags:
        raise NotImplementedError

    @abstractmethod
    async def list_tags(
        self,
        *,
        language: LanguageEnum,
        only_with_published_articles: bool,
    ) -> Tags:
        raise NotImplementedError

    @abstractmethod
    async def search_tags(
        self,
        *,
        search_name: str,
        limit: int,
        language: LanguageEnum,
    ) -> Tags:
        raise NotImplementedError

    @abstractmethod
    async def create_tag(self, *, tag: Tag) -> Tag:
        raise NotImplementedError

    @abstractmethod
    async def update_tag(self, *, tag: Tag) -> Tag:
        raise NotImplementedError

    @abstractmethod
    async def delete_tag(self, *, tag_id: str) -> None:
        raise NotImplementedError


class ArticleAnalyticsStorage(ABC):
    @abstractmethod
    async def increment_view(
        self,
        *,
        article_id: str,
        source_category: ArticleViewSourceCategory,
        viewed_on: date | None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def increment_engaged_view(
        self,
        *,
        article_id: str,
        source_category: ArticleViewSourceCategory,
        viewed_on: date | None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_public_stats(self, *, article_ids: list[str]) -> ArticlePublicStatsCollection:
        raise NotImplementedError

    @abstractmethod
    async def set_reaction(
        self,
        *,
        article_id: str,
        article_scoped_voter_hash: str,
        reaction_kind: ArticleReactionKind | None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_daily_stats(
        self,
        *,
        date_from: date,
        date_to: date,
        language: LanguageEnum,
    ) -> list[ArticleAnalyticsDailyStats]:
        raise NotImplementedError

    @abstractmethod
    async def get_reaction_counts(
        self,
        *,
        article_ids: list[str],
    ) -> dict[str, ArticleReactionCounts]:
        raise NotImplementedError
