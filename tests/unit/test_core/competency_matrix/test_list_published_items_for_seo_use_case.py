from unittest.mock import Mock

import pytest

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.schemas import (
    CompetencyMatrixItemFilters,
    PublishedCompetencyMatrixItemForSeo,
    PublishedCompetencyMatrixItemsForSeo,
)
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

    async def test_list_published_items_for_seo_uses_shared_storage_list_and_available_items(
        self,
    ) -> None:
        self.storage.list_competency_matrix_items.return_value = [
            self.factory.core.competency_matrix_item(
                item_id=1,
                slug="published-question",
                question="Published question",
                publish_status=PublishStatusEnum.PUBLISHED,
                sheet_key="python",
                sheet="Python",
                grade=GradeEnum.JUNIOR,
                section="Basics",
                subsection="Functions",
            ),
            self.factory.core.competency_matrix_item(
                item_id=2,
                slug="unavailable-question",
                question="Unavailable question",
                publish_status=PublishStatusEnum.PUBLISHED,
                answer_en="",
                grade=GradeEnum.JUNIOR,
            ),
        ]

        result = await self.use_case.list_published_items_for_seo()

        assert result == PublishedCompetencyMatrixItemsForSeo(
            values=[
                PublishedCompetencyMatrixItemForSeo(
                    slug="published-question",
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
            ],
        )
        self.storage.list_competency_matrix_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(only_published=True),
        )
