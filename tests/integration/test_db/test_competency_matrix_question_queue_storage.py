from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.competency_matrix.enums import GradeEnum
from core.competency_matrix.exceptions import QueuedCompetencyMatrixQuestionNotFoundError
from core.competency_matrix.schemas import (
    CompetencyMatrixQuestionFingerprint,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestionsCreateParams,
)
from core.enums import PublishStatusEnum
from infra.postgresql.storages.competency_matrix import CompetencyMatrixDatabaseStorage
from tests.test_cases import StorageTestCase


class TestCompetencyMatrixQuestionQueueStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.storage = CompetencyMatrixDatabaseStorage(session=session)

    async def test_create_and_list_queued_questions_in_fifo_order(self) -> None:
        first_created_at = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
        second_created_at = datetime(2026, 6, 7, 12, 1, tzinfo=UTC)
        third_created_at = datetime(2026, 6, 7, 12, 2, tzinfo=UTC)
        await self.storage_helper.create_queued_matrix_questions(
            questions=[
                QueuedCompetencyMatrixQuestion(
                    id=self.factory.core.hex_id(2),
                    question="Earliest",
                    grade=GradeEnum.JUNIOR,
                    sheet="Python",
                    section="Core",
                    subsection="Syntax",
                    suggested_by_username="anon",
                    created_at=first_created_at,
                    claim=None,
                ),
                QueuedCompetencyMatrixQuestion(
                    id=self.factory.core.hex_id(1),
                    question="Middle",
                    grade=None,
                    sheet=None,
                    section=None,
                    subsection=None,
                    suggested_by_username="alice",
                    created_at=second_created_at,
                    claim=None,
                ),
                QueuedCompetencyMatrixQuestion(
                    id=self.factory.core.hex_id(3),
                    question="Latest",
                    grade=None,
                    sheet=None,
                    section=None,
                    subsection=None,
                    suggested_by_username="owner",
                    created_at=third_created_at,
                    claim=None,
                ),
            ],
        )

        questions = await self.storage.list_queued_questions()

        assert [question.id for question in questions] == [
            self.factory.core.hex_id(2),
            self.factory.core.hex_id(1),
            self.factory.core.hex_id(3),
        ]

    async def test_create_queued_question_returns_persisted_question(self) -> None:
        question = await self.storage.create_queued_question(
            params=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                sheet="python",
                grade=GradeEnum.JUNIOR,
            ),
            suggested_by_username="anon",
        )

        self.asserts.hex_id(question.id)
        assert question.question == "What is PEP 8?"
        assert question.grade == GradeEnum.JUNIOR
        assert question.sheet == "python"
        assert question.section is None
        assert question.subsection is None
        assert question.suggested_by_username == "anon"

    async def test_question_suggestion_exists_matches_queue_case_and_whitespace(self) -> None:
        await self.storage.create_queued_question(
            params=QueuedCompetencyMatrixQuestionCreateParams(
                question="  STRA\u00dfe   questions  ",
                sheet="python",
                grade=None,
            ),
            suggested_by_username="anon",
        )

        exists = await self.storage.question_suggestion_exists(
            fingerprint=CompetencyMatrixQuestionFingerprint(value="strasse questions"),
            sheet_key="python",
        )

        assert exists is True

    @pytest.mark.parametrize(
        ("question_field", "publish_status"),
        [
            ("question_ru", PublishStatusEnum.DRAFT),
            ("question_en", PublishStatusEnum.PUBLISHED),
        ],
    )
    async def test_question_suggestion_exists_matches_matrix_languages_and_statuses(
        self,
        question_field: str,
        publish_status: PublishStatusEnum,
    ) -> None:
        item = self.factory.core.competency_matrix_item(
            item_id=50,
            publish_status=publish_status,
            question_ru="Что такое GIL?",
            question_en="What is the GIL?",
        )
        await self.storage_helper.create_competency_matrix_items(items=[item])
        question = getattr(item, question_field)

        exists = await self.storage.question_suggestion_exists(
            fingerprint=CompetencyMatrixQuestionFingerprint.from_question(question=question),
            sheet_key=item.sheet_key,
        )

        assert exists is True

    async def test_question_suggestion_exists_returns_false_for_new_question(self) -> None:
        exists = await self.storage.question_suggestion_exists(
            fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
                question="How does structured concurrency work?",
            ),
            sheet_key="python",
        )

        assert exists is False

    async def test_question_suggestion_exists_ignores_same_question_in_other_sheet(self) -> None:
        await self.storage.create_queued_question(
            params=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is a function?",
                sheet="python",
                grade=None,
            ),
            suggested_by_username="anon",
        )
        item = self.factory.core.competency_matrix_item(
            item_id=51,
            sheet_id=51,
            section_id=51,
            subsection_id=51,
            sheet_key="javascript",
            sheet="JavaScript",
            question_ru="Что такое функция?",
            question_en="What is a function?",
        )
        await self.storage_helper.create_competency_matrix_items(items=[item])

        exists = await self.storage.question_suggestion_exists(
            fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
                question="What is a function?",
            ),
            sheet_key="go",
        )

        assert exists is False

    async def test_create_queued_questions_returns_persisted_questions_in_input_order(self) -> None:
        questions = await self.storage.create_queued_questions(
            params=QueuedCompetencyMatrixQuestionsCreateParams(
                questions=[
                    QueuedCompetencyMatrixQuestionCreateParams(
                        question="What is PEP 8?",
                        sheet="python",
                        grade=None,
                    ),
                    QueuedCompetencyMatrixQuestionCreateParams(
                        question="How does mypy help?",
                        sheet="python",
                        grade=GradeEnum.MIDDLE,
                    ),
                ],
            ),
            suggested_by_username="importer",
        )

        assert [question.question for question in questions] == [
            "What is PEP 8?",
            "How does mypy help?",
        ]
        assert [question.sheet for question in questions] == ["python", "python"]
        assert [question.grade for question in questions] == [None, GradeEnum.MIDDLE]
        assert [question.section for question in questions] == [None, None]
        assert [question.subsection for question in questions] == [None, None]
        self.asserts.hex_id(questions.values[0].id)
        self.asserts.hex_id(questions.values[1].id)
        assert questions.values[0].id != questions.values[1].id
        assert questions.values[0].created_at == questions.values[1].created_at
        assert [question.suggested_by_username for question in questions] == [
            "importer",
            "importer",
        ]

    async def test_list_queued_questions_breaks_fifo_ties_by_id(self) -> None:
        created_at = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
        await self.storage_helper.create_queued_matrix_questions(
            questions=[
                QueuedCompetencyMatrixQuestion(
                    id=self.factory.core.hex_id(2),
                    question="Second",
                    grade=None,
                    sheet=None,
                    section=None,
                    subsection=None,
                    suggested_by_username="anon",
                    created_at=created_at,
                    claim=None,
                ),
                QueuedCompetencyMatrixQuestion(
                    id=self.factory.core.hex_id(1),
                    question="First",
                    grade=None,
                    sheet=None,
                    section=None,
                    subsection=None,
                    suggested_by_username="anon",
                    created_at=created_at,
                    claim=None,
                ),
            ],
        )

        questions = await self.storage.list_queued_questions()

        assert [question.id for question in questions] == [
            self.factory.core.hex_id(1),
            self.factory.core.hex_id(2),
        ]

    async def test_get_queued_question_not_found(self) -> None:
        with pytest.raises(QueuedCompetencyMatrixQuestionNotFoundError):
            await self.storage.get_queued_question(
                question_id=self.factory.core.hex_id(404),
                lock=False,
            )

    async def test_delete_queued_question_removes_pending_entry(self) -> None:
        await self.storage_helper.create_queued_matrix_questions(
            questions=[
                QueuedCompetencyMatrixQuestion(
                    id=self.factory.core.hex_id(7),
                    question="What is PEP 8?",
                    grade=None,
                    sheet=None,
                    section=None,
                    subsection=None,
                    suggested_by_username="anon",
                    created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
                    claim=None,
                ),
            ],
        )

        await self.storage.delete_queued_question(question_id=self.factory.core.hex_id(7))

        questions = await self.storage.list_queued_questions()
        assert questions.values == []
