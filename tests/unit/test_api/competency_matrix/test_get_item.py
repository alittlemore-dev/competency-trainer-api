import pytest_asyncio
from httpx import codes

from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.schemas import (
    CompetencyMatrixItemBySlugGetParams,
    CompetencyMatrixItemGetParams,
)
from core.enums import PublishStatusEnum
from tests.test_cases import ApiTestCase


class TestGetItemAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_get_competency_matrix_item_not_found(self) -> None:
        self.use_case.get_item.side_effect = CompetencyMatrixItemNotFoundError()
        response = self.api.get_admin_competency_matrix_item(pk=-100)
        assert response.status_code == codes.NOT_FOUND
        assert response.json() == {
            "code": "client_error",
            "type": "not_found",
            "message": "Competency matrix item not found",
            "attr": None,
            "location": None,
        }

    def test_admin_get_competency_matrix_item_requires_only_published(self) -> None:
        response = self.api.get_admin_competency_matrix_item(pk=1, only_published=None)
        assert response.status_code == codes.BAD_REQUEST
        self.use_case.get_item.assert_not_called()

    def test_admin_get_competency_matrix_item(self) -> None:
        self.use_case.get_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            slug="how-to-write-function",
            question_ru="Как написать свою функцию?",
            question_en="How to write a function?",
            publish_status=PublishStatusEnum.PUBLISHED,
            suggested_by_username="alice",
            answer_ru="Просто берёшь и пишешь!",
            answer_en="Just write it.",
            interview_answer_explanation_ru="Пиши!",
            interview_answer_explanation_en="Write it!",
            grade=GradeEnum.JUNIOR,
            subsection_ru="Функции",
            subsection_en="Functions",
            section_ru="Основы",
            section_en="Basics",
            sheet_key="python",
            sheet_ru="Питон",
            sheet_en="Python",
            interview_frequency=InterviewFrequencyEnum.CONSTANTLY,
            resources=[
                self.factory.core.attached_external_resource(
                    resource_id=1,
                    name_ru="ресурс",
                    name_en="resource",
                    url="http://example.com",
                    context_ru="контекст ресурса",
                    context_en="resource context",
                ),
            ],
        )
        response = self.api.get_admin_competency_matrix_item(
            pk=1,
            only_published=False,
            language="en",
        )
        assert response.status_code == codes.OK
        assert response.json() == {
            "id": self.factory.core.hex_id(1),
            "slug": "how-to-write-function",
            "question": "How to write a function?",
            "answer": "Just write it.",
            "interviewAnswerExplanation": "Write it!",
            "subsectionId": self.factory.core.hex_id(1),
            "grade": "Junior",
            "subsection": "Functions",
            "section": "Basics",
            "sheetKey": "python",
            "sheet": "Python",
            "interviewFrequency": "constantly",
            "publishStatus": "Published",
            "suggestedByUsername": "alice",
            "translations": {
                "ru": {
                    "question": "Как написать свою функцию?",
                    "answer": "Просто берёшь и пишешь!",
                    "interviewAnswerExplanation": "Пиши!",
                },
                "en": {
                    "question": "How to write a function?",
                    "answer": "Just write it.",
                    "interviewAnswerExplanation": "Write it!",
                },
            },
            "resources": [
                {
                    "id": self.factory.core.hex_id(1),
                    "name": "resource",
                    "url": "http://example.com",
                    "context": "resource context",
                    "translations": {
                        "ru": {"name": "ресурс", "context": "контекст ресурса"},
                        "en": {"name": "resource", "context": "resource context"},
                    },
                },
            ],
        }
        self.use_case.get_item.assert_called_once_with(
            params=CompetencyMatrixItemGetParams(
                item_id=self.factory.core.hex_id(1),
                only_published=False,
            ),
        )

    def test_get_competency_matrix_item_serializes_large_id_as_string(self) -> None:
        self.use_case.get_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1_152_921_504_606_846_975,
            slug="large-id-question",
            question_en="Question with large id?",
            publish_status=PublishStatusEnum.PUBLISHED,
            suggested_by_username="anon",
            answer_en="Answer.",
            interview_answer_explanation_en="Answer explanation.",
            grade=GradeEnum.JUNIOR,
            subsection_en="Functions",
            section_en="Basics",
            sheet_key="python",
            sheet_en="Python",
        )

        response = self.api.get_admin_competency_matrix_item(
            pk=1_152_921_504_606_846_975,
            only_published=False,
            language="en",
        )

        assert response.status_code == codes.OK
        assert response.json()["id"] == self.factory.core.hex_id(1_152_921_504_606_846_975)
        self.use_case.get_item.assert_called_once_with(
            params=CompetencyMatrixItemGetParams(
                item_id=self.factory.core.hex_id(1_152_921_504_606_846_975),
                only_published=False,
            ),
        )

    def test_get_public_competency_matrix_item_by_slug(self) -> None:
        self.use_case.get_item_by_slug.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            slug="how-to-write-function",
            question_ru="Как написать свою функцию?",
            question_en="How to write a function?",
            publish_status=PublishStatusEnum.PUBLISHED,
            answer_ru="Просто берёшь и пишешь!",
            answer_en="Just write it.",
            interview_answer_explanation_ru="Пиши!",
            interview_answer_explanation_en="Write it!",
            grade=GradeEnum.JUNIOR,
            subsection_ru="Функции",
            subsection_en="Functions",
            section_ru="Основы",
            section_en="Basics",
            sheet_key="python",
            sheet_ru="Питон",
            sheet_en="Python",
            interview_frequency=InterviewFrequencyEnum.NEVER_SEEN,
            suggested_by_username="anon",
        )
        response = self.no_auth_api.get_public_competency_matrix_item(
            slug="how-to-write-function",
            language="en",
        )
        assert response.status_code == codes.OK
        body = response.json()
        assert "id" not in body
        assert body["slug"] == "how-to-write-function"
        assert body["question"] == "How to write a function?"
        assert body["interviewFrequency"] == "neverSeen"
        assert body["suggestedByUsername"] == "anon"
        self.use_case.get_item_by_slug.assert_called_once_with(
            params=CompetencyMatrixItemBySlugGetParams(
                slug="how-to-write-function",
                only_published=True,
            ),
        )

    def test_get_public_competency_matrix_item_requires_explicit_language(self) -> None:
        response = self.no_auth_api.get_public_competency_matrix_item(
            slug="how-to-write-function",
            language=None,
        )
        assert response.status_code == codes.BAD_REQUEST
        self.use_case.get_item_by_slug.assert_not_called()

    def test_get_public_competency_matrix_item_not_found(self) -> None:
        self.use_case.get_item_by_slug.side_effect = CompetencyMatrixItemNotFoundError()
        response = self.no_auth_api.get_public_competency_matrix_item(
            slug="missing-question",
            language="ru",
        )
        assert response.status_code == codes.NOT_FOUND
        assert response.json()["message"] == "Competency matrix item not found"
