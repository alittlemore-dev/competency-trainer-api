from collections.abc import AsyncIterable
from contextlib import AsyncExitStack

from dishka import Provider, Scope, provide
from litestar.stores.valkey import ValkeyStore
from valkey.asyncio import Valkey

from core.articles.storages import ArticlesStorage
from core.articles.use_cases import ArticlesUseCase
from core.cache_tools.enums import CacheDomainEnum
from core.cache_tools.schemas import CacheToolsPolicy
from core.cache_tools.storages import CacheWarmOperationStorage, ResponseCacheStatusStorage
from core.cache_tools.use_cases import CacheToolsUseCase, ManualCacheWarmUseCase
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.files.clients import FileClient
from core.files.services import FileService
from core.generators import HexUuidIdGenerator
from core.identity import PublicationAccess
from entrypoints.litestar.response_cache import (
    ResponseCacheDomain,
    ResponseCacheDomainStore,
)
from entrypoints.taskiq.cache_warm.dispatcher import TaskiqCacheWarmDispatcher
from entrypoints.taskiq.cache_warm.service import ResponseCacheWarmService
from entrypoints.taskiq.cache_warm.targets import (
    ArticlesCacheWarmTargetCollector,
    CacheWarmQueryBuilder,
    CompetencyMatrixCacheWarmTargetCollector,
    ResponseCacheWarmTargetCollector,
)
from entrypoints.taskiq.cache_warm.writer import ResponseCacheWarmWriter
from infra.config.constants import constants
from infra.config.settings import settings
from infra.valkey.storages import (
    ValkeyCacheWarmOperationStorage,
    ValkeyResponseCacheStatusStorage,
)


class ResponseCacheWarmProvider(Provider):
    scope = Scope.REQUEST

    cache_warm_query_builder = provide(CacheWarmQueryBuilder)

    @provide
    async def provide_articles_collector(
        self,
        storage: ArticlesStorage,
        file_service: FileService,
        file_client: FileClient,
        query_builder: CacheWarmQueryBuilder,
    ) -> ArticlesCacheWarmTargetCollector:
        return ArticlesCacheWarmTargetCollector(
            articles_use_case=ArticlesUseCase(
                storage=storage,
                file_service=file_service,
                file_client=file_client,
                publication=PublicationAccess(allowed=False),
            ),
            query_builder=query_builder,
        )

    @provide
    async def provide_matrix_collector(
        self,
        storage: CompetencyMatrixStorage,
        question_suggestion_limiter: QuestionSuggestionLimiter,
        query_builder: CacheWarmQueryBuilder,
    ) -> CompetencyMatrixCacheWarmTargetCollector:
        return CompetencyMatrixCacheWarmTargetCollector(
            matrix_use_case=CompetencyMatrixUseCase(
                storage=storage,
                question_suggestion_limiter=question_suggestion_limiter,
                publication=PublicationAccess(allowed=False),
            ),
            query_builder=query_builder,
        )

    response_cache_warm_target_collector = provide(ResponseCacheWarmTargetCollector)
    response_cache_warm_writer = provide(ResponseCacheWarmWriter)

    @provide(scope=Scope.APP)
    async def provide_cache_tools_policy(self) -> CacheToolsPolicy:
        return CacheToolsPolicy(
            enabled=settings.app.use_cache,
            configured_ttl_seconds=constants.response_cache.default_ttl_seconds,
            scheduled_warm_interval_seconds=settings.taskiq.cache_warm_interval_seconds,
            domains=tuple(CacheDomainEnum),
        )

    @provide
    async def provide_response_cache_domain_store(
        self,
    ) -> AsyncIterable[ResponseCacheDomainStore]:
        from entrypoints.litestar.initializers.main import (  # noqa: PLC0415
            create_response_cache_domain_store,
        )

        response_cache_domain_store = create_response_cache_domain_store()
        async with AsyncExitStack() as exit_stack:
            for store in response_cache_domain_store.stores.values():
                await exit_stack.enter_async_context(store)
            yield response_cache_domain_store

    @provide
    async def provide_response_cache_warm_service(
        self,
        target_collector: ResponseCacheWarmTargetCollector,
        writer: ResponseCacheWarmWriter,
    ) -> ResponseCacheWarmService:
        return ResponseCacheWarmService(
            target_collector=target_collector,
            writer=writer,
            use_cache=settings.app.use_cache,
            supported_domains=(
                ResponseCacheDomain.ARTICLES,
                ResponseCacheDomain.COMPETENCY_MATRIX,
            ),
        )

    @provide
    async def provide_response_cache_status_storage(
        self,
    ) -> AsyncIterable[ResponseCacheStatusStorage]:
        valkey = Valkey.from_url(
            settings.valkey.get_url(
                db=constants.valkey.databases.response_cache
            ).get_secret_value(),
            decode_responses=False,
        )
        try:
            yield ValkeyResponseCacheStatusStorage(
                valkey=valkey,
                namespaces={
                    domain: f"{constants.valkey.namespaces.framework}_{domain.value}"
                    for domain in CacheDomainEnum
                },
                scan_batch_size=constants.response_cache.status_scan_batch_size,
            )
        finally:
            await valkey.aclose(close_connection_pool=True)

    @provide
    async def provide_cache_warm_operation_storage(
        self,
    ) -> AsyncIterable[CacheWarmOperationStorage]:
        store = ValkeyStore.with_client(
            url=settings.valkey.get_url(
                db=constants.valkey.databases.taskiq_results,
            ).get_secret_value(),
            db=constants.valkey.databases.taskiq_results,
            port=settings.valkey.port,
            namespace=constants.valkey.namespaces.admin_cache_warm_operations,
        )
        async with store:
            yield ValkeyCacheWarmOperationStorage(
                store=store,
                expires_in_seconds=settings.taskiq.result_expire_seconds,
            )

    @provide
    async def provide_cache_tools_use_case(
        self,
        response_cache_status_storage: ResponseCacheStatusStorage,
        response_cache_domain_store: ResponseCacheDomainStore,
        operation_storage: CacheWarmOperationStorage,
        id_generator: HexUuidIdGenerator,
    ) -> CacheToolsUseCase:
        return CacheToolsUseCase(
            response_cache_status_storage=response_cache_status_storage,
            response_cache_invalidation_storage=response_cache_domain_store,
            operation_storage=operation_storage,
            task_dispatcher=TaskiqCacheWarmDispatcher(),
            id_generator=id_generator,
        )

    @provide
    async def provide_manual_cache_warm_use_case(
        self,
        operation_storage: CacheWarmOperationStorage,
        response_cache_warm_service: ResponseCacheWarmService,
    ) -> ManualCacheWarmUseCase:
        return ManualCacheWarmUseCase(
            operation_storage=operation_storage,
            executor=response_cache_warm_service,
        )
