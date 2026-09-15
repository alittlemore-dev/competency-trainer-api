from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, cast
from unittest.mock import Mock, patch

import click
import pytest
from litestar.exceptions import ImproperlyConfiguredException
from litestar.stores.base import Store

from core.cache_tools.enums import CacheDomainEnum
from entrypoints.litestar import response_cache as response_cache_module
from entrypoints.litestar.api.articles.endpoints import (
    AdminArticlesApiController,
    PublicArticlesApiController,
)
from entrypoints.litestar.api.competency_matrix.endpoints import (
    AdminCompetencyMatrixApiController,
    PublicCompetencyMatrixApiController,
)
from entrypoints.litestar.api.healthcheck.endpoints import HealthcheckController
from entrypoints.litestar.api.i18n.endpoints import I18nApiController
from entrypoints.litestar.cli.commands.cache import invalidate_cache_command
from entrypoints.litestar.cli.plugins import CLIPlugin
from entrypoints.litestar.initializers import main as litestar_initializers
from entrypoints.litestar.response_cache import (
    ResponseCacheDomain,
    ResponseCacheDomainStore,
    invalidate_response_cache_domain_for_mutation,
)
from infra.config.constants import constants
from infra.config.settings import settings
from infra.post_commit_actions import PostCommitActions


@dataclass
class FakeStore:
    values: dict[str, bytes] = field(default_factory=dict)
    set_calls: list[tuple[str, str | bytes, int | timedelta | None]] = field(default_factory=list)
    delete_calls: list[str] = field(default_factory=list)
    delete_all_count: int = 0

    async def set(
        self,
        key: str,
        value: str | bytes,
        expires_in: int | timedelta | None = None,
    ) -> None:
        self.set_calls.append((key, value, expires_in))
        self.values[key] = value if isinstance(value, bytes) else value.encode()

    async def get(self, key: str, renew_for: int | timedelta | None = None) -> bytes | None:
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        self.delete_calls.append(key)
        self.values.pop(key, None)

    async def delete_all(self) -> None:
        self.delete_all_count += 1
        self.values.clear()

    async def exists(self, key: str) -> bool:
        return key in self.values

    async def expires_in(self, key: str) -> int | None:
        return 60 if key in self.values else None


class FakeQueryParams:
    def __init__(self, values: dict[str, Any]) -> None:
        self._values = values

    def dict(self) -> dict[str, Any]:
        return self._values


class FakeUrl:
    path = "/api/articles"


class FakeRequest:
    method = "GET"
    url = FakeUrl()
    query_params = FakeQueryParams({"language": "ru", "page": "1"})


class FakeStores:
    def __init__(self, store: Store) -> None:
        self.store = store
        self.requested_names: list[str] = []

    def get(self, name: str) -> Store:
        self.requested_names.append(name)
        return self.store


class FakeApp:
    def __init__(self, store: Store) -> None:
        self.stores = FakeStores(store=store)


class TestResponseCacheDomainStore:
    async def test_routes_values_to_domain_store(self) -> None:
        articles_store = FakeStore()
        matrix_store = FakeStore()
        store = ResponseCacheDomainStore(
            stores={
                ResponseCacheDomain.ARTICLES: cast("Store", articles_store),
                ResponseCacheDomain.COMPETENCY_MATRIX: cast("Store", matrix_store),
            },
        )

        await store.set("articles:GET/api/articleslanguage=rupage=1", b"articles")
        await store.set("competency_matrix:GET/api/competency-matrix/sheetslanguage=ru", b"matrix")

        assert await articles_store.get("GET/api/articleslanguage=rupage=1") == b"articles"
        assert await matrix_store.get("GET/api/competency-matrix/sheetslanguage=ru") == b"matrix"
        assert await store.get("articles:GET/api/articleslanguage=rupage=1") == b"articles"

    async def test_deletes_only_requested_domain(self) -> None:
        articles_store = FakeStore(values={"GET/api/articles": b"articles"})
        matrix_store = FakeStore(values={"GET/api/competency-matrix/sheets": b"matrix"})
        store = ResponseCacheDomainStore(
            stores={
                ResponseCacheDomain.ARTICLES: cast("Store", articles_store),
                ResponseCacheDomain.COMPETENCY_MATRIX: cast("Store", matrix_store),
            },
        )

        await store.delete_domain(ResponseCacheDomain.ARTICLES)

        assert articles_store.delete_all_count == 1
        assert articles_store.values == {}
        assert matrix_store.delete_all_count == 0
        assert matrix_store.values == {"GET/api/competency-matrix/sheets": b"matrix"}

    async def test_clear_domains_delegates_to_existing_domain_stores(self) -> None:
        i18n_store = FakeStore(values={"GET/api/i18n/languages": b"i18n"})
        articles_store = FakeStore(values={"GET/api/articles": b"articles"})
        store = ResponseCacheDomainStore(
            stores={
                ResponseCacheDomain.I18N: cast("Store", i18n_store),
                ResponseCacheDomain.ARTICLES: cast("Store", articles_store),
            },
        )

        await store.clear_domains(
            domains=(CacheDomainEnum.I18N, CacheDomainEnum.ARTICLES),
        )

        assert i18n_store.values == {}
        assert articles_store.values == {}


class TestInvalidateAllResponseCacheDomains:
    async def test_deletes_all_domain_stores_when_cache_is_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        articles_store = FakeStore(values={"GET/api/articles": b"articles"})
        matrix_store = FakeStore(values={"GET/api/competency-matrix/sheets": b"matrix"})
        domain_store = ResponseCacheDomainStore(
            stores={
                ResponseCacheDomain.ARTICLES: cast("Store", articles_store),
                ResponseCacheDomain.COMPETENCY_MATRIX: cast("Store", matrix_store),
            },
        )
        app = FakeApp(store=cast("Store", domain_store))
        monkeypatch.setattr(settings.app, "use_cache", True)

        await invalidate_cache_command(app=cast("Any", app))

        assert app.stores.requested_names == [constants.response_cache.store_name]
        assert articles_store.delete_all_count == 1
        assert matrix_store.delete_all_count == 1
        assert articles_store.values == {}
        assert matrix_store.values == {}

    async def test_noops_when_cache_is_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        store = FakeStore(values={"GET/api/articles": b"articles"})
        app = FakeApp(store=cast("Store", store))
        monkeypatch.setattr(settings.app, "use_cache", False)

        await invalidate_cache_command(app=cast("Any", app))

        assert app.stores.requested_names == []
        assert store.delete_all_count == 0
        assert store.values == {"GET/api/articles": b"articles"}

    async def test_rejects_non_domain_routed_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        app = FakeApp(store=cast("Store", FakeStore()))
        monkeypatch.setattr(settings.app, "use_cache", True)

        with pytest.raises(ImproperlyConfiguredException):
            await invalidate_cache_command(app=cast("Any", app))


class TestResponseCacheModuleBoundaries:
    def test_initializer_and_cli_helpers_live_outside_response_cache_module(self) -> None:
        assert not hasattr(response_cache_module, "create_response_cache_domain_store")
        assert not hasattr(response_cache_module, "invalidate_cache_command")
        assert callable(litestar_initializers.create_response_cache_domain_store)
        assert callable(invalidate_cache_command)


class TestInvalidateResponseCacheDomainForMutation:
    async def test_invalidates_and_enqueues_warm_only_after_commit_action_runs(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events: list[str] = []
        cached_values = {"detail": b"old article"}
        monkeypatch.setattr(settings.app, "use_cache", True)

        async def fake_invalidate_response_cache_domain(
            *,
            request: object,
            domain: ResponseCacheDomain,
        ) -> None:
            _ = request
            events.append(f"invalidate:{domain.value}")
            cached_values.clear()

        async def fake_cache_warm_domain_kiq(domain_value: str) -> None:
            events.append(f"enqueue:{domain_value}")

        monkeypatch.setattr(
            "entrypoints.litestar.response_cache.invalidate_response_cache_domain",
            fake_invalidate_response_cache_domain,
        )
        monkeypatch.setattr(
            "entrypoints.taskiq.cache_warm.tasks.cache_warm_domain.kiq",
            fake_cache_warm_domain_kiq,
            raising=False,
        )
        post_commit_actions = PostCommitActions(actions=[])

        await invalidate_response_cache_domain_for_mutation(
            request=cast("Any", object()),
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )

        assert events == []
        assert cached_values == {"detail": b"old article"}

        await post_commit_actions.run()

        assert events == ["invalidate:articles", "enqueue:articles"]
        assert cached_values == {}

    async def test_does_not_schedule_post_commit_action_when_cache_is_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(settings.app, "use_cache", False)
        post_commit_actions = PostCommitActions(actions=[])

        await invalidate_response_cache_domain_for_mutation(
            request=cast("Any", object()),
            domain=ResponseCacheDomain.HEALTHCHECK,
            post_commit_actions=post_commit_actions,
        )

        assert post_commit_actions.actions == []

    async def test_post_commit_action_does_not_enqueue_when_invalidation_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        events: list[str] = []
        monkeypatch.setattr(settings.app, "use_cache", True)

        async def fake_invalidate_response_cache_domain(
            *,
            request: object,
            domain: ResponseCacheDomain,
        ) -> None:
            _ = request, domain
            events.append("invalidate")
            msg = "broken cache"
            raise ImproperlyConfiguredException(msg)

        monkeypatch.setattr(
            "entrypoints.litestar.response_cache.invalidate_response_cache_domain",
            fake_invalidate_response_cache_domain,
        )

        async def fake_cache_warm_domain_kiq(domain_value: str) -> None:
            events.append(f"enqueue:{domain_value}")

        monkeypatch.setattr(
            "entrypoints.taskiq.cache_warm.tasks.cache_warm_domain.kiq",
            fake_cache_warm_domain_kiq,
            raising=False,
        )
        post_commit_actions = PostCommitActions(actions=[])

        await invalidate_response_cache_domain_for_mutation(
            request=cast("Any", object()),
            domain=ResponseCacheDomain.ARTICLES,
            post_commit_actions=post_commit_actions,
        )

        assert events == []

        with pytest.raises(ImproperlyConfiguredException):
            await post_commit_actions.run()

        assert events == ["invalidate"]


class TestResponseCacheDomainKeyBuilder:
    def test_builds_domain_prefixed_sorted_litestar_key(self) -> None:
        cache_key_builder = ResponseCacheDomain.ARTICLES.cache_key_builder

        cache_key = cache_key_builder(cast("Any", FakeRequest()))

        assert cache_key == "articles:GET/api/articleslanguage=ru&page=1"

    def test_uses_configured_domain_separator(self) -> None:
        cache_key = ResponseCacheDomain.ARTICLES.cache_key_builder(cast("Any", FakeRequest()))

        assert constants.response_cache.domain_key_separator in cache_key


class TestResponseCacheRouteConfiguration:
    def test_safe_articles_get_handlers_use_articles_cache(self) -> None:
        for handler_name in ("list_articles", "list_articles_tree", "get_article", "list_tags"):
            handler = getattr(PublicArticlesApiController, handler_name)

            assert handler.cache == settings.app.get_cache_duration(
                constants.response_cache.default_ttl_seconds,
            )
            assert handler.cache_key_builder is not None
            assert handler.cache_key_builder(cast("Any", FakeRequest())).startswith("articles:")

    def test_dynamic_articles_get_handlers_are_not_cached(self) -> None:
        for handler_name in ("get_public_stats",):
            assert getattr(PublicArticlesApiController, handler_name).cache is False

    def test_admin_articles_get_handlers_are_not_cached(self) -> None:
        for handler_name in (
            "list_articles",
            "list_articles_tree",
            "get_article",
            "get_stats",
            "list_tags",
            "search_tags",
        ):
            assert getattr(AdminArticlesApiController, handler_name).cache is False

    def test_competency_matrix_get_handlers_use_matrix_cache(self) -> None:
        for handler_name in (
            "list_competency_matrix_sheet",
            "list_competency_matrix_items",
            "get_public_competency_matrix_item",
        ):
            handler = getattr(PublicCompetencyMatrixApiController, handler_name)

            assert handler.cache == settings.app.get_cache_duration(
                constants.response_cache.default_ttl_seconds,
            )
            assert handler.cache_key_builder is not None
            assert handler.cache_key_builder(cast("Any", FakeRequest())).startswith(
                "competency_matrix:",
            )

    def test_admin_competency_matrix_get_handlers_are_not_cached(self) -> None:
        for handler_name in (
            "list_competency_matrix_sheet",
            "search_competency_matrix_resources",
            "list_queued_competency_matrix_questions",
            "list_competency_matrix_items",
            "get_competency_matrix_item",
        ):
            assert getattr(AdminCompetencyMatrixApiController, handler_name).cache is False

    def test_i18n_get_handlers_use_i18n_cache(self) -> None:
        for handler_name in ("list_languages", "get_bundle"):
            handler = getattr(I18nApiController, handler_name)

            assert handler.cache == settings.app.get_cache_duration(
                constants.response_cache.default_ttl_seconds,
            )
            assert handler.cache_key_builder is not None
            assert handler.cache_key_builder(cast("Any", FakeRequest())).startswith("i18n:")

    def test_healthcheck_uses_domain_cache_key(self) -> None:
        handler = HealthcheckController.health

        assert handler.cache == settings.app.get_cache_duration(1)
        assert handler.cache_key_builder is not None
        assert handler.cache_key_builder(cast("Any", FakeRequest())).startswith("healthcheck:")


class TestResponseCacheCli:
    def test_registers_invalidate_cache_command(self) -> None:
        cli = click.Group()

        CLIPlugin().on_cli_init(cli)

        assert "invalidatecache" in cli.commands
        assert "createsuperuser" in cli.commands
        assert "initbuckets" in cli.commands

    def test_initbuckets_delegates_to_storage_command(self) -> None:
        cli = click.Group()
        command_coro = object()
        init_buckets_command = Mock(return_value=command_coro)

        with (
            patch(
                "entrypoints.litestar.cli.plugins.init_buckets_command",
                new=init_buckets_command,
                create=True,
            ),
            patch("entrypoints.litestar.cli.plugins.run_sync") as run_sync,
        ):
            CLIPlugin().on_cli_init(cli)
            callback = cli.commands["initbuckets"].callback
            assert callback is not None
            callback(app=object())

        init_buckets_command.assert_called_once_with()
        run_sync.assert_called_once_with(command_coro)
