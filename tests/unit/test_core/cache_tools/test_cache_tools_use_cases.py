from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest

from core.cache_tools.clients import CacheWarmExecutor
from core.cache_tools.enums import CacheDomainEnum, CacheWarmOperationStatusEnum
from core.cache_tools.event_dispatchers import CacheWarmTaskDispatcher
from core.cache_tools.exceptions import CacheWarmOperationNotFoundError
from core.cache_tools.schemas import (
    CacheDomainStatus,
    CacheToolsPolicy,
    CacheWarmOperation,
    CacheWarmSummary,
)
from core.cache_tools.storages import (
    CacheWarmOperationStorage,
    ResponseCacheInvalidationStorage,
    ResponseCacheStatusStorage,
)
from core.cache_tools.use_cases import CacheToolsUseCase, ManualCacheWarmUseCase
from core.generators import HexUuidIdGenerator

CURRENT_DATETIME = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)
DOMAINS = (
    CacheDomainEnum.I18N,
    CacheDomainEnum.ARTICLES,
    CacheDomainEnum.COMPETENCY_MATRIX,
)


class TestCacheToolsUseCase:
    def setup_method(self) -> None:
        self.status_storage = Mock(spec=ResponseCacheStatusStorage)
        self.invalidation_storage = Mock(spec=ResponseCacheInvalidationStorage)
        self.operation_storage = Mock(spec=CacheWarmOperationStorage)
        self.dispatcher = Mock(spec=CacheWarmTaskDispatcher)
        self.id_generator = Mock(spec=HexUuidIdGenerator)
        self.id_generator.get_next.return_value = "operation-id"
        self.policy = CacheToolsPolicy(
            enabled=True,
            configured_ttl_seconds=86_400,
            scheduled_warm_interval_seconds=3_600,
            domains=DOMAINS,
        )
        self.use_case = CacheToolsUseCase(
            response_cache_status_storage=self.status_storage,
            response_cache_invalidation_storage=self.invalidation_storage,
            operation_storage=self.operation_storage,
            task_dispatcher=self.dispatcher,
            id_generator=self.id_generator,
        )

    async def test_get_status_reports_metrics_and_latest_manual_operation(self) -> None:
        domain_statuses = (
            CacheDomainStatus(
                domain=CacheDomainEnum.I18N,
                key_count=3,
                minimum_remaining_ttl_seconds=120,
                non_expiring_key_count=1,
            ),
            CacheDomainStatus(
                domain=CacheDomainEnum.ARTICLES,
                key_count=4,
                minimum_remaining_ttl_seconds=60,
                non_expiring_key_count=0,
            ),
            CacheDomainStatus(
                domain=CacheDomainEnum.COMPETENCY_MATRIX,
                key_count=0,
                minimum_remaining_ttl_seconds=None,
                non_expiring_key_count=0,
            ),
        )
        latest_operation = CacheWarmOperation(
            operation_id="previous-operation",
            status=CacheWarmOperationStatusEnum.SUCCEEDED,
            queued_at=CURRENT_DATETIME,
            summary=CacheWarmSummary(attempted=10, written=10, skipped=0),
        )
        self.status_storage.get_domain_status.side_effect = domain_statuses
        self.operation_storage.get_latest.return_value = latest_operation

        result = await self.use_case.get_status(policy=self.policy)

        assert result.enabled is True
        assert result.configured_ttl_seconds == 86_400
        assert result.scheduled_warm_interval_seconds == 3_600
        assert result.domains == domain_statuses
        assert result.last_manual_warm_operation == latest_operation
        assert self.status_storage.get_domain_status.await_args_list == [
            call(domain=domain) for domain in DOMAINS
        ]

    async def test_disabled_cache_status_does_not_read_response_cache(self) -> None:
        use_case = CacheToolsUseCase(
            response_cache_status_storage=self.status_storage,
            response_cache_invalidation_storage=self.invalidation_storage,
            operation_storage=self.operation_storage,
            task_dispatcher=self.dispatcher,
            id_generator=self.id_generator,
        )
        self.operation_storage.get_latest.return_value = None

        result = await use_case.get_status(
            policy=CacheToolsPolicy(
                enabled=False,
                configured_ttl_seconds=86_400,
                scheduled_warm_interval_seconds=3_600,
                domains=DOMAINS,
            ),
        )

        assert result.domains == tuple(
            CacheDomainStatus(
                domain=domain,
                key_count=0,
                minimum_remaining_ttl_seconds=None,
                non_expiring_key_count=0,
            )
            for domain in DOMAINS
        )
        self.status_storage.get_domain_status.assert_not_awaited()

    async def test_clear_uses_existing_domain_invalidation_and_returns_empty_metrics(self) -> None:
        self.operation_storage.get_latest.return_value = None
        self.status_storage.get_domain_status.side_effect = tuple(
            CacheDomainStatus(
                domain=domain,
                key_count=0,
                minimum_remaining_ttl_seconds=None,
                non_expiring_key_count=0,
            )
            for domain in DOMAINS
        )

        result = await self.use_case.clear(policy=self.policy)

        self.invalidation_storage.clear_domains.assert_awaited_once_with(domains=DOMAINS)
        assert all(domain_status.key_count == 0 for domain_status in result.domains)
        self.dispatcher.enqueue.assert_not_awaited()

    async def test_disabled_cache_clear_does_not_touch_response_cache(self) -> None:
        use_case = CacheToolsUseCase(
            response_cache_status_storage=self.status_storage,
            response_cache_invalidation_storage=self.invalidation_storage,
            operation_storage=self.operation_storage,
            task_dispatcher=self.dispatcher,
            id_generator=self.id_generator,
        )
        self.operation_storage.get_latest.return_value = None

        result = await use_case.clear(
            policy=CacheToolsPolicy(
                enabled=False,
                configured_ttl_seconds=86_400,
                scheduled_warm_interval_seconds=3_600,
                domains=DOMAINS,
            ),
        )

        assert result.enabled is False
        self.invalidation_storage.clear_domains.assert_not_awaited()

    async def test_enqueue_manual_warm_persists_queued_operation_before_dispatch(self) -> None:
        calls: list[str] = []

        async def create_operation(operation: CacheWarmOperation) -> None:
            assert operation.status is CacheWarmOperationStatusEnum.QUEUED
            calls.append("create")

        async def enqueue(operation_id: str) -> None:
            assert operation_id == "operation-id"
            calls.append("enqueue")

        self.operation_storage.create.side_effect = create_operation
        self.dispatcher.enqueue.side_effect = enqueue

        result = await self.use_case.enqueue_manual_warm(current_datetime=CURRENT_DATETIME)

        assert result == CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.QUEUED,
            queued_at=CURRENT_DATETIME,
            summary=None,
        )
        assert calls == ["create", "enqueue"]

    async def test_enqueue_failure_marks_operation_failed_and_reraises(self) -> None:
        self.dispatcher.enqueue.side_effect = RuntimeError("broker unavailable")

        with pytest.raises(RuntimeError, match="broker unavailable"):
            await self.use_case.enqueue_manual_warm(current_datetime=CURRENT_DATETIME)

        failed_operation = self.operation_storage.update.await_args.kwargs["operation"]
        assert failed_operation.status is CacheWarmOperationStatusEnum.FAILED
        assert failed_operation.summary is None

    async def test_get_manual_warm_operation_returns_stored_operation(self) -> None:
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.RUNNING,
            queued_at=CURRENT_DATETIME,
            summary=None,
        )
        self.operation_storage.get.return_value = operation

        result = await self.use_case.get_manual_warm_operation(operation_id="operation-id")

        assert result == operation

    async def test_get_manual_warm_operation_rejects_unknown_id(self) -> None:
        self.operation_storage.get.return_value = None

        with pytest.raises(CacheWarmOperationNotFoundError):
            await self.use_case.get_manual_warm_operation(operation_id="missing")


class TestManualCacheWarmUseCase:
    def setup_method(self) -> None:
        self.operation_storage = Mock(spec=CacheWarmOperationStorage)
        self.executor = Mock(spec=CacheWarmExecutor)
        self.use_case = ManualCacheWarmUseCase(
            operation_storage=self.operation_storage,
            executor=self.executor,
        )
        self.queued_operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.QUEUED,
            queued_at=CURRENT_DATETIME,
            summary=None,
        )
        self.operation_storage.get.return_value = self.queued_operation

    async def test_run_records_running_and_successful_lifecycle(self) -> None:
        summary = CacheWarmSummary(attempted=12, written=11, skipped=1)
        self.executor.warm_all.return_value = summary

        result = await self.use_case.run(operation_id="operation-id")

        assert result.status is CacheWarmOperationStatusEnum.SUCCEEDED
        assert result.summary == summary
        assert [
            call_.kwargs["operation"].status
            for call_ in self.operation_storage.update.await_args_list
        ] == [
            CacheWarmOperationStatusEnum.RUNNING,
            CacheWarmOperationStatusEnum.SUCCEEDED,
        ]

    async def test_run_records_failed_lifecycle_and_reraises(self) -> None:
        self.executor.warm_all.side_effect = RuntimeError("warm failed")

        with pytest.raises(RuntimeError, match="warm failed"):
            await self.use_case.run(operation_id="operation-id")

        assert [
            call_.kwargs["operation"].status
            for call_ in self.operation_storage.update.await_args_list
        ] == [
            CacheWarmOperationStatusEnum.RUNNING,
            CacheWarmOperationStatusEnum.FAILED,
        ]

    async def test_run_rejects_unknown_operation(self) -> None:
        self.operation_storage.get.return_value = None

        with pytest.raises(CacheWarmOperationNotFoundError):
            await self.use_case.run(operation_id="missing")

        self.executor.warm_all.assert_not_awaited()
