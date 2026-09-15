from datetime import datetime
from typing import Annotated

from dishka.integrations.litestar import DishkaRouter, FromDishka
from litestar import Controller, Request, delete, get, post, put, status_codes
from litestar.datastructures import State
from litestar.di import NamedDependency, Provide

from core.articles.enums import ArticleViewSourceCategory
from core.articles.schemas import ArticleAnalyticsConfig, ArticleFilters
from core.articles.use_cases import ArticleAnalyticsUseCase, ArticlesUseCase
from core.auth.schemas import JwtUser
from core.auth.types import Token
from core.enums import PublishStatusEnum
from core.generators import HexUuidIdGenerator
from entrypoints.litestar.api.articles.dependencies import (
    provide_article_filters,
    provide_public_article_filters,
)
from entrypoints.litestar.api.articles.schemas import (
    ArticleAnalyticsStatsResponseSchema,
    ArticleDetailResponseSchema,
    ArticleFolderPriorityUpdateRequestSchema,
    ArticleFolderRequestSchema,
    ArticleFolderResponseSchema,
    ArticleFoldersResponseSchema,
    ArticleListResponseSchema,
    ArticlePublicStatsCollectionResponseSchema,
    ArticleReactionRequestSchema,
    ArticleRequestSchema,
    ArticleTreeResponseSchema,
    TagRequestSchema,
    TagResponseSchema,
    TagsResponseSchema,
)
from entrypoints.litestar.api.parameters import (
    ArticleIdsQuery,
    ArticleSlugPath,
    DateFromQuery,
    DateToQuery,
    LanguageQuery,
    OnlyPublishedQuery,
    SearchLimitQuery,
    SearchNameQuery,
    TagIdPath,
    api_json_body,
)
from entrypoints.litestar.guards import content_manager_guard
from entrypoints.litestar.response_cache import (
    ResponseCacheDomain,
    invalidate_response_cache_domain_for_mutation,
)
from infra.config.constants import constants
from infra.config.settings import settings
from infra.post_commit_actions import PostCommitActions


class PublicArticlesApiController(Controller):
    path = "/articles"
    tags = ["public articles"]

    @get(
        "",
        description="Get the public article list.",
        name="public-articles-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.ARTICLES.cache_key_builder,
        dependencies={"filters": Provide(provide_public_article_filters, sync_to_thread=False)},
    )
    async def list_articles(
        self,
        use_case: FromDishka[ArticlesUseCase],
        filters: NamedDependency[ArticleFilters],
    ) -> ArticleListResponseSchema:
        articles = await use_case.list_articles(filters=filters)
        return ArticleListResponseSchema.from_domain_schema(
            schema=articles,
            language=filters.language,
        )

    @get(
        "/tree",
        description="Get the public article folder tree.",
        name="public-articles-tree-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.ARTICLES.cache_key_builder,
    )
    async def list_articles_tree(
        self,
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
    ) -> ArticleTreeResponseSchema:
        tree = await use_case.list_tree(only_published=True, language=language)
        return ArticleTreeResponseSchema.from_domain_schema(schema=tree)

    @get(
        "/detail/{slug:str}",
        description="Get public article details.",
        name="public-articles-detail-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.ARTICLES.cache_key_builder,
    )
    async def get_article(
        self,
        slug: ArticleSlugPath,
        use_case: FromDishka[ArticlesUseCase],
        language: LanguageQuery,
    ) -> ArticleDetailResponseSchema:
        article = await use_case.get_article(slug=slug, only_published=True)
        return ArticleDetailResponseSchema.from_domain_schema(
            schema=article,
            language=language,
        )

    @get(
        "/public-stats",
        description="Get public article statistics.",
        name="public-articles-public-stats-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def get_public_stats(
        self,
        article_ids: ArticleIdsQuery,
        analytics_use_case: FromDishka[ArticleAnalyticsUseCase],
    ) -> ArticlePublicStatsCollectionResponseSchema:
        stats = await analytics_use_case.get_public_stats(article_ids=article_ids)
        return ArticlePublicStatsCollectionResponseSchema.from_domain_schema(schema=stats)

    @post(
        "/detail/{slug:str}/analytics/view",
        description="Track a public article view.",
        name="public-articles-track-public-view-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def track_public_view(
        self,
        slug: ArticleSlugPath,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[ArticlesUseCase],
        analytics_use_case: FromDishka[ArticleAnalyticsUseCase],
        config: FromDishka[ArticleAnalyticsConfig],
        _language: LanguageQuery,
    ) -> None:
        if request.user.can_manage_content:
            return
        article = await use_case.get_article(slug=slug, only_published=True)
        await analytics_use_case.track_public_view(
            article=article,
            referrer=request.headers.get("referer"),
            config=config,
        )

    @post(
        "/detail/{slug:str}/analytics/engaged-view",
        description="Track an engaged article view.",
        name="public-articles-track-engaged-view-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def track_engaged_view(
        self,
        slug: ArticleSlugPath,
        request: Request[JwtUser, Token | None, State],
        analytics_use_case: FromDishka[ArticleAnalyticsUseCase],
        _language: LanguageQuery,
    ) -> None:
        if request.user.can_manage_content:
            return
        await analytics_use_case.track_engaged_view(
            slug=slug,
            source_category=ArticleViewSourceCategory.UNKNOWN,
        )

    @post(
        "/detail/{slug:str}/reaction",
        description="Set or clear an anonymous article reaction.",
        name="public-articles-set-reaction-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def set_reaction(
        self,
        slug: ArticleSlugPath,
        data: Annotated[
            ArticleReactionRequestSchema,
            api_json_body(
                title="Article reaction request",
                description="Anonymous article reaction state for one browser-scoped client.",
                examples=({"reactionKind": "heart", "clientToken": "article-client-token"},),
            ),
        ],
        analytics_use_case: FromDishka[ArticleAnalyticsUseCase],
        config: FromDishka[ArticleAnalyticsConfig],
        _language: LanguageQuery,
    ) -> None:
        await analytics_use_case.set_reaction(
            slug=slug,
            client_token=data.client_token,
            reaction_kind=data.reaction_kind,
            config=config,
        )

    @get(
        "/tags",
        description="Get the public tag list.",
        name="public-articles-tags-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        cache=settings.app.get_cache_duration(constants.response_cache.default_ttl_seconds),
        cache_key_builder=ResponseCacheDomain.ARTICLES.cache_key_builder,
    )
    async def list_tags(
        self,
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
    ) -> TagsResponseSchema:
        tags = await use_case.list_tags(
            language=language,
            only_with_published_articles=True,
        )
        return TagsResponseSchema.from_domain_schema(schema=tags, language=language)


class AdminArticlesApiController(Controller):
    path = "/articles"
    tags = ["admin articles"]
    guards = [content_manager_guard]

    @get(
        "",
        description="Get the admin article list.",
        name="admin-articles-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
        dependencies={"filters": Provide(provide_article_filters, sync_to_thread=False)},
    )
    async def list_articles(
        self,
        use_case: FromDishka[ArticlesUseCase],
        filters: NamedDependency[ArticleFilters],
    ) -> ArticleListResponseSchema:
        articles = await use_case.list_articles(filters=filters)
        return ArticleListResponseSchema.from_domain_schema(
            schema=articles,
            language=filters.language,
        )

    @post(
        "",
        description="Create an article.",
        name="admin-articles-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_article(  # noqa: PLR0913
        self,
        id_generator: FromDishka[HexUuidIdGenerator],
        request: Request[JwtUser, Token | None, State],
        language: LanguageQuery,
        data: Annotated[
            ArticleRequestSchema,
            api_json_body(
                title="Article request",
                description=(
                    "Article authoring payload with fixed RU/EN translations and SEO metadata."
                ),
                examples=(
                    {
                        "slug": "how-this-site-is-built",
                        "folderId": "00000000000000000000000000000001",
                        "publishStatus": "Draft",
                        "tagIds": ["00000000000000000000000000000002"],
                        "translations": {
                            "ru": {"title": "Как устроен этот сайт", "content": "Текст статьи"},
                            "en": {"title": "How this site is built", "content": "Article text"},
                        },
                        "metadata": {
                            "seoTitleRu": "Как устроен этот сайт",
                            "seoTitleEn": "How this site is built",
                            "seoDescriptionRu": "Технический разбор сайта.",
                            "seoDescriptionEn": "Technical site case study.",
                            "coverImageFileId": "00000000000000000000000000000003",
                            "coverImageAltRu": "Схема сайта",
                            "coverImageAltEn": "Site diagram",
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
        current_datetime: FromDishka[datetime],
    ) -> ArticleDetailResponseSchema:
        article = await use_case.create_article(
            params=data.to_create_schema(
                article_id=id_generator.get_next(),
                author_username=request.user.username,
            ),
            current_datetime=current_datetime,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )
        return ArticleDetailResponseSchema.from_domain_schema(
            schema=article,
            language=language,
        )

    @get(
        "/tree",
        description="Get the admin article folder tree.",
        name="admin-articles-tree-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_articles_tree(
        self,
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
    ) -> ArticleTreeResponseSchema:
        tree = await use_case.list_tree(only_published=False, language=language)
        return ArticleTreeResponseSchema.from_domain_schema(schema=tree)

    @get(
        "/folders",
        description="Get the admin article folder list.",
        name="admin-articles-folders-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_folders(
        self,
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
    ) -> ArticleFoldersResponseSchema:
        folders = await use_case.list_folders(language=language)
        return ArticleFoldersResponseSchema.from_domain_schema(
            schema=folders,
            language=language,
        )

    @post(
        "/folders",
        description="Create an article folder.",
        name="admin-articles-folders-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_folder(  # noqa: PLR0913
        self,
        id_generator: FromDishka[HexUuidIdGenerator],
        request: Request[JwtUser, Token | None, State],
        language: LanguageQuery,
        data: Annotated[
            ArticleFolderRequestSchema,
            api_json_body(
                title="Article folder request",
                description="Localized article folder payload.",
                examples=(
                    {
                        "key": "engineering",
                        "translations": {
                            "ru": {"name": "Инженерия"},
                            "en": {"name": "Engineering"},
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> ArticleFolderResponseSchema:
        folder = await use_case.create_folder(
            params=data.to_create_schema(folder_id=id_generator.get_next()),
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )
        return ArticleFolderResponseSchema.from_domain_schema(
            schema=folder,
            language=language,
        )

    @put(
        "/folders/priorities",
        description="Update article folder priority order.",
        name="admin-articles-folders-priorities-update-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def update_folder_priorities(
        self,
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            ArticleFolderPriorityUpdateRequestSchema,
            api_json_body(
                title="Article folder priority request",
                description="Full ordered list of article folder identifiers.",
                examples=({"orderedIds": ["00000000000000000000000000000001"]},),
            ),
        ],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.update_folder_priorities(params=data.to_schema())
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )

    @get(
        "/detail/{slug:str}",
        description="Get admin article details.",
        name="admin-articles-detail-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def get_article(
        self,
        slug: ArticleSlugPath,
        use_case: FromDishka[ArticlesUseCase],
        only_published: OnlyPublishedQuery,
        language: LanguageQuery,
    ) -> ArticleDetailResponseSchema:
        article = await use_case.get_article(slug=slug, only_published=only_published)
        return ArticleDetailResponseSchema.from_domain_schema(
            schema=article,
            language=language,
        )

    @get(
        "/stats",
        description="Get admin article statistics.",
        name="admin-articles-stats-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def get_stats(
        self,
        analytics_use_case: FromDishka[ArticleAnalyticsUseCase],
        date_from: DateFromQuery,
        date_to: DateToQuery,
        language: LanguageQuery,
    ) -> ArticleAnalyticsStatsResponseSchema:
        stats = await analytics_use_case.get_stats(
            date_from=date_from,
            date_to=date_to,
            language=language,
        )
        return ArticleAnalyticsStatsResponseSchema.from_domain_schema(schema=stats)

    @put(
        "/detail/{slug:str}",
        description="Update an article.",
        name="admin-articles-update-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def update_article(  # noqa: PLR0913
        self,
        slug: ArticleSlugPath,
        request: Request[JwtUser, Token | None, State],
        data: Annotated[
            ArticleRequestSchema,
            api_json_body(
                title="Article request",
                description=(
                    "Article authoring payload with fixed RU/EN translations and SEO metadata."
                ),
                examples=(
                    {
                        "slug": "how-this-site-is-built",
                        "folderId": "00000000000000000000000000000001",
                        "publishStatus": "Draft",
                        "tagIds": ["00000000000000000000000000000002"],
                        "translations": {
                            "ru": {"title": "Как устроен этот сайт", "content": "Текст статьи"},
                            "en": {"title": "How this site is built", "content": "Article text"},
                        },
                        "metadata": {
                            "seoTitleRu": "Как устроен этот сайт",
                            "seoTitleEn": "How this site is built",
                            "seoDescriptionRu": "Технический разбор сайта.",
                            "seoDescriptionEn": "Technical site case study.",
                            "coverImageFileId": "00000000000000000000000000000003",
                            "coverImageAltRu": "Схема сайта",
                            "coverImageAltEn": "Site diagram",
                        },
                    },
                ),
            ),
        ],
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
        current_datetime: FromDishka[datetime],
    ) -> ArticleDetailResponseSchema:
        article = await use_case.update_article(
            slug=slug,
            params=data.to_update_schema(),
            current_datetime=current_datetime,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )
        return ArticleDetailResponseSchema.from_domain_schema(
            schema=article,
            language=language,
        )

    @delete(
        "/detail/{slug:str}",
        description="Delete an article.",
        name="admin-articles-delete-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def delete_article(
        self,
        slug: ArticleSlugPath,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
        current_datetime: FromDishka[datetime],
    ) -> None:
        await use_case.delete_article(
            slug=slug,
            current_datetime=current_datetime,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )

    @post(
        "/detail/{slug:str}/set-draft",
        description='Set article status to "Draft".',
        name="admin-articles-set-draft-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def set_draft_status_to_article(
        self,
        slug: ArticleSlugPath,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.switch_article_publish_status(
            slug=slug,
            publish_status=PublishStatusEnum.DRAFT,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )

    @post(
        "/detail/{slug:str}/set-published",
        description='Set article status to "Published".',
        name="admin-articles-set-published-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def set_published_status_to_article(
        self,
        slug: ArticleSlugPath,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.switch_article_publish_status(
            slug=slug,
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )

    @get(
        "/tags",
        description="Get the admin tag list.",
        name="admin-articles-tags-list-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def list_tags(
        self,
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
    ) -> TagsResponseSchema:
        tags = await use_case.list_tags(
            language=language,
            only_with_published_articles=False,
        )
        return TagsResponseSchema.from_domain_schema(schema=tags, language=language)

    @get(
        "/tags/search",
        description="Search admin tags.",
        name="admin-articles-tags-search-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def search_tags(
        self,
        search_name: SearchNameQuery,
        limit: SearchLimitQuery,
        language: LanguageQuery,
        use_case: FromDishka[ArticlesUseCase],
    ) -> TagsResponseSchema:
        tags = await use_case.search_tags(
            search_name=search_name,
            limit=limit,
            language=language,
        )
        return TagsResponseSchema.from_domain_schema(schema=tags, language=language)

    @post(
        "/tags",
        description="Create a tag.",
        name="admin-articles-tags-create-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def create_tag(  # noqa: PLR0913
        self,
        id_generator: FromDishka[HexUuidIdGenerator],
        request: Request[JwtUser, Token | None, State],
        language: LanguageQuery,
        data: Annotated[
            TagRequestSchema,
            api_json_body(
                title="Article tag request",
                description="Localized article tag payload.",
                examples=(
                    {
                        "slug": "python",
                        "translations": {
                            "ru": {"name": "Python"},
                            "en": {"name": "Python"},
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> TagResponseSchema:
        tag = await use_case.create_tag(
            params=data.to_create_schema(tag_id=id_generator.get_next()),
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )
        return TagResponseSchema.from_domain_schema(schema=tag, language=language)

    @put(
        "/tags/{tag_id:str}",
        description="Update a tag.",
        name="admin-articles-tags-update-api-handler",
        status_code=status_codes.HTTP_200_OK,
    )
    async def update_tag(  # noqa: PLR0913
        self,
        tag_id: TagIdPath,
        request: Request[JwtUser, Token | None, State],
        language: LanguageQuery,
        data: Annotated[
            TagRequestSchema,
            api_json_body(
                title="Article tag request",
                description="Localized article tag payload.",
                examples=(
                    {
                        "slug": "python",
                        "translations": {
                            "ru": {"name": "Python"},
                            "en": {"name": "Python"},
                        },
                    },
                ),
            ),
        ],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> TagResponseSchema:
        tag = await use_case.update_tag(
            tag_id=tag_id,
            params=data.to_update_schema(),
        )
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )
        return TagResponseSchema.from_domain_schema(schema=tag, language=language)

    @delete(
        "/tags/{tag_id:str}",
        description="Delete a tag.",
        name="admin-articles-tags-delete-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def delete_tag(
        self,
        tag_id: TagIdPath,
        request: Request[JwtUser, Token | None, State],
        use_case: FromDishka[ArticlesUseCase],
        post_commit_actions: FromDishka[PostCommitActions],
    ) -> None:
        await use_case.delete_tag(tag_id=tag_id)
        await invalidate_response_cache_domain_for_mutation(
            request=request,
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )


api_router = DishkaRouter("", route_handlers=[PublicArticlesApiController])
admin_router = DishkaRouter("", route_handlers=[AdminArticlesApiController])
