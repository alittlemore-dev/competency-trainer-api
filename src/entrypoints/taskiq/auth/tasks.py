from datetime import datetime

from dishka.integrations.taskiq import FromDishka, inject

from core.auth.schemas import AuthSessionCleanupParams, AuthSessionCleanupPolicy
from core.auth.use_cases import AuthSessionCleanupUseCase
from entrypoints.taskiq.broker import broker
from infra.config.constants import constants
from infra.config.settings import settings


@broker.task(
    constants.taskiq.auth_session_prune_task_name,
    schedule=[
        {
            "schedule_id": constants.taskiq.auth_session_prune_task_name,
            "interval": settings.taskiq.auth_session_prune_interval_seconds,
        },
    ],
)
@inject(patch_module=True)
async def prune_expired_auth_sessions(
    use_case: FromDishka[AuthSessionCleanupUseCase],
    current_datetime: FromDishka[datetime],
    policy: FromDishka[AuthSessionCleanupPolicy],
) -> dict[str, int]:
    return (
        await use_case.prune_expired_sessions(
            policy=policy,
            params=AuthSessionCleanupParams(current_datetime=current_datetime),
        )
    ).as_dict()
