from unittest.mock import ANY

import pytest
import pytest_asyncio
from httpx import codes

from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.enums import PublishStatusEnum
from tests.test_cases import ApiTestCase


class TestCreateItemAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.generated_id = (await self.container.get_hex_uuid_id_generator()).get_next()
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_create_item(self) -> None:
        self.use_case.create_item.return_value = self.factory.core.competency_matrix_item(
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
            interview_frequency=InterviewFrequencyEnum.OFTEN,
            section_ru="Основы",
            section_en="Basics",
            subsection_ru="Функции",
            subsection_en="Functions",
            publish_status=PublishStatusEnum.DRAFT,
            suggested_by_username="test",
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
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(
                resources=[
                    self.factory.api.existing_matrix_resource_attachment_request(
                        resource_id=1,
                        context_ru="контекст ресурса 1",
                        context_en="resource context 1",
                    ),
                    self.factory.api.existing_matrix_resource_attachment_request(
                        resource_id=2,
                        context_ru="контекст ресурса 2",
                        context_en="resource context 2",
                    ),
                    self.factory.api.new_matrix_resource_attachment_request(
                        name_ru="ресурс 1",
                        name_en="resource 1",
                        url="http://example.com",
                        context_ru="контекст ресурса 3",
                        context_en="resource context 3",
                    ),
                ],
            ),
            language="en",
        )
        self.use_case.create_item.assert_called_once_with(
            params=self.factory.core.competency_matrix_item_create_params(
                item_id=self.generated_id,
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
                interview_frequency=InterviewFrequencyEnum.OFTEN,
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
                    self.factory.core.existing_external_resource_attachment(
                        resource_id=2,
                        context_ru="контекст ресурса 2",
                        context_en="resource context 2",
                    ),
                    self.factory.core.new_external_resource_attachment(
                        resource_id=ANY,
                        name_ru="ресурс 1",
                        name_en="resource 1",
                        url="http://example.com",
                        context_ru="контекст ресурса 3",
                        context_en="resource context 3",
                    ),
                ],
            ),
            suggested_by_username="test",
        )
        assert response.status_code == codes.CREATED, response.json()
        assert response.json() == {
            "id": self.factory.core.hex_id(1),
            "slug": "question-1",
            "question": "question 1",
            "answer": "answer 1",
            "interviewAnswerExplanation": "interview answer explanation 1",
            "subsectionId": self.factory.core.hex_id(1),
            "sheetKey": "python",
            "sheet": "Python",
            "grade": "Junior",
            "interviewFrequency": "often",
            "section": "Basics",
            "subsection": "Functions",
            "publishStatus": PublishStatusEnum.DRAFT.value,
            "suggestedByUsername": "test",
            "translations": {
                "ru": {
                    "question": "вопрос 1",
                    "answer": "ответ 1",
                    "interviewAnswerExplanation": "объяснение ответа 1",
                },
                "en": {
                    "question": "question 1",
                    "answer": "answer 1",
                    "interviewAnswerExplanation": "interview answer explanation 1",
                },
            },
            "resources": [
                {
                    "id": ANY,
                    "name": "resource 1",
                    "url": "http://example.com",
                    "context": "resource context 1",
                    "translations": {
                        "ru": {"name": "ресурс 1", "context": "контекст ресурса 1"},
                        "en": {"name": "resource 1", "context": "resource context 1"},
                    },
                },
            ],
        }

    def test_create_item_uses_subsection_id_structure_reference(self) -> None:
        self.use_case.create_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            question_ru="вопрос 1",
            question_en="question 1",
            sheet_key="python",
            sheet_ru="Питон",
            sheet_en="Python",
            section_ru="Основы",
            section_en="Basics",
            subsection_ru="Функции",
            subsection_en="Functions",
            publish_status=PublishStatusEnum.DRAFT,
        )

        response = self.api.post_create_item(
            data={
                "slug": "question-1",
                "subsectionId": self.factory.core.hex_id(3),
                "grade": "Junior",
                "interviewFrequency": "often",
                "publishStatus": "Draft",
                "translations": {
                    "ru": {
                        "question": "вопрос 1",
                        "answer": "ответ 1",
                        "interviewAnswerExplanation": "объяснение ответа 1",
                    },
                    "en": {
                        "question": "question 1",
                        "answer": "answer 1",
                        "interviewAnswerExplanation": "interview answer explanation 1",
                    },
                },
                "resources": [],
            },
            language="en",
        )

        assert response.status_code == codes.CREATED, response.json()
        params = self.use_case.create_item.call_args.kwargs["params"]
        assert params.subsection_id == self.factory.core.hex_id(3)

    def test_create_item_rejects_resource_attachment_with_resource_id_and_resource(self) -> None:
        data = self.factory.api.competency_matrix_item_request(
            resources=[
                {
                    "resourceId": self.factory.core.hex_id(1),
                    "resource": {
                        "url": "http://example.com",
                        "translations": {
                            "ru": {"name": "ресурс 1"},
                            "en": {"name": "resource 1"},
                        },
                    },
                    "translations": {
                        "ru": {"context": "контекст ресурса"},
                        "en": {"context": "resource context"},
                    },
                },
            ],
        )
        response = self.api.post_create_item(data=data)
        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_requires_existing_resource_context_translations(self) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(
                resources=[{"resourceId": self.factory.core.hex_id(1)}],
            ),
        )
        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_requires_new_resource_context_translations(self) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(
                resources=[
                    {
                        "resource": {
                            "url": "http://example.com",
                            "translations": {
                                "ru": {"name": "ресурс 1"},
                                "en": {"name": "resource 1"},
                            },
                        },
                    },
                ],
            ),
        )
        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_rejects_legacy_interview_answer_field(self) -> None:
        data = self.factory.api.competency_matrix_item_request()
        translations = data["translations"]
        assert isinstance(translations, dict)
        legacy_parts = ("interview", "expected", "answer")
        legacy_field = legacy_parts[0] + "".join(part.title() for part in legacy_parts[1:])
        for language in ("ru", "en"):
            translation = translations[language]
            assert isinstance(translation, dict)
            translation[legacy_field] = translation.pop("interviewAnswerExplanation")

        response = self.api.post_create_item(data=data)

        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    @pytest.mark.parametrize("slug", ["", "   ", "Question One", "question_one"])
    def test_create_item_rejects_blank_or_invalid_slug(self, slug: str) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(slug=slug),
        )

        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_rejects_whitespace_question_translation(self) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(question_en="   "),
        )

        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_rejects_invalid_new_resource_url(self) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(
                resources=[
                    self.factory.api.new_matrix_resource_attachment_request(
                        url="file:///tmp/resource",
                    ),
                ],
            ),
        )

        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_rejects_too_long_matrix_text(self) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(
                answer_en="x" * 20_001,
                resources=[
                    self.factory.api.existing_matrix_resource_attachment_request(
                        context_en="x" * 20_001,
                    ),
                ],
            ),
        )

        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_requires_explicit_language(self) -> None:
        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(),
            language=None,
        )
        assert response.status_code == codes.BAD_REQUEST, response.json()
        self.use_case.create_item.assert_not_called()

    def test_create_item_allows_incomplete_draft_with_minimum_required_fields(self) -> None:
        self.use_case.create_item.return_value = self.factory.core.competency_matrix_item(
            item_id=1,
            slug="partial-question",
            question_ru="частичный вопрос",
            question_en="partial question",
            publish_status=PublishStatusEnum.DRAFT,
            grade=None,
            interview_frequency=None,
            answer_ru="",
            answer_en="",
            interview_answer_explanation_ru="",
            interview_answer_explanation_en="",
            sheet_key="python",
            sheet_ru="",
            sheet_en="",
            section_ru="",
            section_en="",
            subsection_ru="",
            subsection_en="",
        )

        response = self.api.post_create_item(
            data=self.factory.api.competency_matrix_item_request(
                slug="partial-question",
                sheet_key="python",
                question_ru="частичный вопрос",
                question_en="partial question",
                answer_ru="",
                answer_en="",
                interview_answer_explanation_ru="",
                interview_answer_explanation_en="",
                sheet_ru="",
                sheet_en="",
                grade=None,
                interview_frequency=None,
                section_ru="",
                section_en="",
                subsection_ru="",
                subsection_en="",
                publish_status="Draft",
            ),
            language="en",
        )

        assert response.status_code == codes.CREATED, response.content
        self.use_case.create_item.assert_called_once_with(
            params=self.factory.core.competency_matrix_item_create_params(
                item_id=self.generated_id,
                slug="partial-question",
                sheet_key="python",
                question_ru="частичный вопрос",
                question_en="partial question",
                answer_ru="",
                answer_en="",
                interview_answer_explanation_ru="",
                interview_answer_explanation_en="",
                sheet_ru="",
                sheet_en="",
                grade=None,
                interview_frequency=None,
                section_ru="",
                section_en="",
                subsection_ru="",
                subsection_en="",
                publish_status=PublishStatusEnum.DRAFT,
            ),
            suggested_by_username="test",
        )
