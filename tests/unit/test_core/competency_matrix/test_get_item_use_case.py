from unittest.mock import Mock

import pytest

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.schemas import CompetencyMatrixItemGetParams
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
        item = self.factory.core.competency_matrix_item(
            item_id=2,
            question="2",
            publish_status=PublishStatusEnum.DRAFT,
            sheet="Python",
            grade=None,
            section="",
            subsection="",
        )
        self.storage.get_competency_matrix_item.return_value = item
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.use_case.get_item(
                params=CompetencyMatrixItemGetParams(
                    item_id=self.factory.core.hex_id(2),
                    only_published=True,
                ),
            )

    async def test_available(self) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=1,
            question="1",
            publish_status=PublishStatusEnum.PUBLISHED,
            sheet="Python",
            grade=GradeEnum.JUNIOR,
            section="1",
            subsection="1",
        )
        self.storage.get_competency_matrix_item.return_value = item
        res_item = await self.use_case.get_item(
            params=CompetencyMatrixItemGetParams(
                item_id=self.factory.core.hex_id(1),
                only_published=True,
            ),
        )
        assert item == res_item

    async def test_availability_skip(self) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=1,
            question="1",
            publish_status=PublishStatusEnum.DRAFT,
            sheet="Python",
            grade=None,
            section="",
            subsection="",
        )
        self.storage.get_competency_matrix_item.return_value = item
        res_item = await self.use_case.get_item(
            params=CompetencyMatrixItemGetParams(
                item_id=self.factory.core.hex_id(1),
                only_published=False,
            ),
        )
        assert item == res_item
