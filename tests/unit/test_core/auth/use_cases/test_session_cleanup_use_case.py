from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from core.auth.schemas import (
    AuthSessionCleanupCounts,
    AuthSessionCleanupParams,
    AuthSessionCleanupPolicy,
    AuthSessionCleanupResult,
    AuthSessionCleanupStatus,
)
from core.auth.storages import AuthSessionStorage
from core.auth.use_cases import AuthSessionCleanupUseCase
from tests.test_cases import TestCase


class TestAuthSessionCleanupUseCase(TestCase):
    def setup_method(self) -> None:
        current_datetime = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
        self.current_datetime = current_datetime
        self.expiring_soon_at = current_datetime + timedelta(days=7)
        self.auth_session_storage = Mock(spec=AuthSessionStorage)
        self.policy = AuthSessionCleanupPolicy(
            expiring_soon_days=7,
            scheduled_prune_interval_seconds=86_400,
        )
        self.use_case = AuthSessionCleanupUseCase(
            auth_session_storage=self.auth_session_storage,
        )

    async def test_get_cleanup_status_counts_expired_and_expiring_soon_sessions(self) -> None:
        self.auth_session_storage.count_cleanup_sessions.return_value = AuthSessionCleanupCounts(
            expired_count=3,
            expiring_soon_count=4,
        )

        result = await self.use_case.get_cleanup_status(
            policy=self.policy,
            params=AuthSessionCleanupParams(current_datetime=self.current_datetime),
        )

        assert result == AuthSessionCleanupStatus(
            expired_count=3,
            expiring_soon_count=4,
            expiring_soon_days=7,
            scheduled_prune_interval_seconds=86_400,
        )
        self.auth_session_storage.count_cleanup_sessions.assert_called_once_with(
            expired_at=self.current_datetime,
            expiring_soon_at=self.expiring_soon_at,
        )

    async def test_prune_expired_sessions_returns_refreshed_cleanup_status(self) -> None:
        self.auth_session_storage.delete_expired_sessions.return_value = 3
        self.auth_session_storage.count_cleanup_sessions.return_value = AuthSessionCleanupCounts(
            expired_count=0,
            expiring_soon_count=4,
        )

        result = await self.use_case.prune_expired_sessions(
            policy=self.policy,
            params=AuthSessionCleanupParams(current_datetime=self.current_datetime),
        )

        assert result == AuthSessionCleanupResult(
            deleted_count=3,
            expired_count=0,
            expiring_soon_count=4,
            expiring_soon_days=7,
            scheduled_prune_interval_seconds=86_400,
        )
        assert result.as_dict() == {
            "deletedCount": 3,
            "expiredCount": 0,
            "expiringSoonCount": 4,
            "expiringSoonDays": 7,
            "scheduledPruneIntervalSeconds": 86_400,
        }
        self.auth_session_storage.delete_expired_sessions.assert_called_once_with(
            expires_at=self.current_datetime,
        )
        self.auth_session_storage.count_cleanup_sessions.assert_called_once_with(
            expired_at=self.current_datetime,
            expiring_soon_at=self.expiring_soon_at,
        )
