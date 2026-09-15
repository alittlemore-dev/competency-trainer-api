from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from core.competency_matrix.enums import (
    CompetencyMatrixWorkspaceSortEnum,
    GradeEnum,
    InterviewFrequencyEnum,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixWorkspaceFilters,
    CompetencyMatrixWorkspaceItem,
    CompetencyMatrixWorkspaceSummary,
)
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from tests.test_cases import TestCase


class TestCompetencyMatrixWorkspaceUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=CompetencyMatrixStorage)
        self.question_suggestion_limiter = Mock(spec=QuestionSuggestionLimiter)
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=self.question_suggestion_limiter,
        )

    async def test_list_workspace_items_builds_paginated_workspace(self) -> None:
        filters = CompetencyMatrixWorkspaceFilters(
            page=2,
            page_size=1,
            language=LanguageEnum.EN,
            sort=CompetencyMatrixWorkspaceSortEnum.NEWEST,
        )
        published_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        item = CompetencyMatrixWorkspaceItem(
            id=self.factory.core.hex_id(10),
            slug="python-functions",
            question="How do functions work?",
            sheet_key="python",
            sheet="Python",
            grade=GradeEnum.JUNIOR,
            interview_frequency=InterviewFrequencyEnum.OFTEN,
            section="Basics",
            subsection="Functions",
            publish_status=PublishStatusEnum.PUBLISHED,
            published_at=published_at,
            missing_fields=(),
        )
        summary = CompetencyMatrixWorkspaceSummary(
            total=2,
            draft=1,
            missing_draft=1,
            dangerous_published=0,
            ready_published=1,
        )
        self.storage.list_competency_matrix_workspace_items.return_value = ([item], 2, summary)

        workspace = await self.use_case.list_workspace_items(filters=filters)

        assert workspace.total_count == 2
        assert workspace.total_pages == 2
        assert workspace.summary == summary
        assert workspace.values == [item]
        self.storage.list_competency_matrix_workspace_items.assert_called_once_with(
            filters=filters,
        )
