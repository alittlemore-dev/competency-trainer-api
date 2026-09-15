import hmac
from datetime import UTC, datetime
from hashlib import sha256
from unittest.mock import Mock

import pytest

from core.competency_matrix.exceptions import QuestionSuggestionQuotaExceededError
from core.competency_matrix.schemas import (
    QuestionSuggestionLimiterConfig,
    QuestionSuggestionLimitParams,
    QuestionSuggestionQuota,
)
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import QuestionSuggestionQuotaStorage
from core.schemas import Secret


class TestQuestionSuggestionLimiter:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.quota_storage = Mock(spec=QuestionSuggestionQuotaStorage)
        config = QuestionSuggestionLimiterConfig(
            quota_secret=Secret("quota-secret"),
            anonymous_daily_limit=10,
        )
        self.limiter = QuestionSuggestionLimiter(
            quota_storage=self.quota_storage,
            config=config,
        )

    async def test_check_create_allowed_consumes_hashed_anonymous_daily_quota(self) -> None:
        self.quota_storage.consume_question_suggestion_quota.return_value = QuestionSuggestionQuota(
            allowed=True,
            remaining=9,
        )

        await self.limiter.check_create_allowed(
            params=QuestionSuggestionLimitParams(
                client_identifier="203.0.113.10",
                now=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
            ),
        )

        expected_key = hmac.new(
            b"quota-secret",
            b"anonymous:203.0.113.10:2026-06-07",
            sha256,
        ).hexdigest()
        self.quota_storage.consume_question_suggestion_quota.assert_called_once_with(
            actor_key=expected_key,
            limit=10,
            ttl_seconds=43_200,
        )
        assert "203.0.113.10" not in repr(
            self.quota_storage.consume_question_suggestion_quota.call_args,
        )

    async def test_check_create_allowed_rejects_when_daily_quota_is_exhausted(self) -> None:
        self.quota_storage.consume_question_suggestion_quota.return_value = QuestionSuggestionQuota(
            allowed=False,
            remaining=0,
        )

        with pytest.raises(QuestionSuggestionQuotaExceededError):
            await self.limiter.check_create_allowed(
                params=QuestionSuggestionLimitParams(
                    client_identifier="203.0.113.10",
                    now=datetime(2026, 6, 7, 23, 59, tzinfo=UTC),
                ),
            )
