from datetime import UTC, datetime
from typing import Any, cast
from unittest.mock import Mock

from core.auth.schemas import (
    AuthSessionCleanupParams,
    AuthSessionCleanupPolicy,
    AuthSessionCleanupResult,
)
from core.auth.use_cases import AuthSessionCleanupUseCase
from entrypoints.taskiq.auth import tasks as auth_tasks_module


async def test_auth_session_prune_passes_cleanup_policy_and_returns_counts() -> None:
    current_datetime = datetime(2026, 8, 5, 12, 30, tzinfo=UTC)
    policy = AuthSessionCleanupPolicy(
        expiring_soon_days=7,
        scheduled_prune_interval_seconds=86_400,
    )
    use_case = Mock(spec=AuthSessionCleanupUseCase)
    use_case.prune_expired_sessions.return_value = AuthSessionCleanupResult(
        deleted_count=3,
        expired_count=0,
        expiring_soon_count=4,
        expiring_soon_days=7,
        scheduled_prune_interval_seconds=86_400,
    )

    injected_func = cast("Any", auth_tasks_module.prune_expired_auth_sessions.original_func)
    result = await injected_func.__dishka_orig_func__(
        use_case=use_case,
        current_datetime=current_datetime,
        policy=policy,
    )

    use_case.prune_expired_sessions.assert_awaited_once_with(
        policy=policy,
        params=AuthSessionCleanupParams(current_datetime=current_datetime),
    )
    assert result == {
        "deletedCount": 3,
        "expiredCount": 0,
        "expiringSoonCount": 4,
        "expiringSoonDays": 7,
        "scheduledPruneIntervalSeconds": 86_400,
    }
