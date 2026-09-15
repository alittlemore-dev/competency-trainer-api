from core.articles.schemas import ArticleFilters
from entrypoints.litestar.api.parameters import (
    LanguageQuery,
    PageQuery,
    PageSizeQuery,
    PublishedFromQuery,
    PublishedToQuery,
    PublishStatusQuery,
    SearchQueryFilter,
    TagSlugQuery,
)


def provide_public_article_filters(  # noqa: PLR0913
    page: PageQuery,
    page_size: PageSizeQuery,
    language: LanguageQuery,
    tag_slug: TagSlugQuery = None,
    published_from: PublishedFromQuery = None,
    published_to: PublishedToQuery = None,
    search_query: SearchQueryFilter = None,
) -> ArticleFilters:
    normalized_search_query = (
        search_query.strip() if search_query is not None and search_query.strip() else None
    )
    return ArticleFilters(
        page=page,
        page_size=page_size,
        language=language,
        only_published=True,
        tag_slug=tag_slug,
        published_from=published_from,
        published_to=published_to,
        search_query=normalized_search_query,
        include_tags=True,
    )


def provide_article_filters(  # noqa: PLR0913
    page: PageQuery,
    page_size: PageSizeQuery,
    language: LanguageQuery,
    publish_status: PublishStatusQuery = None,
    tag_slug: TagSlugQuery = None,
    published_from: PublishedFromQuery = None,
    published_to: PublishedToQuery = None,
    search_query: SearchQueryFilter = None,
) -> ArticleFilters:
    normalized_search_query = (
        search_query.strip() if search_query is not None and search_query.strip() else None
    )
    return ArticleFilters(
        page=page,
        page_size=page_size,
        language=language,
        only_published=False,
        publish_status=publish_status,
        tag_slug=tag_slug,
        published_from=published_from,
        published_to=published_to,
        search_query=normalized_search_query,
        include_tags=True,
    )
