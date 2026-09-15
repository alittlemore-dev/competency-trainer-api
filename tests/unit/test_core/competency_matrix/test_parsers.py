import pytest

from core.competency_matrix.enums import GradeEnum, QuestionQueueImportIssueCodeEnum
from core.competency_matrix.exceptions import QuestionQueueImportInvalidError
from core.competency_matrix.parsers import QuestionQueueImportParser
from core.competency_matrix.readers import QuestionQueueImportExcelReader
from core.competency_matrix.schemas import (
    QuestionQueueImportFile,
    QuestionQueueImportRules,
)

TEST_IMPORT_RULES = QuestionQueueImportRules(
    supported_text_extensions=frozenset({".txt", ".csv"}),
    supported_excel_extensions=frozenset({".xlsx", ".xlsm"}),
    unsupported_legacy_excel_extensions=frozenset({".xls"}),
    supported_extensions_for_message=(".txt", ".csv", ".xlsx", ".xlsm"),
    question_headers=frozenset({"question", "questions", "вопрос", "вопросы"}),
    question_headers_for_message=("question", "questions", "вопрос", "вопросы"),
    sheet_headers=frozenset({"sheet", "лист"}),
    grade_headers=frozenset({"grade", "грейд"}),
    csv_delimiters=",;\t|",
    question_max_length=255,
)


class FakeExcelReader(QuestionQueueImportExcelReader):
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.read_contents: list[bytes] = []

    def read_rows(self, *, content: bytes) -> list[tuple[object, ...]]:
        self.read_contents.append(content)
        return self.rows


class TestQuestionQueueImportParser:
    def test_preview_rejects_empty_text_file(self) -> None:
        parser = parser_with_excel_rows([])

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            parser.preview(
                file=QuestionQueueImportFile(
                    filename="questions.txt",
                    content=b"",
                ),
            )

        assert [issue.message for issue in exc_info.value.issues] == [
            "Import file must contain at least one question.",
        ]

    def test_preview_keeps_valid_and_invalid_rows_for_confirmation(self) -> None:
        parser = parser_with_excel_rows([])

        preview = parser.preview(
            file=QuestionQueueImportFile(
                filename="questions.csv",
                content=b"question,sheet,grade\nWhat is PEP 8?,python,Junior\n,python,Lead",
            ),
        )

        assert [row.row_number for row in preview.rows] == [2, 3]
        assert preview.rows[0].params is not None
        assert preview.rows[0].params.question == "What is PEP 8?"
        assert preview.rows[0].params.grade == GradeEnum.JUNIOR
        assert preview.rows[1].params is None
        assert [issue.code for issue in preview.rows[1].issues] == [
            QuestionQueueImportIssueCodeEnum.QUESTION_BLANK,
            QuestionQueueImportIssueCodeEnum.GRADE_INVALID,
        ]

    def test_parse_selected_imports_only_valid_selected_rows_in_file_order(self) -> None:
        parser = parser_with_excel_rows([])
        file = QuestionQueueImportFile(
            filename="questions.txt",
            content=b"First question\n\nThird question",
        )

        params = parser.parse_selected(file=file, selected_row_numbers=[3, 1])

        assert [question.question for question in params.questions] == [
            "First question",
            "Third question",
        ]

    @pytest.mark.parametrize("selected_row_numbers", [[], [1, 1], [2], [404]])
    def test_parse_selected_rejects_invalid_selection(
        self,
        selected_row_numbers: list[int],
    ) -> None:
        parser = parser_with_excel_rows([])

        with pytest.raises(QuestionQueueImportInvalidError):
            parser.parse_selected(
                file=QuestionQueueImportFile(
                    filename="questions.txt",
                    content=b"Valid question\n",
                ),
                selected_row_numbers=selected_row_numbers,
            )

    def test_txt_import_preserves_duplicates(self) -> None:
        parser = parser_with_excel_rows([])

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.txt",
                content=b"What is PEP 8?\nWhat is PEP 8?",
            ),
        )

        assert [question.question for question in params.questions] == [
            "What is PEP 8?",
            "What is PEP 8?",
        ]

    def test_csv_import_uses_first_matching_header_and_sniffed_delimiter(self) -> None:
        parser = parser_with_excel_rows([])

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.csv",
                content="ignored|вопросы\nx|Что такое PEP 8?".encode(),
            ),
        )

        assert [question.question for question in params.questions] == ["Что такое PEP 8?"]

    def test_csv_import_reads_optional_context_columns_in_declared_order(self) -> None:
        parser = parser_with_excel_rows([])

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.csv",
                content=b"question,sheet,grade\nWhat is PEP 8?,python,Junior",
            ),
        )

        assert params.questions[0].question == "What is PEP 8?"
        assert params.questions[0].sheet == "python"
        assert params.questions[0].grade == GradeEnum.JUNIOR

    def test_csv_import_keeps_blank_optional_context_columns_empty(self) -> None:
        parser = parser_with_excel_rows([])

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.csv",
                content=b"question,sheet,grade\nWhat is PEP 8?,,",
            ),
        )

        assert params.questions[0].question == "What is PEP 8?"
        assert params.questions[0].sheet is None
        assert params.questions[0].grade is None

    def test_import_normalizes_line_breaks_inside_question_text(self) -> None:
        parser = parser_with_excel_rows([])

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.csv",
                content=b'question\n"What is PEP 8?\nHow should it be used?"',
            ),
        )

        assert [question.question for question in params.questions] == [
            "What is PEP 8? How should it be used?",
        ]

    def test_csv_without_question_header_returns_structured_issue(self) -> None:
        parser = parser_with_excel_rows([])

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            parser.parse(
                file=QuestionQueueImportFile(
                    filename="questions.csv",
                    content=b"title\nWhat is PEP 8?",
                ),
            )

        assert exc_info.value.message == "Question queue import file is invalid."
        assert [issue.message for issue in exc_info.value.issues] == [
            "CSV header must contain one of: question, questions, вопрос, вопросы.",
        ]
        assert [issue.attr_name for issue in exc_info.value.issues] == ["file"]

    def test_excel_with_header_reads_matching_column_from_second_row(self) -> None:
        reader = FakeExcelReader(rows=[("ignored", "questions"), ("x", "What is PEP 8?")])
        parser = parser_with_excel_reader(reader)

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.xlsx",
                content=b"xlsx bytes",
            ),
        )

        assert reader.read_contents == [b"xlsx bytes"]
        assert [question.question for question in params.questions] == ["What is PEP 8?"]

    def test_excel_with_header_reads_optional_context_columns(self) -> None:
        reader = FakeExcelReader(
            rows=[
                ("questions", "sheet", "grade"),
                ("How does mypy help?", "python", "Middle"),
            ],
        )
        parser = parser_with_excel_reader(reader)

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.xlsx",
                content=b"xlsx bytes",
            ),
        )

        assert params.questions[0].question == "How does mypy help?"
        assert params.questions[0].sheet == "python"
        assert params.questions[0].grade == GradeEnum.MIDDLE

    def test_excel_without_header_reads_first_column_from_first_row(self) -> None:
        parser = parser_with_excel_rows([("What is PEP 8?", "ignored"), ("What is Black?",)])

        params = parser.parse(
            file=QuestionQueueImportFile(
                filename="questions.xlsm",
                content=b"xlsm bytes",
            ),
        )

        assert [question.question for question in params.questions] == [
            "What is PEP 8?",
            "What is Black?",
        ]

    def test_excel_non_text_cell_returns_row_issue(self) -> None:
        parser = parser_with_excel_rows([("questions",), (42,)])

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            parser.parse(
                file=QuestionQueueImportFile(
                    filename="questions.xlsx",
                    content=b"xlsx bytes",
                ),
            )

        assert [issue.message for issue in exc_info.value.issues] == [
            "Row 2 question must be text.",
        ]
        assert [issue.attr_name for issue in exc_info.value.issues] == ["file.row.2"]

    def test_import_invalid_grade_returns_row_issue(self) -> None:
        parser = parser_with_excel_rows([])

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            parser.parse(
                file=QuestionQueueImportFile(
                    filename="questions.csv",
                    content=b"grade,question\nLead,What is PEP 8?",
                ),
            )

        assert [issue.message for issue in exc_info.value.issues] == [
            "Row 2 grade must be one of: Junior, Junior+, Middle, Middle+, Senior.",
        ]
        assert [issue.attr_name for issue in exc_info.value.issues] == ["file.row.2"]

    def test_txt_blank_line_and_long_question_return_all_issues(self) -> None:
        parser = parser_with_excel_rows([])

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            parser.parse(
                file=QuestionQueueImportFile(
                    filename="questions.txt",
                    content=f"What is PEP 8?\n\n{'x' * 256}".encode(),
                ),
            )

        assert [issue.message for issue in exc_info.value.issues] == [
            "Row 2 question must not be blank.",
            "Row 3 question must be at most 255 characters.",
        ]

    @pytest.mark.parametrize(
        ("filename", "message"),
        [
            ("questions.xls", "Unsupported import file extension: .xls."),
            (
                "questions.json",
                (
                    "Unsupported import file extension. Supported extensions: "
                    ".txt, .csv, .xlsx, .xlsm."
                ),
            ),
        ],
    )
    def test_unsupported_extensions_return_structured_issue(
        self,
        filename: str,
        message: str,
    ) -> None:
        parser = parser_with_excel_rows([])

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            parser.parse(
                file=QuestionQueueImportFile(
                    filename=filename,
                    content=b"question",
                ),
            )

        assert [issue.message for issue in exc_info.value.issues] == [message]
        assert [issue.attr_name for issue in exc_info.value.issues] == ["file"]


def parser_with_excel_rows(rows: list[tuple[object, ...]]) -> QuestionQueueImportParser:
    return parser_with_excel_reader(FakeExcelReader(rows=rows))


def parser_with_excel_reader(
    excel_reader: QuestionQueueImportExcelReader,
) -> QuestionQueueImportParser:
    return QuestionQueueImportParser(
        rules=TEST_IMPORT_RULES,
        excel_reader=excel_reader,
    )
