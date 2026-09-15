from dataclasses import dataclass

from core.cache_tools.event_dispatchers import CacheWarmTaskDispatcher


@dataclass(kw_only=True, frozen=True, slots=True)
class TaskiqCacheWarmDispatcher(CacheWarmTaskDispatcher):
    async def enqueue(self, *, operation_id: str) -> None:
        from entrypoints.taskiq.cache_warm.tasks import manual_cache_warm  # noqa: PLC0415

        await manual_cache_warm.kiq(operation_id)  # type: ignore[call-overload]
