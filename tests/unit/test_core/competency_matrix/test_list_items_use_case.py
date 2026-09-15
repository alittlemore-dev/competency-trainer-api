from unittest.mock import Mock

import pytest

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.schemas import CompetencyMatrixItemFilters
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

    async def test_not_available(self) -> None:
        self.storage.list_competency_matrix_items.return_value = [
            self.factory.core.competency_matrix_item(
                item_id=1,
                question="1",
                publish_status=PublishStatusEnum.DRAFT,
                sheet="Python",
                grade=None,
                section="",
                subsection="",
            ),
        ]
        items = await self.use_case.list_items(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=True),
        )
        assert items.values == []
        self.storage.list_competency_matrix_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=True),
        )

    async def test_available(self) -> None:
        self.storage.list_competency_matrix_items.return_value = [
            self.factory.core.competency_matrix_item(
                item_id=1,
                question="1",
                publish_status=PublishStatusEnum.PUBLISHED,
                sheet_key="python",
                sheet="Python",
                grade=GradeEnum.JUNIOR,
                section="1",
                subsection="1",
            ),
        ]
        items = await self.use_case.list_items(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=True),
        )
        assert items.values == [
            self.factory.core.competency_matrix_item(
                item_id=1,
                question="1",
                publish_status=PublishStatusEnum.PUBLISHED,
                sheet_key="python",
                sheet="Python",
                grade=GradeEnum.JUNIOR,
                section="1",
                subsection="1",
            ),
        ]

    async def test_availability_skip(self) -> None:
        self.storage.list_competency_matrix_items.return_value = [
            self.factory.core.competency_matrix_item(
                item_id=1,
                question="1",
                publish_status=PublishStatusEnum.DRAFT,
                sheet="Python",
                grade=None,
                section="",
                subsection="",
            ),
        ]
        items = await self.use_case.list_items(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=False),
        )
        assert items.values == [
            self.factory.core.competency_matrix_item(
                item_id=1,
                question="1",
                publish_status=PublishStatusEnum.DRAFT,
                sheet="Python",
                grade=None,
                section="",
                subsection="",
            ),
        ]
        self.storage.list_competency_matrix_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=False),
        )
