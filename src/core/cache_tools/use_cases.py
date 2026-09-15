import asyncio
from dataclasses import dataclass, replace
from datetime import datetime

from core.cache_tools.clients import CacheWarmExecutor
from core.cache_tools.enums import CacheWarmOperationStatusEnum
from core.cache_tools.event_dispatchers import CacheWarmTaskDispatcher
from core.cache_tools.exceptions import CacheWarmOperationNotFoundError
from core.cache_tools.schemas import (
    CacheDomainStatus,
    CacheToolsPolicy,
    CacheToolsStatus,
    CacheWarmOperation,
)
from core.cache_tools.storages import (
    CacheWarmOperationStorage,
    ResponseCacheInvalidationStorage,
    ResponseCacheStatusStorage,
)
from core.generators import HexUuidIdGenerator


@dataclass(kw_only=True, frozen=True, slots=True)
class CacheToolsUseCase:
    response_cache_status_storage: ResponseCacheStatusStorage
    response_cache_invalidation_storage: ResponseCacheInvalidationStorage
    operation_storage: CacheWarmOperationStorage
    task_dispatcher: CacheWarmTaskDispatcher
    id_generator: HexUuidIdGenerator

    async def get_status(self, *, policy: CacheToolsPolicy) -> CacheToolsStatus:
        if policy.enabled:
            domain_statuses = tuple(
                await asyncio.gather(
                    *(
                        self.response_cache_status_storage.get_domain_status(domain=domain)
                        for domain in policy.domains
                    ),
                ),
            )
        else:
            domain_statuses = tuple(
                CacheDomainStatus(
                    domain=domain,
                    key_count=0,
                    minimum_remaining_ttl_seconds=None,
                    non_expiring_key_count=0,
                )
                for domain in policy.domains
            )
        return CacheToolsStatus(
            enabled=policy.enabled,
            configured_ttl_seconds=policy.configured_ttl_seconds,
            scheduled_warm_interval_seconds=policy.scheduled_warm_interval_seconds,
            domains=domain_statuses,
            last_manual_warm_operation=await self.operation_storage.get_latest(),
        )

    async def clear(self, *, policy: CacheToolsPolicy) -> CacheToolsStatus:
        if policy.enabled:
            await self.response_cache_invalidation_storage.clear_domains(
                domains=policy.domains,
            )
        return await self.get_status(policy=policy)

    async def enqueue_manual_warm(self, *, current_datetime: datetime) -> CacheWarmOperation:
        operation = CacheWarmOperation(
            operation_id=self.id_generator.get_next(),
            status=CacheWarmOperationStatusEnum.QUEUED,
            queued_at=current_datetime,
            summary=None,
        )
        await self.operation_storage.create(operation=operation)
        try:
            await self.task_dispatcher.enqueue(operation_id=operation.operation_id)
        except Exception:
            await self.operation_storage.update(
                operation=replace(operation, status=CacheWarmOperationStatusEnum.FAILED),
            )
            raise
        return operation

    async def get_manual_warm_operation(self, *, operation_id: str) -> CacheWarmOperation:
        operation = await self.operation_storage.get(operation_id=operation_id)
        if operation is None:
            raise CacheWarmOperationNotFoundError
        return operation


@dataclass(kw_only=True, frozen=True, slots=True)
class ManualCacheWarmUseCase:
    operation_storage: CacheWarmOperationStorage
    executor: CacheWarmExecutor

    async def run(self, *, operation_id: str) -> CacheWarmOperation:
        operation = await self.operation_storage.get(operation_id=operation_id)
        if operation is None:
            raise CacheWarmOperationNotFoundError
        running_operation = replace(
            operation,
            status=CacheWarmOperationStatusEnum.RUNNING,
            summary=None,
        )
        await self.operation_storage.update(operation=running_operation)
        try:
            summary = await self.executor.warm_all()
        except Exception:
            await self.operation_storage.update(
                operation=replace(
                    running_operation,
                    status=CacheWarmOperationStatusEnum.FAILED,
                ),
            )
            raise
        succeeded_operation = replace(
            running_operation,
            status=CacheWarmOperationStatusEnum.SUCCEEDED,
            summary=summary,
        )
        await self.operation_storage.update(operation=succeeded_operation)
        return succeeded_operation
