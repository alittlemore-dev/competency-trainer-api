import json

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.agent_access.enums import AgentActionEnum, AgentAuditResultEnum
from core.enums import PublishStatusEnum
from infra.postgresql.models import (
    AgentAuditEventModel,
    CompetencyMatrixItemModel,
    MatrixQuestionClaimModel,
    MatrixQuestionDraftCompletionModel,
    QueuedQuestionModel,
)
from tests.integration.test_api.agent_api.conftest import (
    FullStackAgentApiFixture,
    agent_certificate_headers,
)

_PREFIX = "/internal/agent/v1"
_SECRET_MARKER = "AUTHORED_SECRET_MARKER_full_stack_4b"  # noqa: S105


async def test_private_agent_api_full_stack_transactions_and_durable_audits(  # noqa: PLR0915
    full_stack_agent_api: FullStackAgentApiFixture,
    session: AsyncSession,
) -> None:
    fixture = full_stack_agent_api
    full_headers = agent_certificate_headers(value=fixture.full_certificate_header)

    claim_response = fixture.client.post(
        f"{_PREFIX}/matrix/question-claims",
        headers=full_headers,
    )

    assert claim_response.status_code == 200
    claim_body = claim_response.json()
    claim_id = claim_body["claimId"]
    assert claim_body["queueItemId"] == fixture.queue_item_ids[0]

    save_payload = _save_payload(
        subsection_id=fixture.subsection_id,
        slug="full-stack-agent-success",
        authored_marker="Initial authored content",
    )
    save_response = fixture.client.put(
        f"{_PREFIX}/matrix/question-claims/{claim_id}/draft",
        headers=full_headers,
        json=save_payload,
    )

    assert save_response.status_code == 200
    save_body = save_response.json()
    item_id = save_body["itemId"]
    assert save_body == {"itemId": item_id, "publishStatus": "Draft", "replayed": False}
    session.expire_all()
    item = await session.get(CompetencyMatrixItemModel, item_id)
    completion = await session.get(MatrixQuestionDraftCompletionModel, claim_id)
    assert item is not None
    assert item.publish_status is PublishStatusEnum.DRAFT
    assert item.published_at is None
    assert completion is not None
    assert completion.matrix_item_id == item_id
    assert await session.get(QueuedQuestionModel, fixture.queue_item_ids[0]) is None
    assert await session.get(MatrixQuestionClaimModel, claim_id) is None
    assert await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel)) == 1
    assert (
        await session.scalar(
            select(func.count())
            .select_from(AgentAuditEventModel)
            .where(
                AgentAuditEventModel.action == AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
                AgentAuditEventModel.result == AgentAuditResultEnum.SUCCESS,
                AgentAuditEventModel.request_id == claim_id,
            ),
        )
        == 1
    )

    replay_response = fixture.client.put(
        f"{_PREFIX}/matrix/question-claims/{claim_id}/draft",
        headers=full_headers,
        json=save_payload,
    )

    assert replay_response.status_code == 200
    assert replay_response.json() == {
        "itemId": item_id,
        "publishStatus": "Draft",
        "replayed": True,
    }
    assert await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel)) == 1
    assert (
        await session.scalar(
            select(func.count()).select_from(MatrixQuestionDraftCompletionModel),
        )
        == 1
    )

    changed_payload = dict(save_payload)
    changed_payload["answerEn"] = "Changed replay answer"
    conflict_response = fixture.client.put(
        f"{_PREFIX}/matrix/question-claims/{claim_id}/draft",
        headers=full_headers,
        json=changed_payload,
    )

    assert conflict_response.status_code == 409
    assert conflict_response.json()["code"] == "agent_idempotency_conflict"
    assert await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel)) == 1
    assert (
        await session.scalar(
            select(func.count())
            .select_from(AgentAuditEventModel)
            .where(
                AgentAuditEventModel.action == AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
                AgentAuditEventModel.result == AgentAuditResultEnum.REJECTED,
                AgentAuditEventModel.request_id == claim_id,
            ),
        )
        == 1
    )

    wrong_scope_response = fixture.client.post(
        f"{_PREFIX}/matrix/question-claims",
        headers=agent_certificate_headers(value=fixture.limited_certificate_header),
    )

    assert wrong_scope_response.status_code == 403
    assert wrong_scope_response.json()["code"] == "agent_scope_denied"
    assert await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel)) == 1
    assert await session.scalar(select(func.count()).select_from(MatrixQuestionClaimModel)) == 0
    limited_audit = await session.scalar(
        select(AgentAuditEventModel).where(
            AgentAuditEventModel.agent_client_id == fixture.limited_client_id,
        ),
    )
    assert limited_audit is not None
    assert limited_audit.certificate_id == fixture.limited_certificate_id
    assert limited_audit.action is AgentActionEnum.CLAIM_NEXT_MATRIX_QUESTION
    assert limited_audit.result is AgentAuditResultEnum.REJECTED

    expired_response = fixture.client.post(
        f"{_PREFIX}/matrix/question-claims",
        headers=agent_certificate_headers(value=fixture.expired_certificate_header),
    )

    assert expired_response.status_code == 401
    assert expired_response.json()["code"] == "agent_authentication_failed"
    expired_audit = await session.scalar(
        select(AgentAuditEventModel).where(
            AgentAuditEventModel.agent_client_id == fixture.expired_client_id,
        ),
    )
    assert expired_audit is not None
    assert expired_audit.certificate_id == fixture.expired_certificate_id
    assert expired_audit.result is AgentAuditResultEnum.REJECTED
    assert await session.scalar(select(func.count()).select_from(MatrixQuestionClaimModel)) == 0

    second_claim_response = fixture.client.post(
        f"{_PREFIX}/matrix/question-claims",
        headers=full_headers,
    )
    assert second_claim_response.status_code == 200
    second_claim_id = second_claim_response.json()["claimId"]
    assert second_claim_response.json()["queueItemId"] == fixture.queue_item_ids[1]

    invalid_domain_payload = _save_payload(
        subsection_id=fixture.subsection_id,
        slug="full-stack-agent-invalid-domain",
        authored_marker="Domain validation content",
    )
    invalid_resources = invalid_domain_payload["resources"]
    assert isinstance(invalid_resources, list)
    invalid_resource = invalid_resources[0]
    assert isinstance(invalid_resource, dict)
    invalid_resource["url"] = "http://example.com/not-https"
    invalid_domain_response = fixture.client.put(
        f"{_PREFIX}/matrix/question-claims/{second_claim_id}/draft",
        headers=full_headers,
        json=invalid_domain_payload,
    )

    assert invalid_domain_response.status_code == 400
    assert invalid_domain_response.json()["code"] == "invalid_request"
    assert await session.get(QueuedQuestionModel, fixture.queue_item_ids[1]) is not None
    assert await session.get(MatrixQuestionClaimModel, second_claim_id) is not None
    assert await session.get(MatrixQuestionDraftCompletionModel, second_claim_id) is None
    assert await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel)) == 1

    await fixture.install_success_audit_failure()
    failed_payload = _save_payload(
        subsection_id=fixture.subsection_id,
        slug="full-stack-agent-rolled-back",
        authored_marker=_SECRET_MARKER,
    )
    with structlog.testing.capture_logs() as logs:
        failed_response = fixture.client.put(
            f"{_PREFIX}/matrix/question-claims/{second_claim_id}/draft",
            headers=full_headers,
            json=failed_payload,
        )

    assert failed_response.status_code == 500
    assert failed_response.json()["code"] == "internal_error"
    assert set(failed_response.json()) == {"code", "requestId"}
    assert _SECRET_MARKER not in failed_response.text
    assert _SECRET_MARKER not in json.dumps(logs, default=str)
    assert any(log.get("event") == "agent_api_request_failed" for log in logs)
    session.expire_all()
    assert await session.get(QueuedQuestionModel, fixture.queue_item_ids[1]) is not None
    assert await session.get(MatrixQuestionClaimModel, second_claim_id) is not None
    assert await session.get(MatrixQuestionDraftCompletionModel, second_claim_id) is None
    assert await session.scalar(select(func.count()).select_from(CompetencyMatrixItemModel)) == 1
    assert (
        await session.scalar(
            select(func.count()).where(
                CompetencyMatrixItemModel.question_ru.contains(_SECRET_MARKER),
            ),
        )
        == 0
    )
    failed_audits = list(
        await session.scalars(
            select(AgentAuditEventModel).where(
                AgentAuditEventModel.agent_client_id == fixture.full_client_id,
                AgentAuditEventModel.certificate_id == fixture.full_certificate_id,
                AgentAuditEventModel.action == AgentActionEnum.SAVE_MATRIX_QUESTION_DRAFT,
                AgentAuditEventModel.result == AgentAuditResultEnum.FAILED,
                AgentAuditEventModel.request_id == second_claim_id,
            ),
        ),
    )
    assert len(failed_audits) == 1
    assert _SECRET_MARKER not in repr(failed_audits)


def _save_payload(
    *,
    subsection_id: str,
    slug: str,
    authored_marker: str,
) -> dict[str, object]:
    return {
        "slug": slug,
        "subsectionId": subsection_id,
        "grade": "Middle",
        "interviewFrequency": "often",
        "questionRu": f"Вопрос: {authored_marker}",
        "questionEn": f"Question: {authored_marker}",
        "answerRu": f"Ответ: {authored_marker}",
        "answerEn": f"Answer: {authored_marker}",
        "interviewAnswerExplanationRu": f"Объяснение ответа: {authored_marker}",
        "interviewAnswerExplanationEn": f"Answer explanation: {authored_marker}",
        "resources": [
            {
                "nameRu": "Интеграционный ресурс",
                "nameEn": "Integration resource",
                "url": "https://example.com/agent-integration",
                "contextRu": f"Контекст: {authored_marker}",
                "contextEn": f"Context: {authored_marker}",
            },
        ],
    }
