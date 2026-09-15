import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from hashlib import sha256

from core.competency_matrix.exceptions import QuestionSuggestionQuotaExceededError
from core.competency_matrix.schemas import (
    QuestionSuggestionLimiterConfig,
    QuestionSuggestionLimitParams,
)
from core.competency_matrix.storages import QuestionSuggestionQuotaStorage


@dataclass(kw_only=True, slots=True, frozen=True)
class QuestionSuggestionLimiter:
    quota_storage: QuestionSuggestionQuotaStorage
    config: QuestionSuggestionLimiterConfig

    async def check_create_allowed(self, *, params: QuestionSuggestionLimitParams) -> None:
        now_utc = params.now.astimezone(UTC)
        quota = await self.quota_storage.consume_question_suggestion_quota(
            actor_key=self._anonymous_actor_key(
                client_identifier=params.client_identifier,
                now=now_utc,
            ),
            limit=self.config.anonymous_daily_limit,
            ttl_seconds=self._seconds_until_next_utc_day(now=now_utc),
        )
        if not quota.allowed:
            raise QuestionSuggestionQuotaExceededError

    def _anonymous_actor_key(self, *, client_identifier: str, now: datetime) -> str:
        payload = f"anonymous:{client_identifier}:{now.date().isoformat()}"
        return hmac.new(
            self.config.quota_secret.get_secret_value().encode(),
            payload.encode(),
            sha256,
        ).hexdigest()

    def _seconds_until_next_utc_day(self, *, now: datetime) -> int:
        next_day = datetime.combine(now.date() + timedelta(days=1), time.min, tzinfo=UTC)
        return int((next_day - now).total_seconds())
