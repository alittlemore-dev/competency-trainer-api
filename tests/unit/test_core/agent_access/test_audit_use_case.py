from datetime import UTC, datetime
from unittest.mock import Mock

from core.agent_access.enums import AgentActionEnum, AgentAuditResultEnum
from core.agent_access.schemas import AgentAuditEventCreateParams
from core.agent_access.storages import AgentAuditStorage
from core.agent_access.use_cases import AgentAuditUseCase
from tests.test_cases import TestCase


class TestAgentAuditUseCase(TestCase):
    async def test_record_passes_failure_audit_directly_to_storage(self) -> None:
        storage = Mock(spec=AgentAuditStorage)
        use_case = AgentAuditUseCase(storage=storage)
        params = AgentAuditEventCreateParams(
            agent_client_id="a" * 32,
            certificate_id="b" * 32,
            action=AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
            queue_item_id=None,
            matrix_item_id=None,
            request_id="c" * 32,
            result=AgentAuditResultEnum.REJECTED,
            input_digest="d" * 64,
            created_at=datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        )

        await use_case.record(params=params)

        storage.create_audit_event.assert_awaited_once_with(params=params)
