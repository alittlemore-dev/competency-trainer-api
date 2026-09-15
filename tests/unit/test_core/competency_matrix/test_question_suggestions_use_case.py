from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest

from core.competency_matrix.enums import GradeEnum, QuestionQueueImportIssueCodeEnum
from core.competency_matrix.exceptions import (
    MatrixQuestionClaimConflictError,
    QuestionSuggestionAlreadyExistsError,
    QuestionSuggestionSheetUnavailableError,
    QueuedCompetencyMatrixQuestionNotFoundError,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixQuestionFingerprint,
    MatrixQuestionClaimSummary,
    QuestionQueueImportPreview,
    QuestionQueueImportPreviewRow,
    QuestionSuggestionCreateParams,
    QuestionSuggestionLimitParams,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateItemParams,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestions,
    QueuedCompetencyMatrixQuestionsCreateParams,
)
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from tests.test_cases import TestCase


class TestQuestionSuggestionsUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=CompetencyMatrixStorage)
        self.storage.get_item_structure_by_subsection_id.return_value = (
            self.factory.core.competency_matrix_item_structure()
        )
        self.question_suggestion_limiter = Mock(spec=QuestionSuggestionLimiter)
        self.storage.list_sheets.return_value = self.factory.core.sheets(values=["Python"])
        self.storage.question_suggestion_exists.return_value = False
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=self.question_suggestion_limiter,
        )

    def test_question_fingerprint_normalizes_whitespace_and_unicode_case(self) -> None:
        assert (
            CompetencyMatrixQuestionFingerprint.from_question(
                question="  STRA\u00dfe\n\tquestions  ",
            ).value
            == "strasse questions"
        )

    async def test_suggest_question_checks_duplicate_before_quota_and_creation(self) -> None:
        now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
        self.storage.create_queued_question.return_value = QueuedCompetencyMatrixQuestion(
            id=self.factory.core.hex_id(1),
            question="What is PEP 8?",
            grade=None,
            sheet=None,
            section=None,
            subsection=None,
            suggested_by_username="anon",
            created_at=now,
            claim=None,
        )

        params = QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                grade=None,
                sheet="python",
            ),
            limit=QuestionSuggestionLimitParams(
                client_identifier="203.0.113.10",
                now=now,
            ),
            suggested_by_username="anon",
            reject_duplicates=True,
            validate_public_sheet=True,
        )
        calls = Mock()
        calls.attach_mock(self.storage.list_sheets, "sheets")
        calls.attach_mock(self.storage.question_suggestion_exists, "exists")
        calls.attach_mock(self.question_suggestion_limiter.check_create_allowed, "quota")
        calls.attach_mock(self.storage.create_queued_question, "create")
        created_question = await self.use_case.suggest_question(params=params)

        assert created_question.question == "What is PEP 8?"
        fingerprint = CompetencyMatrixQuestionFingerprint(value="what is pep 8?")
        self.storage.question_suggestion_exists.assert_called_once_with(
            fingerprint=fingerprint,
            sheet_key="python",
        )
        self.question_suggestion_limiter.check_create_allowed.assert_called_once_with(
            params=params.limit,
        )
        self.storage.create_queued_question.assert_called_once_with(
            params=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                grade=None,
                sheet="python",
            ),
            suggested_by_username="anon",
        )
        assert calls.mock_calls == [
            call.sheets(),
            call.exists(fingerprint=fingerprint, sheet_key="python"),
            call.quota(params=params.limit),
            call.create(
                params=params.question,
                suggested_by_username="anon",
            ),
        ]

    async def test_suggest_question_rejects_duplicate_without_consuming_quota(self) -> None:
        self.storage.question_suggestion_exists.return_value = True
        params = QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question=" What   is PEP 8? ",
                grade=None,
                sheet="python",
            ),
            limit=QuestionSuggestionLimitParams(
                client_identifier="203.0.113.10",
                now=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
            ),
            suggested_by_username="anon",
            reject_duplicates=True,
            validate_public_sheet=True,
        )

        with pytest.raises(QuestionSuggestionAlreadyExistsError):
            await self.use_case.suggest_question(params=params)

        fingerprint = CompetencyMatrixQuestionFingerprint(value="what is pep 8?")
        self.storage.question_suggestion_exists.assert_called_once_with(
            fingerprint=fingerprint,
            sheet_key="python",
        )
        self.question_suggestion_limiter.check_create_allowed.assert_not_called()
        self.storage.create_queued_question.assert_not_called()

    async def test_suggest_question_rejects_non_public_sheet_before_duplicate_and_quota(
        self,
    ) -> None:
        params = QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                grade=None,
                sheet="javascript",
            ),
            limit=QuestionSuggestionLimitParams(
                client_identifier="203.0.113.10",
                now=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
            ),
            suggested_by_username="anon",
            reject_duplicates=True,
            validate_public_sheet=True,
        )

        with pytest.raises(QuestionSuggestionSheetUnavailableError):
            await self.use_case.suggest_question(params=params)

        self.storage.question_suggestion_exists.assert_not_called()
        self.question_suggestion_limiter.check_create_allowed.assert_not_called()
        self.storage.create_queued_question.assert_not_called()

    async def test_suggest_question_skips_quota_limiter_when_limit_is_absent(self) -> None:
        now = datetime(2026, 6, 7, 12, 0, tzinfo=UTC)
        queued_question = QueuedCompetencyMatrixQuestion(
            id=self.factory.core.hex_id(1),
            question="What is PEP 8?",
            grade=None,
            sheet=None,
            section=None,
            subsection=None,
            suggested_by_username="alice",
            created_at=now,
            claim=None,
        )
        params = QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                grade=None,
                sheet=None,
            ),
            limit=None,
            suggested_by_username="alice",
            reject_duplicates=False,
            validate_public_sheet=False,
        )
        self.storage.create_queued_question.return_value = queued_question

        created_question = await self.use_case.suggest_question(params=params)

        assert created_question == queued_question
        self.storage.list_sheets.assert_not_called()
        self.question_suggestion_limiter.check_create_allowed.assert_not_called()
        self.storage.question_suggestion_exists.assert_not_called()
        self.storage.create_queued_question.assert_called_once_with(
            params=params.question,
            suggested_by_username="alice",
        )

    async def test_import_queued_questions_creates_questions_without_quota_limiter(self) -> None:
        params = QueuedCompetencyMatrixQuestionsCreateParams(
            questions=[
                QueuedCompetencyMatrixQuestionCreateParams(
                    question="What is PEP 8?",
                    grade=None,
                    sheet="python",
                ),
                QueuedCompetencyMatrixQuestionCreateParams(
                    question="How does mypy help?",
                    grade=GradeEnum.MIDDLE,
                    sheet="python",
                ),
            ],
        )
        queued_questions = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=1,
                    question="What is PEP 8?",
                    created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
                ),
                self.factory.core.queued_competency_matrix_question(
                    question_id=2,
                    question="How does mypy help?",
                    created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
                ),
            ],
        )
        self.storage.create_queued_questions.return_value = queued_questions

        created_questions = await self.use_case.import_queued_questions(
            params=params,
            suggested_by_username="importer",
        )

        assert created_questions == queued_questions
        self.question_suggestion_limiter.check_create_allowed.assert_not_called()
        self.storage.create_queued_questions.assert_called_once_with(
            params=params,
            suggested_by_username="importer",
        )

    async def test_preview_import_marks_file_and_queue_duplicates(self) -> None:
        first_params = QueuedCompetencyMatrixQuestionCreateParams(
            question="What   is PEP 8?",
            grade=None,
            sheet=None,
        )
        second_params = QueuedCompetencyMatrixQuestionCreateParams(
            question="what is pep 8?",
            grade=None,
            sheet=None,
        )
        preview = QuestionQueueImportPreview(
            rows=[
                QuestionQueueImportPreviewRow(
                    row_number=1,
                    question=first_params.question,
                    sheet="",
                    grade="",
                    params=first_params,
                    issues=(),
                ),
                QuestionQueueImportPreviewRow(
                    row_number=2,
                    question=second_params.question,
                    sheet="",
                    grade="",
                    params=second_params,
                    issues=(),
                ),
            ],
        )
        self.storage.list_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=10,
                    question=" WHAT IS PEP 8? ",
                    created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
                ),
            ],
        )

        result = await self.use_case.preview_queued_questions_import(preview=preview)

        assert [issue.code for issue in result.rows[0].issues] == [
            QuestionQueueImportIssueCodeEnum.DUPLICATE_IN_QUEUE,
        ]
        assert [issue.code for issue in result.rows[1].issues] == [
            QuestionQueueImportIssueCodeEnum.DUPLICATE_IN_FILE,
            QuestionQueueImportIssueCodeEnum.DUPLICATE_IN_QUEUE,
        ]
        assert result.rows[0].selected_by_default is False
        assert result.rows[1].selected_by_default is False

    async def test_create_item_from_queue_creates_item_then_removes_queue_entry(self) -> None:
        current_datetime = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
        queued_question = QueuedCompetencyMatrixQuestion(
            id=self.factory.core.hex_id(7),
            question="What is PEP 8?",
            grade=GradeEnum.JUNIOR,
            sheet="Python",
            section="Core",
            subsection="Style",
            suggested_by_username="alice",
            created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
            claim=None,
        )
        params = self.factory.core.competency_matrix_item_create_params(
            item_id=10,
            question_ru="Что такое PEP 8?",
            question_en="What is PEP 8?",
            grade=GradeEnum.JUNIOR,
            sheet="Python",
            section="Core",
            subsection="Style",
        )
        created_item = self.factory.core.competency_matrix_item(
            item_id=10,
            question_en="What is PEP 8?",
        )
        self.storage.get_queued_question.return_value = queued_question
        self.storage.create_competency_matrix_item.return_value = created_item

        item = await self.use_case.create_item_from_queue(
            params=QueuedCompetencyMatrixQuestionCreateItemParams(
                queued_question_id=self.factory.core.hex_id(7),
                item=params,
            ),
            current_datetime=current_datetime,
        )

        assert item == created_item
        self.storage.get_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(7),
            lock=True,
        )
        self.storage.create_competency_matrix_item.assert_called_once()
        created_item = self.storage.create_competency_matrix_item.call_args.kwargs["item"]
        assert created_item.suggested_by_username == "alice"
        self.storage.delete_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(7)
        )
        create_item_call_index = next(
            index
            for index, method_call in enumerate(self.storage.method_calls)
            if method_call[0] == "create_competency_matrix_item"
        )
        delete_queue_call_index = self.storage.method_calls.index(
            call.delete_queued_question(question_id=self.factory.core.hex_id(7)),
        )
        assert create_item_call_index < delete_queue_call_index

    async def test_create_item_from_queue_does_not_delete_missing_queue_entry(
        self,
    ) -> None:
        self.storage.get_queued_question.side_effect = QueuedCompetencyMatrixQuestionNotFoundError

        with pytest.raises(QueuedCompetencyMatrixQuestionNotFoundError):
            await self.use_case.create_item_from_queue(
                params=QueuedCompetencyMatrixQuestionCreateItemParams(
                    queued_question_id=self.factory.core.hex_id(404),
                    item=self.factory.core.competency_matrix_item_create_params(item_id=1),
                ),
                current_datetime=datetime(2026, 7, 14, 12, 0, tzinfo=UTC),
            )

        self.storage.create_competency_matrix_item.assert_not_called()
        self.storage.delete_queued_question.assert_not_called()
        self.storage.get_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(404),
            lock=True,
        )

    async def test_create_item_from_queue_rejects_active_agent_claim(self) -> None:
        current_datetime = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
        self.storage.get_queued_question.return_value = (
            self.factory.core.queued_competency_matrix_question(
                question_id=7,
                claim=MatrixQuestionClaimSummary(
                    id=self.factory.core.hex_id(8),
                    agent_client_id=self.factory.core.hex_id(9),
                    agent_client_name="codex-desktop",
                    claimed_at=datetime(2026, 7, 14, 11, 0, tzinfo=UTC),
                    expires_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC),
                ),
            )
        )

        with pytest.raises(MatrixQuestionClaimConflictError):
            await self.use_case.create_item_from_queue(
                params=QueuedCompetencyMatrixQuestionCreateItemParams(
                    queued_question_id=self.factory.core.hex_id(7),
                    item=self.factory.core.competency_matrix_item_create_params(item_id=1),
                ),
                current_datetime=current_datetime,
            )

        self.storage.create_competency_matrix_item.assert_not_called()
        self.storage.delete_queued_question.assert_not_called()
        self.storage.get_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(7),
            lock=True,
        )

    async def test_delete_queued_question_rejects_active_agent_claim(self) -> None:
        current_datetime = datetime(2026, 7, 14, 12, 0, tzinfo=UTC)
        self.storage.get_queued_question.return_value = (
            self.factory.core.queued_competency_matrix_question(
                question_id=7,
                claim=MatrixQuestionClaimSummary(
                    id=self.factory.core.hex_id(8),
                    agent_client_id=self.factory.core.hex_id(9),
                    agent_client_name="codex-desktop",
                    claimed_at=datetime(2026, 7, 14, 11, 0, tzinfo=UTC),
                    expires_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC),
                ),
            )
        )

        with pytest.raises(MatrixQuestionClaimConflictError):
            await self.use_case.delete_queued_question(
                question_id=self.factory.core.hex_id(7),
                current_datetime=current_datetime,
            )

        self.storage.delete_queued_question.assert_not_called()
        self.storage.get_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(7),
            lock=True,
        )

    async def test_release_agent_claim_deletes_locked_claim(self) -> None:
        claim = MatrixQuestionClaimSummary(
            id=self.factory.core.hex_id(8),
            agent_client_id=self.factory.core.hex_id(9),
            agent_client_name="codex-desktop",
            claimed_at=datetime(2026, 7, 14, 11, 0, tzinfo=UTC),
            expires_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC),
        )
        self.storage.get_queued_question.return_value = (
            self.factory.core.queued_competency_matrix_question(question_id=7, claim=claim)
        )

        await self.use_case.release_queued_question_agent_claim(
            question_id=self.factory.core.hex_id(7)
        )

        self.storage.delete_question_claim.assert_called_once_with(claim_id=claim.id)
        self.storage.get_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(7),
            lock=True,
        )
