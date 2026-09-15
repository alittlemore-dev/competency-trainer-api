from datetime import UTC, datetime, timedelta
from typing import Any, cast
from unittest.mock import Mock

from core.files.schemas import FileOrphanCleanupResult
from core.files.services import FileOrphanCleanupService
from entrypoints.taskiq.files import tasks as file_tasks_module
from infra.config.settings import settings


async def test_file_orphan_prune_uses_retention_cutoff_and_returns_camel_case_counts() -> None:
    current_datetime = datetime(2026, 8, 5, 12, 30, tzinfo=UTC)
    service = Mock(spec=FileOrphanCleanupService)
    service.prune.return_value = FileOrphanCleanupResult(
        scanned_count=4,
        deleted_count=2,
        failed_count=1,
        skipped_in_use_count=1,
    )

    injected_func = cast("Any", file_tasks_module.prune_file_orphans.original_func)
    result = await injected_func.__dishka_orig_func__(
        service=service,
        current_datetime=current_datetime,
    )

    service.prune.assert_awaited_once_with(
        cutoff=current_datetime - timedelta(seconds=settings.files.orphan_retention_seconds),
    )
    assert result == {
        "scannedCount": 4,
        "deletedCount": 2,
        "failedCount": 1,
        "skippedInUseCount": 1,
    }
