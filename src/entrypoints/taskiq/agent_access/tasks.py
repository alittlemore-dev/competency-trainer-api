from datetime import datetime

from dishka.integrations.taskiq import FromDishka, inject

from core.agent_access.schemas import AgentAuditPolicy
from core.agent_access.use_cases import AgentAuditCleanupUseCase
from entrypoints.taskiq.broker import broker
from infra.config.constants import constants
from infra.config.settings import settings


@broker.task(
    constants.taskiq.agent_audit_prune_task_name,
    schedule=[
        {
            "schedule_id": constants.taskiq.agent_audit_prune_task_name,
            "interval": settings.taskiq.agent_audit_prune_interval_seconds,
        },
    ],
)
@inject(patch_module=True)
async def prune_expired_agent_audits(
    use_case: FromDishka[AgentAuditCleanupUseCase],
    current_datetime: FromDishka[datetime],
    policy: FromDishka[AgentAuditPolicy],
) -> dict[str, int]:
    return (
        await use_case.prune_expired_audits(
            current_datetime=current_datetime,
            policy=policy,
        )
    ).as_dict()
