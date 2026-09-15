import pytest_asyncio
from httpx import codes

from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import CompetencyMatrixItemFilters
from core.enums import PublishStatusEnum
from tests.test_cases import ApiTestCase


class TestItemsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_list_not_correct_sheet_key(self) -> None:
        self.use_case.list_items.return_value = self.factory.core.competency_matrix_items(
            values=[
                self.factory.core.competency_matrix_item(
                    item_id=1,
                    question_ru="Как написать свою функцию?",
                    question_en="How to write a function?",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    grade=GradeEnum.JUNIOR,
                    subsection_ru="Функции",
                    subsection_en="Functions",
                    section_ru="Основы",
                    section_en="Basics",
                    sheet_key="python",
                    sheet_ru="Питон",
                    sheet_en="Python",
                    interview_frequency=InterviewFrequencyEnum.RARELY,
                ),
            ],
        )
        response = self.api.get_competency_matrix_items(sheet_key="java", language="en")
        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "sheetKey": "java",
            "sheet": "",
            "sections": [],
        }
        self.use_case.list_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(sheet_key="java", only_published=True),
        )

    def test_list(self) -> None:
        self.use_case.list_items.return_value = self.factory.core.competency_matrix_items(
            values=[
                self.factory.core.competency_matrix_item(
                    item_id=1,
                    question_ru="Как написать свою функцию?",
                    question_en="How to write a function?",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    grade=GradeEnum.JUNIOR,
                    subsection_ru="Функции",
                    subsection_en="Functions",
                    section_ru="Основы",
                    section_en="Basics",
                    sheet_key="python",
                    sheet_ru="Питон",
                    sheet_en="Python",
                    interview_frequency=InterviewFrequencyEnum.RARELY,
                ),
            ],
        )
        response = self.api.get_competency_matrix_items(sheet_key="python", language="en")
        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "sheetKey": "python",
            "sheet": "Python",
            "sections": [
                {
                    "section": "Basics",
                    "subsections": [
                        {
                            "subsection": "Functions",
                            "grades": [
                                {
                                    "grade": "Junior",
                                    "items": [
                                        {
                                            "slug": "how-to-write-a-function",
                                            "question": "How to write a function?",
                                            "interviewFrequency": "rarely",
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        self.use_case.list_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=True),
        )

    def test_admin_list_requires_only_published(self) -> None:
        response = self.api.get_admin_competency_matrix_items(
            sheet_key="python",
            only_published=None,
        )
        assert response.status_code == codes.BAD_REQUEST
        self.use_case.list_items.assert_not_called()

    def test_list_requires_explicit_language(self) -> None:
        response = self.api.get_competency_matrix_items(sheet_key="python", language=None)
        assert response.status_code == codes.BAD_REQUEST
        self.use_case.list_items.assert_not_called()

    def test_moderator_can_request_all_items(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.use_case.list_items.return_value = self.factory.core.competency_matrix_items(
            values=[],
        )

        response = self.api.get_admin_competency_matrix_items(
            sheet_key="python",
            only_published=False,
        )

        assert response.status_code == codes.OK, response.content
        self.use_case.list_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(sheet_key="python", only_published=False),
        )
