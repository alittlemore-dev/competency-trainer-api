from unittest.mock import Mock

import pytest

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.schemas import CompetencyMatrixItemBySlugGetParams
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.enums import PublishStatusEnum
from tests.test_cases import TestCase


class TestCompetencyMatrixUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=CompetencyMatrixStorage)
        self.question_suggestion_limiter = Mock(spec=QuestionSuggestionLimiter)
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=self.question_suggestion_limiter,
        )

    async def test_get_item_by_slug_rejects_unavailable_public_item(self) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=2,
            question="Draft question",
            publish_status=PublishStatusEnum.DRAFT,
            sheet="Python",
            grade=None,
            section="",
            subsection="",
        )
        self.storage.get_competency_matrix_item_by_slug.return_value = item

        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.use_case.get_item_by_slug(
                params=CompetencyMatrixItemBySlugGetParams(
                    slug="draft-question",
                    only_published=True,
                ),
            )

    async def test_get_item_by_slug_returns_available_public_item(self) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=1,
            question="How to write a function?",
            publish_status=PublishStatusEnum.PUBLISHED,
            sheet="Python",
            grade=GradeEnum.JUNIOR,
            section="Basics",
            subsection="Functions",
        )
        self.storage.get_competency_matrix_item_by_slug.return_value = item

        result = await self.use_case.get_item_by_slug(
            params=CompetencyMatrixItemBySlugGetParams(
                slug="how-to-write-a-function",
                only_published=True,
            ),
        )

        assert result == item
        self.storage.get_competency_matrix_item_by_slug.assert_called_once_with(
            slug="how-to-write-a-function",
        )
