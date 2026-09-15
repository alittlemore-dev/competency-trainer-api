import hmac
from dataclasses import dataclass
from datetime import date, datetime
from hashlib import sha256
from urllib.parse import urlparse

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.event_dispatchers import ArticleAnalyticsErrorReporter
from core.articles.exceptions import (
    ArticleFolderAlreadyExistsError,
    ArticleNotFoundError,
    TagNotFoundError,
)
from core.articles.schemas import (
    Article,
    ArticleAnalyticsConfig,
    ArticleAnalyticsStats,
    ArticleCreateParams,
    ArticleFilters,
    ArticleFolder,
    ArticleFolderCreateParams,
    ArticleFolderPriorityUpdateParams,
    ArticleFolders,
    ArticlePublicStatsCollection,
    Articles,
    ArticleTree,
    ArticleUpdateParams,
    PublishedArticlesForSeo,
    Tag,
    TagCreateParams,
    Tags,
    TagUpdateParams,
)
from core.articles.storages import ArticleAnalyticsStorage, ArticlesStorage
from core.enums import PublishStatusEnum
from core.files.clients import FileClient
from core.files.enums import FilePurpose
from core.files.services import FileService
from core.i18n.enums import LanguageEnum


@dataclass(kw_only=True, slots=True, frozen=True)
class ArticlesUseCase:
    storage: ArticlesStorage
    file_service: FileService
    file_client: FileClient

    async def get_article(self, *, slug: str, only_published: bool) -> Article:
        article = await self.storage.get_article_by_slug(
            slug=slug,
            lock=False,
        )
        if only_published and not article.is_available():
            raise ArticleNotFoundError
        cover_image_file = article.metadata.cover_image_file
        if cover_image_file is None:
            return article.with_cover_image_url(cover_image_url=None)
        return article.with_cover_image_url(
            cover_image_url=self.file_client.get_access_url(
                object_name=cover_image_file.relative_path,
                namespace=cover_image_file.namespace,
            ),
        )

    async def list_articles(self, *, filters: ArticleFilters) -> Articles:
        if filters.page is None or filters.page_size is None:
            message = "pagination required"
            raise ValueError(message)
        articles, total_count = await self.storage.list_articles(filters=filters)
        hydrated_articles: list[Article] = []
        for article in articles:
            cover_image_file = article.metadata.cover_image_file
            cover_image_url = (
                self.file_client.get_access_url(
                    object_name=cover_image_file.relative_path,
                    namespace=cover_image_file.namespace,
                )
                if cover_image_file is not None
                else None
            )
            hydrated_articles.append(article.with_cover_image_url(cover_image_url=cover_image_url))
        return Articles.from_page(
            values=hydrated_articles,
            total_count=total_count,
            page_size=filters.page_size,
        )

    async def list_published_articles_for_seo(self) -> PublishedArticlesForSeo:
        articles, _total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                only_published=True,
                include_tags=False,
                include_files=False,
                order_for_seo=True,
            ),
        )
        available_articles = [article for article in articles if article.is_available()]
        return PublishedArticlesForSeo.from_articles(articles=available_articles)

    async def list_tree(self, *, only_published: bool, language: LanguageEnum) -> ArticleTree:
        items = await self.storage.list_tree_items(
            only_published=only_published,
            language=language,
        )
        return ArticleTree.from_items(items=items)

    async def create_article(
        self,
        *,
        params: ArticleCreateParams,
        current_datetime: datetime,
    ) -> Article:
        tags = await self.storage.get_tags_by_ids(
            tag_ids=params.tag_ids,
        )
        if not tags.all_tags_exist_by_ids(ids=set(params.tag_ids)):
            raise TagNotFoundError
        folder = await self.storage.get_folder_by_id(folder_id=params.folder_id)
        if params.metadata.cover_image_file_id is not None:
            await self.file_service.ensure_files_allowed(
                file_ids=frozenset({params.metadata.cover_image_file_id}),
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            )
        await self.file_service.ensure_files_allowed(
            file_ids=params.content_file_ids,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
        )
        created_article = params.to_article(
            now=current_datetime,
            folder=folder,
            tags=tags,
        )
        await self.file_service.lock_file_usage_transitions(
            file_ids=created_article.managed_file_ids,
        )
        article = await self.storage.create_article(
            article=created_article,
        )
        await self.file_service.sync_file_usages(
            attached_file_ids=created_article.managed_file_ids,
            detached_file_ids=frozenset(),
            orphaned_at=current_datetime,
        )
        cover_image_file = article.metadata.cover_image_file
        if cover_image_file is None:
            return article.with_cover_image_url(cover_image_url=None)
        return article.with_cover_image_url(
            cover_image_url=self.file_client.get_access_url(
                object_name=cover_image_file.relative_path,
                namespace=cover_image_file.namespace,
            ),
        )

    async def update_article(
        self,
        *,
        slug: str,
        params: ArticleUpdateParams,
        current_datetime: datetime,
    ) -> Article:
        existing_article = await self.storage.get_article_by_slug(
            slug=slug,
            lock=True,
        )
        tags = await self.storage.get_tags_by_ids(
            tag_ids=params.tag_ids,
        )
        if not tags.all_tags_exist_by_ids(ids=set(params.tag_ids)):
            raise TagNotFoundError
        folder = await self.storage.get_folder_by_id(folder_id=params.folder_id)
        if params.metadata.cover_image_file_id is not None:
            await self.file_service.ensure_files_allowed(
                file_ids=frozenset({params.metadata.cover_image_file_id}),
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            )
        await self.file_service.ensure_files_allowed(
            file_ids=params.content_file_ids,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
        )
        updated_article = params.to_article(
            existing_article=existing_article,
            now=current_datetime,
            folder=folder,
            tags=tags,
        )
        await self.file_service.lock_file_usage_transitions(
            file_ids=existing_article.managed_file_ids | updated_article.managed_file_ids,
        )
        article = await self.storage.update_article(
            article=updated_article,
        )
        await self.file_service.sync_file_usages(
            attached_file_ids=updated_article.managed_file_ids,
            detached_file_ids=existing_article.managed_file_ids.difference(
                updated_article.managed_file_ids,
            ),
            orphaned_at=current_datetime,
        )
        cover_image_file = article.metadata.cover_image_file
        if cover_image_file is None:
            return article.with_cover_image_url(cover_image_url=None)
        return article.with_cover_image_url(
            cover_image_url=self.file_client.get_access_url(
                object_name=cover_image_file.relative_path,
                namespace=cover_image_file.namespace,
            ),
        )

    async def delete_article(self, *, slug: str, current_datetime: datetime) -> None:
        article = await self.storage.get_article_by_slug(slug=slug, lock=True)
        await self.file_service.lock_file_usage_transitions(
            file_ids=article.managed_file_ids,
        )
        await self.storage.delete_article(slug=slug)
        await self.file_service.sync_file_usages(
            attached_file_ids=frozenset(),
            detached_file_ids=article.managed_file_ids,
            orphaned_at=current_datetime,
        )

    async def switch_article_publish_status(
        self,
        *,
        slug: str,
        publish_status: PublishStatusEnum,
    ) -> None:
        await self.storage.update_article_publish_status(slug=slug, publish_status=publish_status)

    async def list_tags(
        self,
        *,
        language: LanguageEnum,
        only_with_published_articles: bool,
    ) -> Tags:
        return await self.storage.list_tags(
            language=language,
            only_with_published_articles=only_with_published_articles,
        )

    async def search_tags(
        self,
        *,
        search_name: str,
        limit: int,
        language: LanguageEnum,
    ) -> Tags:
        return await self.storage.search_tags(
            search_name=search_name,
            limit=limit,
            language=language,
        )

    async def create_tag(self, *, params: TagCreateParams) -> Tag:
        return await self.storage.create_tag(tag=params.to_tag())

    async def update_tag(
        self,
        *,
        tag_id: str,
        params: TagUpdateParams,
    ) -> Tag:
        return await self.storage.update_tag(tag=params.to_tag(tag_id=tag_id))

    async def delete_tag(self, *, tag_id: str) -> None:
        await self.storage.delete_tag(tag_id=tag_id)

    async def list_folders(self, *, language: LanguageEnum) -> ArticleFolders:
        return await self.storage.list_folders(language=language)

    async def create_folder(self, *, params: ArticleFolderCreateParams) -> ArticleFolder:
        if await self.storage.folder_key_exists(key=params.key):
            raise ArticleFolderAlreadyExistsError
        priority = await self.storage.next_folder_priority()
        return await self.storage.create_folder(folder=params.to_folder(priority=priority))

    async def update_folder_priorities(self, *, params: ArticleFolderPriorityUpdateParams) -> None:
        folders = await self.storage.list_folders(language=LanguageEnum.EN)
        folders.ensure_priority_order_matches(ordered_ids=params.ordered_ids)
        await self.storage.update_folder_priorities(ordered_ids=params.ordered_ids)


@dataclass(kw_only=True, slots=True, frozen=True)
class ArticleAnalyticsUseCase:
    articles_storage: ArticlesStorage
    analytics_storage: ArticleAnalyticsStorage
    error_reporter: ArticleAnalyticsErrorReporter

    async def track_public_view(
        self,
        *,
        article: Article,
        referrer: str | None,
        config: ArticleAnalyticsConfig,
    ) -> None:
        try:
            await self.track_view(
                article=article,
                source_category=self._classify_source_category(referrer=referrer, config=config),
            )
        except Exception as exc:  # noqa: BLE001
            self.error_reporter.report_public_view_tracking_failure(article=article, error=exc)

    async def track_view(
        self,
        *,
        article: Article,
        source_category: ArticleViewSourceCategory,
    ) -> None:
        if not article.is_available():
            return
        await self.analytics_storage.increment_view(
            article_id=article.id,
            source_category=source_category,
            viewed_on=None,
        )

    async def track_engaged_view(
        self,
        *,
        slug: str,
        source_category: ArticleViewSourceCategory,
    ) -> None:
        article = await self._get_published_article(slug=slug)
        await self.analytics_storage.increment_engaged_view(
            article_id=article.id,
            source_category=source_category,
            viewed_on=None,
        )

    async def get_public_stats(self, *, article_ids: list[str]) -> ArticlePublicStatsCollection:
        unique_article_ids = list(dict.fromkeys(article_ids))
        stats = await self.analytics_storage.get_public_stats(article_ids=unique_article_ids)
        return stats.fill_missing(article_ids=unique_article_ids)

    async def set_reaction(
        self,
        *,
        slug: str,
        client_token: str,
        reaction_kind: ArticleReactionKind | None,
        config: ArticleAnalyticsConfig,
    ) -> None:
        article = await self._get_published_article(slug=slug)
        await self.analytics_storage.set_reaction(
            article_id=article.id,
            article_scoped_voter_hash=self._build_article_scoped_voter_hash(
                article_id=article.id,
                client_token=client_token,
                config=config,
            ),
            reaction_kind=reaction_kind,
        )

    async def get_stats(
        self,
        *,
        date_from: date,
        date_to: date,
        language: LanguageEnum,
    ) -> ArticleAnalyticsStats:
        daily = await self.analytics_storage.get_daily_stats(
            date_from=date_from,
            date_to=date_to,
            language=language,
        )
        article_ids = list(dict.fromkeys(item.article_id for item in daily))
        reaction_counts = await self.analytics_storage.get_reaction_counts(article_ids=article_ids)
        return ArticleAnalyticsStats.from_daily_stats(
            date_from=date_from,
            date_to=date_to,
            daily=daily,
            reaction_counts=reaction_counts,
        )

    async def _get_published_article(self, *, slug: str) -> Article:
        article = await self.articles_storage.get_article_by_slug(
            slug=slug,
            lock=False,
        )
        if not article.is_available():
            raise ArticleNotFoundError
        return article

    def _classify_source_category(
        self,
        *,
        referrer: str | None,
        config: ArticleAnalyticsConfig,
    ) -> ArticleViewSourceCategory:
        if not referrer:
            return ArticleViewSourceCategory.DIRECT
        hostname = urlparse(referrer).hostname
        if hostname is None:
            return ArticleViewSourceCategory.UNKNOWN
        normalized_hostname = hostname.lower()
        app_domain = config.app_domain.lower()
        if normalized_hostname == app_domain or normalized_hostname.endswith(f".{app_domain}"):
            return ArticleViewSourceCategory.INTERNAL
        if self._is_search_hostname(hostname=normalized_hostname):
            return ArticleViewSourceCategory.SEARCH
        if self._is_social_hostname(hostname=normalized_hostname):
            return ArticleViewSourceCategory.SOCIAL
        return ArticleViewSourceCategory.EXTERNAL

    def _is_search_hostname(self, *, hostname: str) -> bool:
        return any(
            search_hostname in hostname
            for search_hostname in (
                "google.",
                "yandex.",
                "bing.",
                "duckduckgo.",
                "search.yahoo.",
            )
        )

    def _is_social_hostname(self, *, hostname: str) -> bool:
        return any(
            social_hostname in hostname
            for social_hostname in (
                "facebook.",
                "linkedin.",
                "reddit.",
                "t.me",
                "telegram.",
                "twitter.",
                "x.com",
                "vk.",
            )
        )

    def _build_article_scoped_voter_hash(
        self,
        *,
        article_id: str,
        client_token: str,
        config: ArticleAnalyticsConfig,
    ) -> str:
        message = f"{article_id}:{client_token}".encode()
        return hmac.new(
            config.reaction_secret.get_secret_value().encode(),
            message,
            sha256,
        ).hexdigest()
