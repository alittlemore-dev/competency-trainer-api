from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlencode

from core.articles.schemas import Article, ArticleFilters, Articles, ArticleTree, Tags
from core.articles.use_cases import ArticlesUseCase
from core.competency_matrix.schemas import (
    CompetencyMatrixItem,
    CompetencyMatrixItemBySlugGetParams,
    CompetencyMatrixItemFilters,
    CompetencyMatrixItems,
    Sheets,
)
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.articles.schemas import (
    ArticleDetailResponseSchema,
    ArticleListResponseSchema,
    ArticleTreeResponseSchema,
    TagsResponseSchema,
)
from entrypoints.litestar.api.competency_matrix.schemas import (
    CompetencyMatrixItemDetailResponseSchema,
    CompetencyMatrixItemsListResponseSchema,
    CompetencyMatrixSheetsListResponseSchema,
)
from entrypoints.litestar.api.i18n.catalog import get_i18n_messages, get_language_label
from entrypoints.litestar.api.i18n.schemas import (
    I18nBundleResponseSchema,
    LanguageResponseSchema,
    LanguagesResponseSchema,
)
from entrypoints.litestar.api.schemas import CamelCaseSchema
from entrypoints.litestar.response_cache import ResponseCacheDomain
from infra.config.constants import constants
from infra.config.settings import settings


@dataclass(frozen=True, slots=True)
class CacheWarmTarget:
    domain: ResponseCacheDomain
    path: str
    query: tuple[tuple[str, str], ...]
    response: CamelCaseSchema

    def build_cache_key(self) -> str:
        query_string = urlencode(sorted(self.query), doseq=True)
        return (
            f"{self.domain.value}"
            f"{constants.response_cache.domain_key_separator}"
            f"GET{self.path}{query_string}"
        )

    def response_cache_payload(self) -> bytes:
        return self.response.response_cache_payload()


@dataclass(frozen=True, slots=True)
class CacheWarmQueryBuilder:
    def build(self, *values: tuple[str, str]) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(values, key=lambda item: item[0]))


@dataclass(frozen=True, slots=True)
class I18nCacheWarmTargetCollector:
    def collect(self) -> list[CacheWarmTarget]:
        return [
            self._languages_target(),
            *[self._bundle_target(language=language) for language in LanguageEnum],
        ]

    def _languages_target(self) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.I18N,
            path="/api/i18n/languages",
            query=(),
            response=LanguagesResponseSchema(
                default_language=settings.i18n.default_language,
                languages=[
                    LanguageResponseSchema.from_language(
                        language=language,
                        label=get_language_label(language=language),
                    )
                    for language in LanguageEnum
                ],
            ),
        )

    def _bundle_target(self, *, language: LanguageEnum) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.I18N,
            path=f"/api/i18n/bundles/{language.value}",
            query=(),
            response=I18nBundleResponseSchema(
                language=language,
                messages=dict(get_i18n_messages(language=language)),
            ),
        )


@dataclass(frozen=True, slots=True)
class ArticlesCacheWarmTargetCollector:
    articles_use_case: ArticlesUseCase
    query_builder: CacheWarmQueryBuilder

    async def collect(self) -> list[CacheWarmTarget]:
        targets: list[CacheWarmTarget] = []
        for language in LanguageEnum:
            targets.extend(await self._collect_language_targets(language=language))
        return targets

    async def _collect_language_targets(self, *, language: LanguageEnum) -> list[CacheWarmTarget]:
        tags = await self.articles_use_case.list_tags(
            language=language,
            only_with_published_articles=True,
        )
        tree = await self.articles_use_case.list_tree(only_published=True, language=language)
        articles = await self.articles_use_case.list_articles(
            filters=self._build_list_filters(language=language),
        )
        return [
            self._tags_target(tags=tags, language=language),
            self._tree_target(tree=tree, language=language),
            self._list_target(articles=articles, language=language),
            *await self._detail_targets(articles=articles, language=language),
        ]

    def _build_list_filters(self, *, language: LanguageEnum) -> ArticleFilters:
        return ArticleFilters(
            page=1,
            page_size=settings.cache_warm.articles_page_size,
            language=language,
            only_published=True,
            tag_slug=None,
            published_from=None,
            published_to=None,
            search_query=None,
            include_tags=True,
            order_for_seo=False,
        )

    def _tags_target(self, *, tags: Tags, language: LanguageEnum) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.ARTICLES,
            path="/api/articles/tags",
            query=self.query_builder.build(("language", language.value)),
            response=TagsResponseSchema.from_domain_schema(
                schema=tags,
                language=language,
            ),
        )

    def _tree_target(self, *, tree: ArticleTree, language: LanguageEnum) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.ARTICLES,
            path="/api/articles/tree",
            query=self.query_builder.build(("language", language.value)),
            response=ArticleTreeResponseSchema.from_domain_schema(schema=tree),
        )

    def _list_target(self, *, articles: Articles, language: LanguageEnum) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.ARTICLES,
            path="/api/articles",
            query=self.query_builder.build(
                ("language", language.value),
                ("page", "1"),
                ("pageSize", str(settings.cache_warm.articles_page_size)),
            ),
            response=ArticleListResponseSchema.from_domain_schema(
                schema=articles,
                language=language,
            ),
        )

    async def _detail_targets(
        self,
        *,
        articles: Articles,
        language: LanguageEnum,
    ) -> list[CacheWarmTarget]:
        return [
            self._detail_target(
                article=article,
                detail=await self._load_detail(article=article),
                language=language,
            )
            for article in articles.values
        ]

    async def _load_detail(self, *, article: Article) -> Article:
        return await self.articles_use_case.get_article(slug=article.slug, only_published=True)

    def _detail_target(
        self,
        *,
        article: Article,
        detail: Article,
        language: LanguageEnum,
    ) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.ARTICLES,
            path=f"/api/articles/detail/{article.slug}",
            query=self.query_builder.build(("language", language.value)),
            response=ArticleDetailResponseSchema.from_domain_schema(
                schema=detail,
                language=language,
            ),
        )


@dataclass(frozen=True, slots=True)
class CompetencyMatrixCacheWarmTargetCollector:
    matrix_use_case: CompetencyMatrixUseCase
    query_builder: CacheWarmQueryBuilder

    async def collect(self) -> list[CacheWarmTarget]:
        targets: list[CacheWarmTarget] = []
        for language in LanguageEnum:
            targets.extend(await self._collect_language_targets(language=language))
        return targets

    async def _collect_language_targets(self, *, language: LanguageEnum) -> list[CacheWarmTarget]:
        sheets = await self.matrix_use_case.list_sheets()
        return [
            self._sheets_target(sheets=sheets, language=language),
            *await self._sheet_item_targets(sheets=sheets, language=language),
        ]

    def _sheets_target(self, *, sheets: Sheets, language: LanguageEnum) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            path="/api/competency-matrix/sheets",
            query=self.query_builder.build(("language", language.value)),
            response=CompetencyMatrixSheetsListResponseSchema.from_domain_schema(
                schema=sheets,
                language=language,
            ),
        )

    async def _sheet_item_targets(
        self,
        *,
        sheets: Sheets,
        language: LanguageEnum,
    ) -> list[CacheWarmTarget]:
        targets: list[CacheWarmTarget] = []
        for sheet in sheets:
            items = await self.matrix_use_case.list_items(
                filters=CompetencyMatrixItemFilters(
                    sheet_key=sheet.key,
                    only_published=True,
                ),
            )
            targets.append(
                self._items_target(sheet_key=sheet.key, items=items, language=language),
            )
            targets.extend(await self._item_detail_targets(items=items, language=language))
        return targets

    def _items_target(
        self,
        *,
        sheet_key: str,
        items: CompetencyMatrixItems,
        language: LanguageEnum,
    ) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            path="/api/competency-matrix/items",
            query=self.query_builder.build(
                ("language", language.value),
                ("sheetKey", sheet_key),
            ),
            response=CompetencyMatrixItemsListResponseSchema.from_domain_schema(
                sheet_key=sheet_key,
                schema=items,
                language=language,
            ),
        )

    async def _item_detail_targets(
        self,
        *,
        items: CompetencyMatrixItems,
        language: LanguageEnum,
    ) -> list[CacheWarmTarget]:
        targets: list[CacheWarmTarget] = []
        for item in items.values:
            targets.extend(await self._single_item_detail_targets(item=item, language=language))
        return targets

    async def _single_item_detail_targets(
        self,
        *,
        item: CompetencyMatrixItem,
        language: LanguageEnum,
    ) -> list[CacheWarmTarget]:
        public_detail = await self.matrix_use_case.get_item_by_slug(
            params=CompetencyMatrixItemBySlugGetParams(
                slug=item.slug,
                only_published=True,
            ),
        )
        return [
            self._public_detail_target(item=item, detail=public_detail, language=language),
        ]

    def _public_detail_target(
        self,
        *,
        item: CompetencyMatrixItem,
        detail: CompetencyMatrixItem,
        language: LanguageEnum,
    ) -> CacheWarmTarget:
        return CacheWarmTarget(
            domain=ResponseCacheDomain.COMPETENCY_MATRIX,
            path=f"/api/competency-matrix/items/public/{item.slug}",
            query=self.query_builder.build(("language", language.value)),
            response=CompetencyMatrixItemDetailResponseSchema.from_domain_schema(
                schema=detail,
                language=language,
            ),
        )


@dataclass(frozen=True, slots=True)
class ResponseCacheWarmTargetCollector:
    i18n_collector: I18nCacheWarmTargetCollector
    articles_collector: ArticlesCacheWarmTargetCollector
    matrix_collector: CompetencyMatrixCacheWarmTargetCollector

    async def collect(self, *, domains: Iterable[ResponseCacheDomain]) -> list[CacheWarmTarget]:
        requested_domains = tuple(domains)
        targets: list[CacheWarmTarget] = []
        if ResponseCacheDomain.I18N in requested_domains:
            targets.extend(self.i18n_collector.collect())
        if ResponseCacheDomain.ARTICLES in requested_domains:
            targets.extend(await self.articles_collector.collect())
        if ResponseCacheDomain.COMPETENCY_MATRIX in requested_domains:
            targets.extend(await self.matrix_collector.collect())
        return targets
