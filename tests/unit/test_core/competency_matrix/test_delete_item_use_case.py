from unittest.mock import Mock

import pytest

from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
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

    async def test_delete(self) -> None:
        item_id = self.factory.core.hex_id(1)
        await self.use_case.delete_item(item_id=item_id)
        self.storage.delete_competency_matrix_item.assert_called_once_with(item_id=item_id)
