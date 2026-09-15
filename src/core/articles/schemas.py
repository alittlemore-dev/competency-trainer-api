from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime
from math import ceil
from typing import Self

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.exceptions import ArticleFolderPriorityInvalidError
from core.enums import PublishStatusEnum
from core.files.markdown import extract_file_ids_from_markdown
from core.files.schemas import StoredFile
from core.i18n.enums import LanguageEnum
from core.schemas import Secret, ValuedDataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class Tag:
    id: str
    name_ru: str
    name_en: str
    slug: str

    def localized_name(self, *, language: LanguageEnum) -> str:
        if language == LanguageEnum.RU:
            return self.name_ru
        return self.name_en


@dataclass(frozen=True, slots=True, kw_only=True)
class Tags(ValuedDataclass[Tag]):
    def all_tags_exist_by_ids(self, ids: set[str]) -> bool:
        return ids.difference({tag.id for tag in self.values}) == set()


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleFolder:
    id: str
    key: str
    name_ru: str
    name_en: str
    priority: int

    def localized_name(self, *, language: LanguageEnum) -> str:
        if language == LanguageEnum.RU:
            return self.name_ru
        return self.name_en


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleFolders(ValuedDataclass[ArticleFolder]):
    def ensure_priority_order_matches(self, *, ordered_ids: tuple[str, ...]) -> None:
        folder_ids = tuple(folder.id for folder in self.values)
        if len(folder_ids) != len(ordered_ids) or set(folder_ids) != set(ordered_ids):
            raise ArticleFolderPriorityInvalidError


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleMetadata:
    seo_title_ru: str | None
    seo_title_en: str | None
    seo_description_ru: str | None
    seo_description_en: str | None
    cover_image_file_id: str | None
    cover_image_file: StoredFile | None
    cover_image_url: str | None
    cover_image_alt_ru: str | None
    cover_image_alt_en: str | None

    def with_cover_image_url(self, *, cover_image_url: str | None) -> ArticleMetadata:
        return replace(self, cover_image_url=cover_image_url)

    def localized_seo_title(self, *, language: LanguageEnum) -> str | None:
        if language == LanguageEnum.RU:
            return self.seo_title_ru
        return self.seo_title_en

    def localized_seo_description(self, *, language: LanguageEnum) -> str | None:
        if language == LanguageEnum.RU:
            return self.seo_description_ru
        return self.seo_description_en

    def localized_cover_image_alt(self, *, language: LanguageEnum) -> str | None:
        if language == LanguageEnum.RU:
            return self.cover_image_alt_ru
        return self.cover_image_alt_en


@dataclass(frozen=True, slots=True, kw_only=True)
class Article:
    id: str
    slug: str
    title_ru: str
    title_en: str
    content_ru: str
    content_en: str
    folder: ArticleFolder
    author_username: str
    published_at: datetime | None
    publish_status: PublishStatusEnum
    metadata: ArticleMetadata
    content_file_ids: frozenset[str]
    created_at: datetime
    updated_at: datetime
    tags: Tags

    def is_available(self) -> bool:
        return self.publish_status == PublishStatusEnum.PUBLISHED

    @property
    def managed_file_ids(self) -> frozenset[str]:
        cover_image_file_id = self.metadata.cover_image_file_id
        if cover_image_file_id is None:
            return self.content_file_ids
        return self.content_file_ids | frozenset({cover_image_file_id})

    def localized_title(self, *, language: LanguageEnum) -> str:
        if language == LanguageEnum.RU:
            return self.title_ru
        return self.title_en

    def localized_content(self, *, language: LanguageEnum) -> str:
        if language == LanguageEnum.RU:
            return self.content_ru
        return self.content_en

    def localized_folder(self, *, language: LanguageEnum) -> str:
        return self.folder.localized_name(language=language)

    def with_cover_image_url(self, *, cover_image_url: str | None) -> Article:
        return replace(
            self,
            metadata=self.metadata.with_cover_image_url(cover_image_url=cover_image_url),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class PublishedArticleForSeo:
    slug: str
    publish_status: PublishStatusEnum
    updated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class PublishedArticlesForSeo(ValuedDataclass[PublishedArticleForSeo]):
    @classmethod
    def from_articles(cls, *, articles: list[Article]) -> Self:
        return cls(
            values=[
                PublishedArticleForSeo(
                    slug=article.slug,
                    publish_status=article.publish_status,
                    updated_at=article.updated_at,
                )
                for article in articles
            ],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class Articles(ValuedDataclass[Article]):
    total_count: int
    total_pages: int

    @classmethod
    def from_page(cls, *, values: list[Article], total_count: int, page_size: int) -> Self:
        return cls(
            values=values,
            total_count=total_count,
            total_pages=ceil(total_count / page_size) if total_count > 0 else 0,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleFilters:
    page: int | None = None
    page_size: int | None = None
    language: LanguageEnum = LanguageEnum.EN
    only_published: bool | None = None
    publish_status: PublishStatusEnum | None = None
    tag_slug: str | None = None
    published_from: date | None = None
    published_to: date | None = None
    search_query: str | None = None
    include_tags: bool = True
    include_files: bool = True
    order_for_seo: bool = False

    @property
    def limit(self) -> int:
        if self.page_size is None:
            raise ValueError
        return self.page_size

    @property
    def offset(self) -> int:
        if self.page is None or self.page_size is None:
            raise ValueError
        return (self.page - 1) * self.page_size


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleCreateParams:
    id: str
    slug: str
    title_ru: str
    title_en: str
    content_ru: str
    content_en: str
    folder_id: str
    author_username: str
    publish_status: PublishStatusEnum
    metadata: ArticleMetadata
    tag_ids: list[str]

    @property
    def content_file_ids(self) -> frozenset[str]:
        return extract_file_ids_from_markdown(self.content_ru) | extract_file_ids_from_markdown(
            self.content_en,
        )

    def to_article(self, *, now: datetime, folder: ArticleFolder, tags: Tags) -> Article:
        return Article(
            id=self.id,
            slug=self.slug,
            title_ru=self.title_ru,
            title_en=self.title_en,
            content_ru=self.content_ru,
            content_en=self.content_en,
            folder=folder,
            author_username=self.author_username,
            publish_status=self.publish_status,
            metadata=self.metadata,
            content_file_ids=self.content_file_ids,
            published_at=now if self.publish_status == PublishStatusEnum.PUBLISHED else None,
            created_at=now,
            updated_at=now,
            tags=tags,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleUpdateParams:
    slug: str
    title_ru: str
    title_en: str
    content_ru: str
    content_en: str
    folder_id: str
    publish_status: PublishStatusEnum
    metadata: ArticleMetadata
    tag_ids: list[str]

    @property
    def content_file_ids(self) -> frozenset[str]:
        return extract_file_ids_from_markdown(self.content_ru) | extract_file_ids_from_markdown(
            self.content_en,
        )

    def to_article(
        self,
        *,
        existing_article: Article,
        now: datetime,
        folder: ArticleFolder,
        tags: Tags,
    ) -> Article:
        published_at = existing_article.published_at
        if published_at is None and self.publish_status == PublishStatusEnum.PUBLISHED:
            published_at = now
        return Article(
            id=existing_article.id,
            slug=self.slug,
            title_ru=self.title_ru,
            title_en=self.title_en,
            content_ru=self.content_ru,
            content_en=self.content_en,
            folder=folder,
            author_username=existing_article.author_username,
            publish_status=self.publish_status,
            metadata=self.metadata,
            content_file_ids=self.content_file_ids,
            published_at=published_at,
            created_at=existing_article.created_at,
            updated_at=now,
            tags=tags,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleTreeItem:
    title: str
    slug: str
    publish_status: PublishStatusEnum
    published_at: datetime | None
    updated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleTreeItemData:
    folder_id: str
    folder_key: str
    folder: str
    title: str
    slug: str
    publish_status: PublishStatusEnum
    published_at: datetime | None
    updated_at: datetime

    def to_tree_item(self) -> ArticleTreeItem:
        return ArticleTreeItem(
            title=self.title,
            slug=self.slug,
            publish_status=self.publish_status,
            published_at=self.published_at,
            updated_at=self.updated_at,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleTreeFolder:
    folder_id: str
    folder_key: str
    folder: str
    articles: list[ArticleTreeItem]


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleTree:
    folders: list[ArticleTreeFolder]

    @classmethod
    def from_items(cls, *, items: list[ArticleTreeItemData]) -> Self:
        folders: dict[str, ArticleTreeFolder] = {}
        for item in items:
            if item.folder_id not in folders:
                folders[item.folder_id] = ArticleTreeFolder(
                    folder_id=item.folder_id,
                    folder_key=item.folder_key,
                    folder=item.folder,
                    articles=[],
                )
            folders[item.folder_id].articles.append(item.to_tree_item())
        return cls(folders=list(folders.values()))


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleFolderCreateParams:
    id: str
    key: str
    name_ru: str
    name_en: str

    def to_folder(self, *, priority: int) -> ArticleFolder:
        return ArticleFolder(
            id=self.id,
            key=self.key,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=priority,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleFolderPriorityUpdateParams:
    ordered_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleAnalyticsConfig:
    reaction_secret: Secret[str]
    app_domain: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleReactionCounts:
    heart: int
    fire: int
    thinking: int
    neutral: int
    poop: int

    @classmethod
    def zero(cls) -> Self:
        return cls(heart=0, fire=0, thinking=0, neutral=0, poop=0)

    @classmethod
    def from_counts(cls, *, counts: Mapping[ArticleReactionKind, int]) -> Self:
        return cls(
            heart=counts.get(ArticleReactionKind.HEART, 0),
            fire=counts.get(ArticleReactionKind.FIRE, 0),
            thinking=counts.get(ArticleReactionKind.THINKING, 0),
            neutral=counts.get(ArticleReactionKind.NEUTRAL, 0),
            poop=counts.get(ArticleReactionKind.POOP, 0),
        )

    @property
    def total(self) -> int:
        return self.heart + self.fire + self.thinking + self.neutral + self.poop


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticlePublicStats:
    article_id: str
    view_count: int
    reaction_counts: ArticleReactionCounts


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticlePublicStatsCollection(ValuedDataclass[ArticlePublicStats]):
    def by_article_id(self, article_id: str) -> ArticlePublicStats:
        for stats in self.values:
            if stats.article_id == article_id:
                return stats
        return ArticlePublicStats(
            article_id=article_id,
            view_count=0,
            reaction_counts=ArticleReactionCounts.zero(),
        )

    def fill_missing(self, article_ids: list[str]) -> ArticlePublicStatsCollection:
        return ArticlePublicStatsCollection(
            values=[self.by_article_id(article_id) for article_id in article_ids],
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleAnalyticsTotals:
    view_count: int
    engaged_view_count: int
    reaction_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleAnalyticsArticleStats:
    article_id: str
    title: str
    slug: str
    view_count: int
    engaged_view_count: int
    reaction_counts: ArticleReactionCounts

    @classmethod
    def from_daily_stats(
        cls,
        *,
        daily: ArticleAnalyticsDailyStats,
        reaction_counts: ArticleReactionCounts,
    ) -> Self:
        return cls(
            article_id=daily.article_id,
            title=daily.title,
            slug=daily.slug,
            view_count=daily.view_count,
            engaged_view_count=daily.engaged_view_count,
            reaction_counts=reaction_counts,
        )

    def with_daily_stats(self, *, daily: ArticleAnalyticsDailyStats) -> Self:
        return self.__class__(
            article_id=self.article_id,
            title=self.title,
            slug=self.slug,
            view_count=self.view_count + daily.view_count,
            engaged_view_count=self.engaged_view_count + daily.engaged_view_count,
            reaction_counts=self.reaction_counts,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleAnalyticsDailyStats:
    article_id: str
    title: str
    slug: str
    date: date
    source_category: ArticleViewSourceCategory
    view_count: int
    engaged_view_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class ArticleAnalyticsStats:
    date_from: date
    date_to: date
    totals: ArticleAnalyticsTotals
    articles: list[ArticleAnalyticsArticleStats]
    daily: list[ArticleAnalyticsDailyStats]

    @classmethod
    def from_daily_stats(
        cls,
        *,
        date_from: date,
        date_to: date,
        daily: list[ArticleAnalyticsDailyStats],
        reaction_counts: dict[str, ArticleReactionCounts],
    ) -> Self:
        articles = cls._build_article_stats(daily=daily, reaction_counts=reaction_counts)
        return cls(
            date_from=date_from,
            date_to=date_to,
            totals=ArticleAnalyticsTotals(
                view_count=sum(item.view_count for item in daily),
                engaged_view_count=sum(item.engaged_view_count for item in daily),
                reaction_count=sum(item.reaction_counts.total for item in articles),
            ),
            articles=articles,
            daily=daily,
        )

    @classmethod
    def _build_article_stats(
        cls,
        *,
        daily: list[ArticleAnalyticsDailyStats],
        reaction_counts: dict[str, ArticleReactionCounts],
    ) -> list[ArticleAnalyticsArticleStats]:
        article_stats: dict[str, ArticleAnalyticsArticleStats] = {}
        for item in daily:
            existing = article_stats.get(item.article_id)
            if existing is None:
                article_stats[item.article_id] = ArticleAnalyticsArticleStats.from_daily_stats(
                    daily=item,
                    reaction_counts=reaction_counts.get(
                        item.article_id,
                        ArticleReactionCounts.zero(),
                    ),
                )
            else:
                article_stats[item.article_id] = existing.with_daily_stats(daily=item)
        return sorted(article_stats.values(), key=lambda item: (-item.view_count, item.title))


@dataclass(frozen=True, slots=True, kw_only=True)
class TagCreateParams:
    id: str
    name_ru: str
    name_en: str
    slug: str

    def to_tag(self) -> Tag:
        return Tag(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            slug=self.slug,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class TagUpdateParams:
    name_ru: str
    name_en: str
    slug: str

    def to_tag(self, tag_id: str) -> Tag:
        return Tag(
            id=tag_id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            slug=self.slug,
        )
