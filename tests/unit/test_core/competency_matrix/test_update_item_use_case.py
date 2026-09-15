from unittest.mock import Mock

import pytest

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemNotFoundError,
    CompetencyMatrixItemNotPublicReadyError,
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
        self.storage.get_item_structure_by_subsection_id.return_value = (
            self.factory.core.competency_matrix_item_structure()
        )
        self.question_suggestion_limiter = Mock(spec=QuestionSuggestionLimiter)
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=self.question_suggestion_limiter,
        )

    async def test_update_item_rejects_missing_existing_resource(self) -> None:
        self.storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=2,
                suggested_by_username="original-author",
            )
        )
        self.storage.get_resources_by_ids.return_value = self.factory.core.external_resources(
            values=[
                self.factory.core.external_resource(
                    resource_id=1,
                    name="resource 1",
                    url="http://example1.com",
                ),
            ],
        )
        params = self.factory.core.competency_matrix_item_update_params(
            item_id=2,
            resources=[
                self.factory.core.existing_external_resource_attachment(
                    resource_id=1,
                    context="resource context 1",
                ),
                self.factory.core.existing_external_resource_attachment(
                    resource_id=2,
                    context="resource context 2",
                ),
            ],
        )
        with pytest.raises(CompetencyMatrixItemNotFoundError):
            await self.use_case.update_item(params=params)
        self.storage.get_resources_by_ids.assert_called_once_with(
            resource_ids=[self.factory.core.hex_id(1), self.factory.core.hex_id(2)],
        )
        self.storage.update_competency_matrix_item.assert_not_called()

    async def test_update_item_rejects_published_item_with_missing_public_fields(self) -> None:
        self.storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=2,
                suggested_by_username="original-author",
            )
        )
        params = self.factory.core.competency_matrix_item_update_params(
            item_id=2,
            publish_status=PublishStatusEnum.PUBLISHED,
            answer_en="",
        )

        with pytest.raises(CompetencyMatrixItemNotPublicReadyError):
            await self.use_case.update_item(params=params)

        self.storage.update_competency_matrix_item.assert_not_called()

    async def test_update_item(self) -> None:
        self.storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=2,
                suggested_by_username="original-author",
            )
        )
        self.storage.get_resources_by_ids.return_value = self.factory.core.external_resources(
            values=[
                self.factory.core.external_resource(
                    resource_id=1,
                    name="resource 1",
                    url="http://example1.com",
                ),
                self.factory.core.external_resource(
                    resource_id=2,
                    name="resource 2",
                    url="http://example2.com",
                ),
            ],
        )
        params = self.factory.core.competency_matrix_item_update_params(
            item_id=2,
            question="2",
            publish_status=PublishStatusEnum.DRAFT,
            grade=GradeEnum.JUNIOR,
            resources=[
                self.factory.core.existing_external_resource_attachment(
                    resource_id=1,
                    context="resource context 1",
                ),
                self.factory.core.existing_external_resource_attachment(
                    resource_id=2,
                    context="resource context 2",
                ),
                self.factory.core.new_external_resource_attachment(
                    resource_id=3,
                    name="resource 3",
                    url="http://example.com",
                    context="resource context 3",
                ),
            ],
        )
        await self.use_case.update_item(params=params)
        self.storage.get_resources_by_ids.assert_called_once_with(
            resource_ids=[self.factory.core.hex_id(1), self.factory.core.hex_id(2)],
        )
        self.storage.update_competency_matrix_item.assert_called_once_with(
            item=self.factory.core.competency_matrix_item(
                item_id=2,
                question="2",
                publish_status=PublishStatusEnum.DRAFT,
                grade=GradeEnum.JUNIOR,
                suggested_by_username="original-author",
                resources=[
                    self.factory.core.attached_external_resource(
                        resource_id=1,
                        name="resource 1",
                        url="http://example1.com",
                        context="resource context 1",
                    ),
                    self.factory.core.attached_external_resource(
                        resource_id=2,
                        name="resource 2",
                        url="http://example2.com",
                        context="resource context 2",
                    ),
                    self.factory.core.attached_external_resource(
                        resource_id=3,
                        name="resource 3",
                        url="http://example.com",
                        context="resource context 3",
                    ),
                ],
            ),
        )
