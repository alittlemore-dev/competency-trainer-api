from unittest.mock import Mock

import pytest

from core.competency_matrix.exceptions import CompetencyMatrixItemNotPublicReadyError
from core.competency_matrix.schemas import CompetencyMatrixItemPublishStatusSwitchParams
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

    async def test_set_draft(self) -> None:
        await self.use_case.switch_item_publish_status(
            params=CompetencyMatrixItemPublishStatusSwitchParams(
                item_id=self.factory.core.hex_id(1),
                publish_status=PublishStatusEnum.DRAFT,
            ),
        )
        self.storage.get_competency_matrix_item.assert_not_called()
        self.storage.update_competency_matrix_item_publish_status.assert_called_once_with(
            item_id=self.factory.core.hex_id(1),
            publish_status=PublishStatusEnum.DRAFT,
        )

    async def test_set_published(self) -> None:
        self.storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=1,
                publish_status=PublishStatusEnum.DRAFT,
            )
        )

        await self.use_case.switch_item_publish_status(
            params=CompetencyMatrixItemPublishStatusSwitchParams(
                item_id=self.factory.core.hex_id(1),
                publish_status=PublishStatusEnum.PUBLISHED,
            ),
        )
        self.storage.get_competency_matrix_item.assert_called_once_with(
            item_id=self.factory.core.hex_id(1),
        )
        self.storage.update_competency_matrix_item_publish_status.assert_called_once_with(
            item_id=self.factory.core.hex_id(1),
            publish_status=PublishStatusEnum.PUBLISHED,
        )

    async def test_set_published_rejects_item_with_missing_public_fields(self) -> None:
        self.storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=1,
                publish_status=PublishStatusEnum.DRAFT,
                answer_en="",
            )
        )

        with pytest.raises(CompetencyMatrixItemNotPublicReadyError):
            await self.use_case.switch_item_publish_status(
                params=CompetencyMatrixItemPublishStatusSwitchParams(
                    item_id=self.factory.core.hex_id(1),
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
            )

        self.storage.update_competency_matrix_item_publish_status.assert_not_called()
