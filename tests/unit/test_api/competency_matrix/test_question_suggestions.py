from datetime import UTC, datetime
from io import BytesIO
from typing import cast
from unittest.mock import ANY, Mock

import pytest_asyncio
from httpx import codes
from litestar import Request
from litestar.datastructures import State
from openpyxl import Workbook

from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.auth.types import Token
from core.competency_matrix.enums import (
    GradeEnum,
    QuestionQueueImportIssueCodeEnum,
    QuestionQueueImportIssueSeverityEnum,
)
from core.competency_matrix.exceptions import (
    MatrixQuestionClaimConflictError,
    QuestionSuggestionAlreadyExistsError,
    QuestionSuggestionQuotaExceededError,
    QuestionSuggestionSheetUnavailableError,
    QueuedCompetencyMatrixQuestionNotFoundError,
)
from core.competency_matrix.schemas import (
    MatrixQuestionClaimSummary,
    QuestionQueueImportPreview,
    QuestionQueueImportPreviewIssue,
    QuestionQueueImportPreviewRow,
    QuestionSuggestionCreateParams,
    QueuedCompetencyMatrixQuestionCreateItemParams,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestions,
)
from core.enums import PublishStatusEnum
from entrypoints.litestar.api.competency_matrix.dependencies import (
    provide_question_suggestion_limit_params,
)
from entrypoints.litestar.api.competency_matrix.schemas import (
    QueuedQuestionsImportConfirmationRequestSchema,
    QueuedQuestionsImportPreviewRequestSchema,
)
from entrypoints.litestar.api.schemas import CamelCaseSchema
from tests.test_cases import ApiTestCase
from tests.unit.mocks.providers.auth import test_current_datetime


class TestQuestionSuggestionsApi(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_import_request_schemas_are_pydantic_api_schemas(self) -> None:
        assert issubclass(QueuedQuestionsImportPreviewRequestSchema, CamelCaseSchema)
        assert issubclass(QueuedQuestionsImportConfirmationRequestSchema, CamelCaseSchema)

    def test_anonymous_user_can_suggest_question(self) -> None:
        response = self.no_auth_api.post_question_suggestion(
            question="  What is PEP 8?  ",
            sheet="python",
        )

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        self.use_case.suggest_question.assert_called_once_with(
            params=ANY,
        )
        call_params = self.use_case.suggest_question.call_args.kwargs["params"]
        assert isinstance(call_params, QuestionSuggestionCreateParams)
        assert call_params.question == QueuedCompetencyMatrixQuestionCreateParams(
            question="What is PEP 8?",
            sheet="python",
            grade=None,
        )
        assert call_params.limit is not None
        assert call_params.suggested_by_username == "anon"
        assert call_params.reject_duplicates is True
        assert call_params.validate_public_sheet is True
        assert call_params.limit.client_identifier != ""
        assert call_params.limit.now.tzinfo is not None

    def test_anonymous_user_cannot_suggest_question_without_sheet_key(self) -> None:
        response = self.no_auth_api.client.post(
            "/api/competency-matrix/question-suggestions",
            json={"question": "What is PEP 8?"},
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.suggest_question.assert_not_called()

    def test_anonymous_suggestion_uses_forwarded_client_identifier(self) -> None:
        response = self.no_auth_api.post_question_suggestion(
            question="What is PEP 8?",
            headers={"X-Forwarded-For": "203.0.113.10, 10.0.0.2"},
        )

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        self.use_case.suggest_question.assert_called_once_with(
            params=ANY,
        )
        call_params = self.use_case.suggest_question.call_args.kwargs["params"]
        assert call_params == QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                sheet="python",
                grade=None,
            ),
            limit=call_params.limit,
            suggested_by_username="anon",
            reject_duplicates=True,
            validate_public_sheet=True,
        )
        assert call_params.limit is not None
        assert call_params.limit.client_identifier == "203.0.113.10"
        assert call_params.limit.now.tzinfo is not None
        assert call_params.suggested_by_username == "anon"

    def test_authenticated_public_suggestion_uses_username_and_keeps_ip_quota(self) -> None:
        response = self.api.post_question_suggestion(question="What is PEP 8?")

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        call_params = self.use_case.suggest_question.call_args.kwargs["params"]
        assert call_params.suggested_by_username == "test"
        assert call_params.limit is not None

    def test_question_suggestion_limit_dependency_uses_forwarded_client_identifier(self) -> None:
        request = cast(
            "Request[JwtUser, Token | None, State]",
            Mock(
                headers={"x-forwarded-for": "203.0.113.10, 10.0.0.2"},
                client=Mock(host="198.51.100.4"),
            ),
        )

        params = provide_question_suggestion_limit_params(request=request)

        assert params.client_identifier == "203.0.113.10"
        assert params.now.tzinfo is not None

    def test_suggest_question_rejects_empty_question(self) -> None:
        response = self.no_auth_api.post_question_suggestion(question="")

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.suggest_question.assert_not_called()

    def test_suggest_question_rejects_blank_question(self) -> None:
        response = self.no_auth_api.post_question_suggestion(question="   ")

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.suggest_question.assert_not_called()

    def test_suggest_question_returns_429_when_daily_quota_is_exhausted(self) -> None:
        self.use_case.suggest_question.side_effect = QuestionSuggestionQuotaExceededError

        response = self.no_auth_api.post_question_suggestion(question="What is PEP 8?")

        self.asserts.error_message(
            response=response,
            expected_status=codes.TOO_MANY_REQUESTS,
            expected_message="Question suggestion daily quota exceeded",
        )

    def test_suggest_question_returns_409_when_question_already_exists(self) -> None:
        self.use_case.suggest_question.side_effect = QuestionSuggestionAlreadyExistsError

        response = self.no_auth_api.post_question_suggestion(question="What is PEP 8?")

        self.asserts.error_message(
            response=response,
            expected_status=codes.CONFLICT,
            expected_message="Question already exists in the competency matrix or suggestion queue",
        )

    def test_suggest_question_returns_400_when_sheet_is_not_public(self) -> None:
        self.use_case.suggest_question.side_effect = QuestionSuggestionSheetUnavailableError

        response = self.no_auth_api.post_question_suggestion(
            question="What is PEP 8?",
            sheet="private-sheet",
        )

        self.asserts.error_message(
            response=response,
            expected_status=codes.BAD_REQUEST,
            expected_message="Selected competency matrix sheet is not publicly available",
        )

    def test_content_manager_can_list_queue_in_fifo_order(self) -> None:
        self.use_case.list_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=1,
                    question="First question",
                    created_at=datetime(2026, 6, 7, 12, 0, tzinfo=UTC),
                ),
                self.factory.core.queued_competency_matrix_question(
                    question_id=2,
                    question="Second question",
                    grade=GradeEnum.JUNIOR,
                    sheet="Python",
                    section="Core",
                    subsection="Syntax",
                    suggested_by_username="alice",
                    created_at=datetime(2026, 6, 7, 12, 1, tzinfo=UTC),
                ),
            ],
        )

        response = self.api.get_queued_matrix_questions()

        self.asserts.json_body(
            response=response,
            expected_status=codes.OK,
            expected_body={
                "questions": [
                    {
                        "id": self.factory.core.hex_id(1),
                        "question": "First question",
                        "grade": None,
                        "sheet": None,
                        "section": None,
                        "subsection": None,
                        "suggestedByUsername": "anon",
                        "createdAt": "2026-06-07T12:00:00+00:00",
                        "claim": None,
                    },
                    {
                        "id": self.factory.core.hex_id(2),
                        "question": "Second question",
                        "grade": "Junior",
                        "sheet": "Python",
                        "section": "Core",
                        "subsection": "Syntax",
                        "suggestedByUsername": "alice",
                        "createdAt": "2026-06-07T12:01:00+00:00",
                        "claim": None,
                    },
                ],
            },
        )
        self.use_case.list_queued_questions.assert_called_once_with(
            current_datetime=test_current_datetime
        )

    def test_regular_user_cannot_list_queue(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="user",
            role=RoleEnum.USER,
        )

        response = self.api.get_queued_matrix_questions()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
        self.use_case.list_queued_questions.assert_not_called()

    def test_queue_list_exposes_active_agent_claim(self) -> None:
        self.use_case.list_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=1,
                    created_at=datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
                    claim=MatrixQuestionClaimSummary(
                        id=self.factory.core.hex_id(2),
                        agent_client_id=self.factory.core.hex_id(3),
                        agent_client_name="codex-desktop",
                        claimed_at=datetime(2026, 7, 14, 11, 0, tzinfo=UTC),
                        expires_at=datetime(2026, 7, 14, 13, 0, tzinfo=UTC),
                    ),
                )
            ]
        )

        response = self.api.get_queued_matrix_questions()

        self.asserts.status(response=response, expected_status=codes.OK)
        claim = response.json()["questions"][0]["claim"]
        assert claim == {
            "id": self.factory.core.hex_id(2),
            "agentClientId": self.factory.core.hex_id(3),
            "agentClientName": "codex-desktop",
            "claimedAt": "2026-07-14T11:00:00+00:00",
            "expiresAt": "2026-07-14T13:00:00+00:00",
        }
        self.use_case.list_queued_questions.assert_called_once_with(
            current_datetime=test_current_datetime
        )

    def test_content_manager_can_create_queued_question(self) -> None:
        self.use_case.suggest_question.return_value = (
            self.factory.core.queued_competency_matrix_question(
                question_id=3,
                question="What is PEP 8?",
                suggested_by_username="test",
                created_at=datetime(2026, 6, 7, 12, 3, tzinfo=UTC),
            )
        )

        response = self.api.post_create_queued_matrix_question(question="  What is PEP 8?  ")

        self.asserts.json_body(
            response=response,
            expected_status=codes.CREATED,
            expected_body={
                "id": self.factory.core.hex_id(3),
                "question": "What is PEP 8?",
                "grade": None,
                "sheet": None,
                "section": None,
                "subsection": None,
                "suggestedByUsername": "test",
                "createdAt": "2026-06-07T12:03:00+00:00",
                "claim": None,
            },
        )
        self.use_case.suggest_question.assert_called_once_with(params=ANY)
        call_params = self.use_case.suggest_question.call_args.kwargs["params"]
        assert call_params == QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question="What is PEP 8?",
                sheet=None,
                grade=None,
            ),
            limit=None,
            suggested_by_username="test",
            reject_duplicates=False,
            validate_public_sheet=False,
        )

    def test_content_manager_can_import_txt_queued_questions(self) -> None:
        self.use_case.import_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=3,
                    question="What is PEP 8?",
                    suggested_by_username="test",
                    created_at=datetime(2026, 6, 7, 12, 3, tzinfo=UTC),
                ),
                self.factory.core.queued_competency_matrix_question(
                    question_id=4,
                    question="How does mypy help?",
                    suggested_by_username="test",
                    created_at=datetime(2026, 6, 7, 12, 3, tzinfo=UTC),
                ),
            ],
        )

        response = self.api.post_import_queued_matrix_questions(
            filename="questions.txt",
            content=b"What is PEP 8?\nHow does mypy help?",
            content_type="text/plain",
            selected_row_numbers=[1, 2],
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        body = response.json()
        assert body["questions"] == [
            {
                "id": self.factory.core.hex_id(3),
                "question": "What is PEP 8?",
                "grade": None,
                "sheet": None,
                "section": None,
                "subsection": None,
                "suggestedByUsername": "test",
                "createdAt": "2026-06-07T12:03:00+00:00",
                "claim": None,
            },
            {
                "id": self.factory.core.hex_id(4),
                "question": "How does mypy help?",
                "grade": None,
                "sheet": None,
                "section": None,
                "subsection": None,
                "suggestedByUsername": "test",
                "createdAt": "2026-06-07T12:03:00+00:00",
                "claim": None,
            },
        ]
        self.use_case.import_queued_questions.assert_called_once_with(
            params=ANY,
            suggested_by_username="test",
        )
        call_params = self.use_case.import_queued_questions.call_args.kwargs["params"]
        assert self.use_case.import_queued_questions.call_args.kwargs["suggested_by_username"] == (
            "test"
        )
        assert self.collections.pluck(items=call_params.questions, attr="question") == [
            "What is PEP 8?",
            "How does mypy help?",
        ]

    def test_content_manager_can_preview_valid_invalid_and_duplicate_rows(self) -> None:
        valid_params = QueuedCompetencyMatrixQuestionCreateParams(
            question="What is PEP 8?",
            grade=None,
            sheet="python",
        )
        self.use_case.preview_queued_questions_import.return_value = QuestionQueueImportPreview(
            rows=[
                QuestionQueueImportPreviewRow(
                    row_number=2,
                    question="What is PEP 8?",
                    sheet="python",
                    grade="",
                    params=valid_params,
                    issues=(
                        QuestionQueueImportPreviewIssue(
                            code=QuestionQueueImportIssueCodeEnum.DUPLICATE_IN_QUEUE,
                            severity=QuestionQueueImportIssueSeverityEnum.WARNING,
                            related_row_numbers=(),
                        ),
                    ),
                ),
                QuestionQueueImportPreviewRow(
                    row_number=3,
                    question="",
                    sheet="python",
                    grade="Lead",
                    params=None,
                    issues=(
                        QuestionQueueImportPreviewIssue(
                            code=QuestionQueueImportIssueCodeEnum.QUESTION_BLANK,
                            severity=QuestionQueueImportIssueSeverityEnum.ERROR,
                            related_row_numbers=(),
                        ),
                    ),
                ),
            ],
        )

        response = self.api.post_preview_queued_matrix_questions(
            filename="questions.csv",
            content=b"question,sheet,grade\nWhat is PEP 8?,python,\n,python,Lead",
            content_type="text/csv",
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "rows": [
                {
                    "rowNumber": 2,
                    "question": "What is PEP 8?",
                    "sheet": "python",
                    "grade": "",
                    "canImport": True,
                    "selectedByDefault": False,
                    "issues": [
                        {
                            "code": "duplicateInQueue",
                            "severity": "warning",
                            "relatedRowNumbers": [],
                        },
                    ],
                },
                {
                    "rowNumber": 3,
                    "question": "",
                    "sheet": "python",
                    "grade": "Lead",
                    "canImport": False,
                    "selectedByDefault": False,
                    "issues": [
                        {
                            "code": "questionBlank",
                            "severity": "error",
                            "relatedRowNumbers": [],
                        },
                    ],
                },
            ],
        }
        self.use_case.preview_queued_questions_import.assert_called_once_with(preview=ANY)

    def test_regular_user_cannot_preview_queued_questions(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="user",
            role=RoleEnum.USER,
        )

        response = self.api.post_preview_queued_matrix_questions(
            filename="questions.txt",
            content=b"What is PEP 8?",
            content_type="text/plain",
        )

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
        self.use_case.preview_queued_questions_import.assert_not_called()

    def test_content_manager_can_import_csv_queued_questions(self) -> None:
        self.use_case.import_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=5,
                    question="What is PEP 8?",
                    grade=GradeEnum.JUNIOR,
                    sheet="python",
                    created_at=datetime(2026, 6, 7, 12, 5, tzinfo=UTC),
                ),
            ],
        )

        response = self.api.post_import_queued_matrix_questions(
            filename="questions.csv",
            content="question;sheet;grade\nЧто такое PEP 8?;python;Junior".encode(),
            content_type="text/csv",
            selected_row_numbers=[2],
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        self.use_case.import_queued_questions.assert_called_once_with(
            params=ANY,
            suggested_by_username="test",
        )
        call_params = self.use_case.import_queued_questions.call_args.kwargs["params"]
        assert self.collections.pluck(items=call_params.questions, attr="question") == [
            "Что такое PEP 8?",
        ]
        assert self.collections.pluck(items=call_params.questions, attr="sheet") == ["python"]
        assert self.collections.pluck(items=call_params.questions, attr="grade") == [
            GradeEnum.JUNIOR,
        ]

    def test_import_normalizes_line_breaks_inside_question_text(self) -> None:
        self.use_case.import_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=8,
                    question="What is PEP 8?",
                    created_at=datetime(2026, 6, 7, 12, 8, tzinfo=UTC),
                ),
            ],
        )

        response = self.api.post_import_queued_matrix_questions(
            filename="questions.csv",
            content=b'question\n"What is PEP 8?\nHow should it be used?"',
            content_type="text/csv",
            selected_row_numbers=[2],
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        self.use_case.import_queued_questions.assert_called_once_with(
            params=ANY,
            suggested_by_username="test",
        )
        call_params = self.use_case.import_queued_questions.call_args.kwargs["params"]
        assert self.collections.pluck(items=call_params.questions, attr="question") == [
            "What is PEP 8? How should it be used?",
        ]

    def test_content_manager_can_import_xlsx_queued_questions(self) -> None:
        self.use_case.import_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=6,
                    question="What is PEP 8?",
                    created_at=datetime(2026, 6, 7, 12, 6, tzinfo=UTC),
                ),
            ],
        )

        response = self.api.post_import_queued_matrix_questions(
            filename="questions.xlsx",
            content=xlsx_bytes([["questions"], ["What is PEP 8?"]]),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            selected_row_numbers=[2],
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        self.use_case.import_queued_questions.assert_called_once_with(
            params=ANY,
            suggested_by_username="test",
        )
        call_params = self.use_case.import_queued_questions.call_args.kwargs["params"]
        assert self.collections.pluck(items=call_params.questions, attr="question") == [
            "What is PEP 8?",
        ]

    def test_content_manager_can_import_xlsm_queued_questions_without_header(self) -> None:
        self.use_case.import_queued_questions.return_value = QueuedCompetencyMatrixQuestions(
            values=[
                self.factory.core.queued_competency_matrix_question(
                    question_id=7,
                    question="What is PEP 8?",
                    created_at=datetime(2026, 6, 7, 12, 7, tzinfo=UTC),
                ),
            ],
        )

        response = self.api.post_import_queued_matrix_questions(
            filename="questions.xlsm",
            content=xlsx_bytes([["What is PEP 8?"]]),
            content_type="application/vnd.ms-excel.sheet.macroEnabled.12",
            selected_row_numbers=[1],
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        self.use_case.import_queued_questions.assert_called_once_with(
            params=ANY,
            suggested_by_username="test",
        )
        call_params = self.use_case.import_queued_questions.call_args.kwargs["params"]
        assert self.collections.pluck(items=call_params.questions, attr="question") == [
            "What is PEP 8?",
        ]

    def test_regular_user_cannot_import_queued_questions(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="user",
            role=RoleEnum.USER,
        )

        response = self.api.post_import_queued_matrix_questions(
            filename="questions.txt",
            content=b"What is PEP 8?",
            content_type="text/plain",
            selected_row_numbers=[1],
        )

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
        self.use_case.import_queued_questions.assert_not_called()

    def test_import_rejects_csv_without_question_header(self) -> None:
        response = self.api.post_import_queued_matrix_questions(
            filename="questions.csv",
            content=b"title\nWhat is PEP 8?",
            content_type="text/csv",
            selected_row_numbers=[1],
        )

        body = self.asserts.error_message(
            response=response,
            expected_status=codes.BAD_REQUEST,
            expected_message="Question queue import file is invalid.",
        )
        assert body["nested_errors"][0]["message"] == (
            "CSV header must contain one of: question, questions, вопрос, вопросы."
        )
        self.use_case.import_queued_questions.assert_not_called()

    def test_import_rejects_legacy_xls_file(self) -> None:
        response = self.api.post_import_queued_matrix_questions(
            filename="questions.xls",
            content=b"not an xls file",
            content_type="application/vnd.ms-excel",
            selected_row_numbers=[1],
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        body = response.json()
        assert body["nested_errors"][0]["message"] == ("Unsupported import file extension: .xls.")
        self.use_case.import_queued_questions.assert_not_called()

    def test_import_rejects_empty_txt_lines_without_creating_questions(self) -> None:
        response = self.api.post_import_queued_matrix_questions(
            filename="questions.txt",
            content=b"What is PEP 8?\n\nHow does mypy help?",
            content_type="text/plain",
            selected_row_numbers=[2],
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        body = response.json()
        assert body["nested_errors"][0]["message"] == "Selected import row 2 is invalid."
        self.use_case.import_queued_questions.assert_not_called()

    def test_import_rejects_long_questions_without_creating_questions(self) -> None:
        response = self.api.post_import_queued_matrix_questions(
            filename="questions.txt",
            content=("x" * 256).encode(),
            content_type="text/plain",
            selected_row_numbers=[1],
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        body = response.json()
        assert body["nested_errors"][0]["message"] == "Selected import row 1 is invalid."
        self.use_case.import_queued_questions.assert_not_called()

    def test_import_rejects_non_text_excel_cells_without_creating_questions(self) -> None:
        response = self.api.post_import_queued_matrix_questions(
            filename="questions.xlsx",
            content=xlsx_bytes([["questions"], [42]]),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            selected_row_numbers=[2],
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        body = response.json()
        assert body["nested_errors"][0]["message"] == "Selected import row 2 is invalid."
        self.use_case.import_queued_questions.assert_not_called()

    def test_regular_user_cannot_create_queued_question(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="user",
            role=RoleEnum.USER,
        )

        response = self.api.post_create_queued_matrix_question(question="What is PEP 8?")

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
        self.use_case.suggest_question.assert_not_called()

    def test_create_queued_question_rejects_blank_question(self) -> None:
        response = self.api.post_create_queued_matrix_question(question="   ")

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.suggest_question.assert_not_called()

    def test_content_manager_can_reject_queue_entry(self) -> None:
        response = self.api.delete_queued_matrix_question(question_id=7)

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        self.use_case.delete_queued_question.assert_called_once_with(
            question_id=self.factory.core.hex_id(7),
            current_datetime=test_current_datetime,
        )

    def test_reject_queue_entry_returns_conflict_for_active_agent_claim(self) -> None:
        self.use_case.delete_queued_question.side_effect = MatrixQuestionClaimConflictError

        response = self.api.delete_queued_matrix_question(question_id=7)

        self.asserts.error_message(
            response=response,
            expected_status=codes.CONFLICT,
            expected_message="Queued competency matrix question is claimed by an agent",
        )

    def test_content_manager_can_release_agent_claim(self) -> None:
        response = self.api.post_release_queued_matrix_question_claim(question_id=7)

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        self.use_case.release_queued_question_agent_claim.assert_called_once_with(
            question_id=self.factory.core.hex_id(7)
        )

    def test_reject_queue_entry_returns_not_found(self) -> None:
        self.use_case.delete_queued_question.side_effect = (
            QueuedCompetencyMatrixQuestionNotFoundError
        )

        response = self.api.delete_queued_matrix_question(question_id=404)

        self.asserts.error_message(
            response=response,
            expected_status=codes.NOT_FOUND,
            expected_message="Queued competency matrix question not found",
        )

    def test_content_manager_can_create_matrix_item_from_queue_entry(self) -> None:
        self.use_case.create_item_from_queue.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=10,
                question_ru="Что такое PEP 8?",
                question_en="What is PEP 8?",
                answer_ru="Ответ",
                answer_en="Answer",
                interview_answer_explanation_ru="Объяснение ответа",
                interview_answer_explanation_en="Answer explanation",
                sheet_key="python",
                sheet_ru="Питон",
                sheet_en="Python",
                grade=GradeEnum.JUNIOR,
                section_ru="Основы",
                section_en="Core",
                subsection_ru="Стиль",
                subsection_en="Style",
                publish_status=PublishStatusEnum.DRAFT,
            )
        )

        response = self.api.post_create_item_from_queue(
            question_id=7,
            data=self.factory.api.competency_matrix_item_request(
                question_ru="Что такое PEP 8?",
                question_en="What is PEP 8?",
                answer_ru="Ответ",
                answer_en="Answer",
                interview_answer_explanation_ru="Объяснение ответа",
                interview_answer_explanation_en="Answer explanation",
                sheet_key="python",
                sheet_ru="Питон",
                sheet_en="Python",
                grade="Junior",
                section_ru="Основы",
                section_en="Core",
                subsection_ru="Стиль",
                subsection_en="Style",
                resources=[],
            ),
            language="en",
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        body = response.json()
        assert body["id"] == self.factory.core.hex_id(10)
        assert body["question"] == "What is PEP 8?"
        self.use_case.create_item_from_queue.assert_called_once_with(
            params=ANY,
            current_datetime=test_current_datetime,
        )
        call_params = self.use_case.create_item_from_queue.call_args.kwargs["params"]
        assert isinstance(call_params, QueuedCompetencyMatrixQuestionCreateItemParams)
        assert call_params.queued_question_id == self.factory.core.hex_id(7)

    def test_create_from_queue_returns_conflict_for_active_agent_claim(self) -> None:
        self.use_case.create_item_from_queue.side_effect = MatrixQuestionClaimConflictError

        response = self.api.post_create_item_from_queue(
            question_id=7,
            data=self.factory.api.competency_matrix_item_request(
                resources=[],
            ),
            language="en",
        )

        self.asserts.error_message(
            response=response,
            expected_status=codes.CONFLICT,
            expected_message="Queued competency matrix question is claimed by an agent",
        )


def xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()
