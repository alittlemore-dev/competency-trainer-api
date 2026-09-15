import pytest

from entrypoints.taskiq.cache_warm import tasks as cache_warm_tasks_module
from entrypoints.taskiq.cache_warm.dispatcher import TaskiqCacheWarmDispatcher


class TestTaskiqCacheWarmDispatcher:
    async def test_enqueues_operation_id_on_manual_task(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        operation_ids: list[str] = []

        async def fake_kiq(operation_id: str) -> None:
            operation_ids.append(operation_id)

        monkeypatch.setattr(cache_warm_tasks_module.manual_cache_warm, "kiq", fake_kiq)

        await TaskiqCacheWarmDispatcher().enqueue(operation_id="operation-id")

        assert operation_ids == ["operation-id"]
