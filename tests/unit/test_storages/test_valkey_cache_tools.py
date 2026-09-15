from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, Mock

from litestar.stores.base import Store
from valkey.asyncio import Valkey

from core.cache_tools.enums import CacheDomainEnum, CacheWarmOperationStatusEnum
from core.cache_tools.schemas import CacheWarmOperation, CacheWarmSummary
from infra.valkey.storages import (
    ValkeyCacheWarmOperationStorage,
    ValkeyResponseCacheStatusStorage,
)


class TestValkeyResponseCacheStatusStorage:
    async def test_counts_keys_and_ttl_states_across_scan_pages(self) -> None:
        valkey = Mock(spec=Valkey)
        valkey.scan = AsyncMock(
            side_effect=[
                (7, [b"LITESTAR_articles:first", b"LITESTAR_articles:second"]),
                (
                    0,
                    [
                        b"LITESTAR_articles:second",
                        b"LITESTAR_articles:third",
                        b"LITESTAR_articles:vanished",
                    ],
                ),
            ],
        )
        first_pipeline = Mock()
        first_pipeline.ttl = Mock()
        first_pipeline.execute = AsyncMock(return_value=[120, -1])
        second_pipeline = Mock()
        second_pipeline.ttl = Mock()
        second_pipeline.execute = AsyncMock(return_value=[30, -2])
        valkey.pipeline.side_effect = [first_pipeline, second_pipeline]
        storage = ValkeyResponseCacheStatusStorage(
            valkey=valkey,
            namespaces={CacheDomainEnum.ARTICLES: "LITESTAR_articles"},
            scan_batch_size=200,
        )

        result = await storage.get_domain_status(domain=CacheDomainEnum.ARTICLES)

        assert result.domain is CacheDomainEnum.ARTICLES
        assert result.key_count == 3
        assert result.minimum_remaining_ttl_seconds == 30
        assert result.non_expiring_key_count == 1
        assert valkey.scan.await_args_list[0].kwargs == {
            "cursor": 0,
            "match": "LITESTAR_articles:*",
            "count": 200,
        }
        assert valkey.scan.await_args_list[1].kwargs["cursor"] == 7

    async def test_empty_domain_has_no_minimum_ttl(self) -> None:
        valkey = Mock(spec=Valkey)
        valkey.scan = AsyncMock(return_value=(0, []))
        storage = ValkeyResponseCacheStatusStorage(
            valkey=valkey,
            namespaces={CacheDomainEnum.I18N: "LITESTAR_i18n"},
            scan_batch_size=200,
        )

        result = await storage.get_domain_status(domain=CacheDomainEnum.I18N)

        assert result.key_count == 0
        assert result.minimum_remaining_ttl_seconds is None
        assert result.non_expiring_key_count == 0
        valkey.pipeline.assert_not_called()


class TestValkeyCacheWarmOperationStorage:
    async def test_create_persists_operation_and_latest_pointer_with_bounded_ttl(self) -> None:
        store = Mock(spec=Store)
        storage = ValkeyCacheWarmOperationStorage(store=store, expires_in_seconds=3_600)
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.QUEUED,
            queued_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
            summary=None,
        )

        await storage.create(operation=operation)

        assert store.set.await_count == 2
        assert {call_.kwargs["key"] for call_ in store.set.await_args_list} == {
            "operation:operation-id",
            "latest",
        }
        assert all(call_.kwargs["expires_in"] == 3_600 for call_ in store.set.await_args_list)

    async def test_update_refreshes_operation_and_latest_pointer_ttl_atomically(self) -> None:
        store = Mock(spec=Store)
        store.get.return_value = b"operation-id"
        storage = ValkeyCacheWarmOperationStorage(store=store, expires_in_seconds=3_600)
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.RUNNING,
            queued_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
            summary=None,
        )

        await storage.update(operation=operation)

        store.set.assert_awaited_once()
        assert store.set.await_args.kwargs["key"] == "operation:operation-id"
        assert store.set.await_args.kwargs["expires_in"] == 3_600
        store.get.assert_awaited_once_with(key="latest", renew_for=3_600)

    async def test_update_does_not_replace_a_newer_latest_pointer(self) -> None:
        store = Mock(spec=Store)
        store.get.return_value = b"newer-operation-id"
        storage = ValkeyCacheWarmOperationStorage(store=store, expires_in_seconds=3_600)
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.RUNNING,
            queued_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
            summary=None,
        )

        await storage.update(operation=operation)

        store.set.assert_awaited_once()
        assert store.set.await_args.kwargs["key"] == "operation:operation-id"
        store.get.assert_awaited_once_with(key="latest", renew_for=3_600)

    async def test_round_trips_successful_operation(self) -> None:
        store = Mock(spec=Store)
        storage = ValkeyCacheWarmOperationStorage(store=store, expires_in_seconds=3_600)
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.SUCCEEDED,
            queued_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
            summary=CacheWarmSummary(attempted=3, written=2, skipped=1),
        )
        store.get.return_value = storage.serialize(operation=operation)

        result = await storage.get(operation_id="operation-id")

        assert result == operation

    async def test_get_latest_uses_pointer_without_unbounded_listing(self) -> None:
        store = Mock(spec=Store)
        storage = ValkeyCacheWarmOperationStorage(
            store=cast("Store", store), expires_in_seconds=3_600
        )
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.RUNNING,
            queued_at=datetime(2026, 7, 16, 12, 0, tzinfo=UTC),
            summary=None,
        )
        store.get.side_effect = [b"operation-id", storage.serialize(operation=operation)]

        result = await storage.get_latest()

        assert result == operation
        assert [call_.kwargs["key"] for call_ in store.get.await_args_list] == [
            "latest",
            "operation:operation-id",
        ]

    async def test_missing_operation_and_latest_pointer_return_none(self) -> None:
        store = Mock(spec=Store)
        store.get.return_value = None
        storage = ValkeyCacheWarmOperationStorage(store=store, expires_in_seconds=3_600)

        operation = await storage.get(operation_id="missing")
        latest = await storage.get_latest()

        assert operation is None
        assert latest is None
