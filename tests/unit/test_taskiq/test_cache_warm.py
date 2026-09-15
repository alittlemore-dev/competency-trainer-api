from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast

import msgspec
import pytest
from litestar.stores.base import Store

from core.articles.schemas import ArticleFilters, ArticleTree
from core.articles.use_cases import ArticlesUseCase
from core.competency_matrix.schemas import (
    CompetencyMatrixItemBySlugGetParams,
    CompetencyMatrixItemFilters,
)
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.articles.schemas import ArticleDetailResponseSchema
from entrypoints.litestar.response_cache import ResponseCacheDomain, ResponseCacheDomainStore
from entrypoints.taskiq.cache_warm.service import CacheWarmSummary, ResponseCacheWarmService
from entrypoints.taskiq.cache_warm.targets import (
    ArticlesCacheWarmTargetCollector,
    CacheWarmQueryBuilder,
    CacheWarmTarget,
    CompetencyMatrixCacheWarmTargetCollector,
    I18nCacheWarmTargetCollector,
    ResponseCacheWarmTargetCollector,
)
from entrypoints.taskiq.cache_warm.writer import ResponseCacheWarmWriter
from infra.config.constants import constants
from infra.config.settings import settings
from tests.helpers.factory import FactoryHelper
from tests.test_cases import TestCase


@dataclass
class FakeStore:
    values: dict[str, bytes] = field(default_factory=dict)
    set_calls: list[tuple[str, bytes | str, int | timedelta | None]] = field(default_factory=list)

    async def set(
        self,
        key: str,
        value: bytes | str,
        expires_in: int | timedelta | None = None,
    ) -> None:
        self.set_calls.append((key, value, expires_in))
        self.values[key] = value if isinstance(value, bytes) else value.encode()

    async def get(self, key: str, renew_for: int | timedelta | None = None) -> bytes | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.values.pop(key, None)

    async def delete_all(self) -> None:
        self.values.clear()

    async def exists(self, key: str) -> bool:
        return key in self.values

    async def expires_in(self, key: str) -> int | None:
        return 60 if key in self.values else None


class FakeArticlesUseCase:
    def __init__(self, factory: FactoryHelper) -> None:
        self.factory = factory
        self.list_articles_filters: list[ArticleFilters] = []
        self.list_tree_languages: list[LanguageEnum] = []
        self.list_tags_calls: list[tuple[LanguageEnum, bool]] = []
        self.detail_slugs: list[str] = []
        self.articles = [
            factory.core.article(slug="first-article"),
            factory.core.article(slug="second-article"),
        ]

    async def list_articles(self, *, filters: ArticleFilters):
        self.list_articles_filters.append(filters)
        return self.factory.core.article_list(articles=self.articles, total_count=2, total_pages=1)

    async def list_tree(self, *, only_published: bool, language: LanguageEnum):
        assert only_published is True
        self.list_tree_languages.append(language)
        return ArticleTree(folders=[])

    async def list_tags(
        self,
        *,
        language: LanguageEnum,
        only_with_published_articles: bool,
    ):
        self.list_tags_calls.append((language, only_with_published_articles))
        return self.factory.core.tags(values=[self.factory.core.tag(tag_id=1)])

    async def get_article(self, *, slug: str, only_published: bool):
        assert only_published is True
        self.detail_slugs.append(slug)
        return self.factory.core.article(slug=slug)


class FakeCompetencyMatrixUseCase:
    def __init__(self, factory: FactoryHelper) -> None:
        self.factory = factory
        self.list_items_filters: list[CompetencyMatrixItemFilters] = []
        self.public_detail_slugs: list[str] = []
        self.items = [
            factory.core.competency_matrix_item(
                item_id=1,
                slug="first-question",
                sheet_key="python",
                sheet="Python",
            ),
            factory.core.competency_matrix_item(
                item_id=2,
                slug="second-question",
                sheet_key="python",
                sheet="Python",
            ),
        ]

    async def list_sheets(self):
        return self.factory.core.sheets(values=["Python"])

    async def list_items(self, *, filters: CompetencyMatrixItemFilters):
        self.list_items_filters.append(filters)
        return self.factory.core.competency_matrix_items(values=self.items)

    async def get_item_by_slug(self, *, params: CompetencyMatrixItemBySlugGetParams):
        assert params.only_published is True
        self.public_detail_slugs.append(params.slug)
        return next(item for item in self.items if item.slug == params.slug)


class TestCacheWarmTargetGeneration(TestCase):
    async def test_collects_canonical_targets_for_both_languages(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.cache_warm, "articles_page_size", 10)
        articles_use_case = FakeArticlesUseCase(factory=self.factory)
        matrix_use_case = FakeCompetencyMatrixUseCase(factory=self.factory)
        query_builder = CacheWarmQueryBuilder()
        collector = ResponseCacheWarmTargetCollector(
            i18n_collector=I18nCacheWarmTargetCollector(),
            articles_collector=ArticlesCacheWarmTargetCollector(
                articles_use_case=cast("ArticlesUseCase", articles_use_case),
                query_builder=query_builder,
            ),
            matrix_collector=CompetencyMatrixCacheWarmTargetCollector(
                matrix_use_case=cast("CompetencyMatrixUseCase", matrix_use_case),
                query_builder=query_builder,
            ),
        )

        targets = await collector.collect(
            domains=(
                ResponseCacheDomain.I18N,
                ResponseCacheDomain.ARTICLES,
                ResponseCacheDomain.COMPETENCY_MATRIX,
            ),
        )
        target_paths = {(target.domain, target.path, target.query) for target in targets}

        for language in LanguageEnum:
            assert (
                ResponseCacheDomain.I18N,
                f"/api/i18n/bundles/{language.value}",
                (),
            ) in target_paths
            assert (
                ResponseCacheDomain.ARTICLES,
                "/api/articles",
                (
                    ("language", language.value),
                    ("page", "1"),
                    ("pageSize", "10"),
                ),
            ) in target_paths
            assert (
                ResponseCacheDomain.ARTICLES,
                "/api/articles/tags",
                (("language", language.value),),
            ) in target_paths
            assert (
                ResponseCacheDomain.ARTICLES,
                "/api/articles/tree",
                (("language", language.value),),
            ) in target_paths
            assert (
                ResponseCacheDomain.COMPETENCY_MATRIX,
                "/api/competency-matrix/sheets",
                (("language", language.value),),
            ) in target_paths
            assert (
                ResponseCacheDomain.COMPETENCY_MATRIX,
                "/api/competency-matrix/items",
                (
                    ("language", language.value),
                    ("sheetKey", "python"),
                ),
            ) in target_paths
            for slug in ("first-question", "second-question"):
                assert (
                    ResponseCacheDomain.COMPETENCY_MATRIX,
                    f"/api/competency-matrix/items/public/{slug}",
                    (("language", language.value),),
                ) in target_paths

        assert (
            ResponseCacheDomain.I18N,
            "/api/i18n/languages",
            (),
        ) in target_paths
        assert articles_use_case.list_articles_filters == [
            ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                include_tags=True,
            ),
            ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.EN,
                only_published=True,
                include_tags=True,
            ),
        ]
        assert articles_use_case.list_tags_calls == [
            (LanguageEnum.RU, True),
            (LanguageEnum.EN, True),
        ]
        assert matrix_use_case.public_detail_slugs == [
            "first-question",
            "second-question",
            "first-question",
            "second-question",
        ]

    async def test_domain_specific_collection_limits_use_case_work(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.cache_warm, "articles_page_size", 10)
        articles_use_case = FakeArticlesUseCase(factory=self.factory)
        matrix_use_case = FakeCompetencyMatrixUseCase(factory=self.factory)
        query_builder = CacheWarmQueryBuilder()
        collector = ResponseCacheWarmTargetCollector(
            i18n_collector=I18nCacheWarmTargetCollector(),
            articles_collector=ArticlesCacheWarmTargetCollector(
                articles_use_case=cast("ArticlesUseCase", articles_use_case),
                query_builder=query_builder,
            ),
            matrix_collector=CompetencyMatrixCacheWarmTargetCollector(
                matrix_use_case=cast("CompetencyMatrixUseCase", matrix_use_case),
                query_builder=query_builder,
            ),
        )

        targets = await collector.collect(
            domains=(ResponseCacheDomain.ARTICLES,),
        )

        assert {target.domain for target in targets} == {ResponseCacheDomain.ARTICLES}
        assert articles_use_case.list_articles_filters
        assert matrix_use_case.list_items_filters == []


class TestCacheWarmWriter(TestCase):
    async def test_writes_litestar_compatible_payload_to_domain_store(self) -> None:
        articles_store = FakeStore()
        store = ResponseCacheDomainStore(
            stores={ResponseCacheDomain.ARTICLES: cast("Store", articles_store)},
        )
        response = ArticleDetailResponseSchema.from_domain_schema(
            schema=self.factory.core.article(slug="first-article"),
            language=LanguageEnum.EN,
        )
        target = CacheWarmTarget(
            domain=ResponseCacheDomain.ARTICLES,
            path="/api/articles/detail/first-article",
            query=(("language", "en"),),
            response=response,
        )

        await ResponseCacheWarmWriter(
            store=store,
        ).write_target(target)

        assert target.build_cache_key() == (
            "articles:GET/api/articles/detail/first-articlelanguage=en"
        )
        assert articles_store.set_calls[0][0] == "GET/api/articles/detail/first-articlelanguage=en"
        assert articles_store.set_calls[0][2] == constants.response_cache.default_ttl_seconds
        payload = articles_store.set_calls[0][1]
        assert isinstance(payload, bytes)
        messages = msgspec.msgpack.decode(payload)
        assert messages == [
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [[b"content-type", b"application/json"]],
            },
            {
                "type": "http.response.body",
                "body": response.model_dump_json(by_alias=True).encode(),
            },
        ]

    def test_cache_warm_target_uses_schema_owned_payload_encoding(self) -> None:
        response = ArticleDetailResponseSchema.from_domain_schema(
            schema=self.factory.core.article(slug="first-article"),
            language=LanguageEnum.EN,
        )
        target = CacheWarmTarget(
            domain=ResponseCacheDomain.ARTICLES,
            path="/api/articles/detail/first-article",
            query=(("language", "en"),),
            response=response,
        )

        assert target.response_cache_payload() == response.response_cache_payload()

    async def test_cache_disabled_summary_skips_without_use_case_work(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.app, "use_cache", False)
        articles_use_case = FakeArticlesUseCase(factory=self.factory)
        matrix_use_case = FakeCompetencyMatrixUseCase(factory=self.factory)
        store = ResponseCacheDomainStore(stores={})
        query_builder = CacheWarmQueryBuilder()
        target_collector = ResponseCacheWarmTargetCollector(
            i18n_collector=I18nCacheWarmTargetCollector(),
            articles_collector=ArticlesCacheWarmTargetCollector(
                articles_use_case=cast("ArticlesUseCase", articles_use_case),
                query_builder=query_builder,
            ),
            matrix_collector=CompetencyMatrixCacheWarmTargetCollector(
                matrix_use_case=cast("CompetencyMatrixUseCase", matrix_use_case),
                query_builder=query_builder,
            ),
        )
        writer = ResponseCacheWarmWriter(
            store=store,
        )
        service = ResponseCacheWarmService(
            target_collector=target_collector,
            writer=writer,
            use_cache=False,
            supported_domains=(
                ResponseCacheDomain.I18N,
                ResponseCacheDomain.ARTICLES,
                ResponseCacheDomain.COMPETENCY_MATRIX,
            ),
        )

        summary = await service.warm_domains(
            domains=(ResponseCacheDomain.ARTICLES,),
        )

        assert summary == CacheWarmSummary(attempted=0, written=0, skipped=1)
        assert summary.as_dict() == {"attempted": 0, "written": 0, "skipped": 1}
        assert articles_use_case.list_articles_filters == []
        assert matrix_use_case.list_items_filters == []
