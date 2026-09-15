from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from core.agent_access.schemas import AgentAuditCleanupResult, AgentAuditPolicy
from core.agent_access.storages import AgentAuditStorage
from core.agent_access.use_cases import AgentAuditCleanupUseCase
from tests.test_cases import TestCase


class TestAgentAuditCleanupUseCase(TestCase):
    async def test_prune_expired_audits_uses_explicit_365_day_cutoff(self) -> None:
        current_datetime = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
        storage = Mock(spec=AgentAuditStorage)
        storage.prune_audit_events.return_value = 3
        use_case = AgentAuditCleanupUseCase(storage=storage)
        policy = AgentAuditPolicy(
            page_size_max=100,
            retention_seconds=365 * 24 * 60 * 60,
        )

        result = await use_case.prune_expired_audits(
            current_datetime=current_datetime,
            policy=policy,
        )

        assert result == AgentAuditCleanupResult(deleted_count=3)
        assert result.as_dict() == {"deletedCount": 3}
        storage.prune_audit_events.assert_awaited_once_with(
            created_at_before=current_datetime - timedelta(days=365),
        )
        storage.create_audit_event.assert_not_awaited()
