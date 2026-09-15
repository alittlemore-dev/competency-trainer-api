from unittest.mock import ANY

import pytest_asyncio
from httpx import codes

from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.exceptions import (
    CompetencyMatrixItemNotFoundError,
    CompetencyMatrixItemNotPublicReadyError,
)
from core.competency_matrix.schemas import CompetencyMatrixMissingFieldEnum
from core.enums import PublishStatusEnum
from tests.test_cases import ApiTestCase


class TestUpdateItemAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_update_item_not_found(self) -> None:
        self.use_case.update_item.side_effect = CompetencyMatrixItemNotFoundError()
        response = self.api.put_update_item(
            pk=100500,
            data=self.factory.api.competency_matrix_item_request(
                resources=[
                    self.factory.api.existing_matrix_resource_attachment_request(resource_id=1),
                ],
            ),
        )
        assert response.status_code == codes.NOT_FOUND
        assert response.json() == {
            "code": "client_error",
            "type": "not_found",
            "message": "Competency matrix item not found",
            "attr": None,
            "location": None,
        }

    def test_update_item(self) -> None:
        self.use_case.update_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            question_ru="вопрос 1",
            question_en="question 1",
            answer_ru="ответ 1",
            answer_en="answer 1",
            interview_answer_explanation_ru="объяснение ответа 1",
            interview_answer_explanation_en="interview answer explanation 1",
            sheet_key="python",
            sheet_ru="Питон",
            sheet_en="Python",
            grade=GradeEnum.JUNIOR,
            interview_frequency=InterviewFrequencyEnum.RARELY,
            section_ru="Основы",
            section_en="Basics",
            subsection_ru="Функции",
            subsection_en="Functions",
            publish_status=PublishStatusEnum.DRAFT,
            resources=[
                self.factory.core.attached_external_resource(
                    resource_id=1,
                    name_ru="ресурс 1",
                    name_en="resource 1",
                    url="http://example.com",
                    context_ru="контекст ресурса 1",
                    context_en="resource context 1",
                ),
            ],
        )
        response = self.api.put_update_item(
            pk=100500,
            data=self.factory.api.competency_matrix_item_request(
                interview_frequency="rarely",
                resources=[
                    self.factory.api.existing_matrix_resource_attachment_request(
                        resource_id=1,
                        context_ru="контекст ресурса 1",
                        context_en="resource context 1",
                    ),
                    self.factory.api.new_matrix_resource_attachment_request(
                        name_ru="ресурс 1",
                        name_en="resource 1",
                        url="http://example.com",
                        context_ru="контекст ресурса 2",
                        context_en="resource context 2",
                    ),
                ],
            ),
            language="en",
        )
        self.use_case.update_item.assert_called_once_with(
            params=self.factory.core.competency_matrix_item_update_params(
                item_id=100500,
                question_ru="вопрос 1",
                question_en="question 1",
                answer_ru="ответ 1",
                answer_en="answer 1",
                interview_answer_explanation_ru="объяснение ответа 1",
                interview_answer_explanation_en="interview answer explanation 1",
                sheet_key="python",
                sheet_ru="Питон",
                sheet_en="Python",
                grade=GradeEnum.JUNIOR,
                interview_frequency=InterviewFrequencyEnum.RARELY,
                section_ru="Основы",
                section_en="Basics",
                subsection_ru="Функции",
                subsection_en="Functions",
                publish_status=PublishStatusEnum.DRAFT,
                resources=[
                    self.factory.core.existing_external_resource_attachment(
                        resource_id=1,
                        context_ru="контекст ресурса 1",
                        context_en="resource context 1",
                    ),
                    self.factory.core.new_external_resource_attachment(
                        resource_id=ANY,
                        name_ru="ресурс 1",
                        name_en="resource 1",
                        url="http://example.com",
                        context_ru="контекст ресурса 2",
                        context_en="resource context 2",
                    ),
                ],
            ),
        )
        assert response.status_code == codes.OK, response.json()
        assert response.json()["slug"] == "question-1"
        assert response.json()["question"] == "question 1"
        assert response.json()["sheetKey"] == "python"
        assert response.json()["interviewFrequency"] == "rarely"
        assert response.json()["resources"][0]["translations"] == {
            "ru": {"name": "ресурс 1", "context": "контекст ресурса 1"},
            "en": {"name": "resource 1", "context": "resource context 1"},
        }

    def test_update_item_rejects_incomplete_published_item(self) -> None:
        self.use_case.update_item.side_effect = CompetencyMatrixItemNotPublicReadyError(
            missing_fields=(CompetencyMatrixMissingFieldEnum.ANSWER_EN,),
        )

        response = self.api.put_update_item(
            pk=100500,
            data=self.factory.api.competency_matrix_item_request(
                publish_status=PublishStatusEnum.PUBLISHED,
                answer_en="",
            ),
        )

        assert response.status_code == codes.BAD_REQUEST
        assert response.json()["message"] == "Competency matrix item is not public-ready."

    def test_update_item_requires_explicit_language(self) -> None:
        response = self.api.put_update_item(
            pk=100500,
            data=self.factory.api.competency_matrix_item_request(),
            language=None,
        )
        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.update_item.assert_not_called()
