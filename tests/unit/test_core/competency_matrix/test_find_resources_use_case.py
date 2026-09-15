from unittest.mock import Mock

import pytest

from core.competency_matrix.schemas import CompetencyMatrixResourceSearchParams
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.i18n.enums import LanguageEnum
from tests.test_cases import TestCase


class TestFindResourcesItemUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=CompetencyMatrixStorage)
        self.question_suggestion_limiter = Mock(spec=QuestionSuggestionLimiter)
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=self.question_suggestion_limiter,
        )

    async def test_search_resources(self) -> None:
        search_name = self.factory.core.search_name("Find")
        await self.use_case.find_resources(
            params=CompetencyMatrixResourceSearchParams(
                search_name=search_name,
                limit=10,
                language=LanguageEnum.EN,
            ),
        )
        self.storage.search_competency_matrix_resources.assert_called_once_with(
            search_name="find",
            limit=10,
            language=LanguageEnum.EN,
        )
