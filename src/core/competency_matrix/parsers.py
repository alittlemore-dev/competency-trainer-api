from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import PurePath
from typing import NoReturn, cast

from core.competency_matrix.enums import (
    GradeEnum,
    QuestionQueueImportIssueCodeEnum,
    QuestionQueueImportIssueSeverityEnum,
)
from core.competency_matrix.exceptions import (
    QuestionQueueImportInvalidError,
    QuestionQueueImportIssue,
)
from core.competency_matrix.readers import QuestionQueueImportExcelReader
from core.competency_matrix.schemas import (
    ParsedQuestionRow,
    QuestionQueueImportFile,
    QuestionQueueImportPreview,
    QuestionQueueImportPreviewIssue,
    QuestionQueueImportPreviewRow,
    QuestionQueueImportRules,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestionsCreateParams,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionQueueImportColumnIndexes:
    question: int
    sheet: int | None
    grade: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class QuestionQueueImportParser:
    rules: QuestionQueueImportRules
    excel_reader: QuestionQueueImportExcelReader

    def preview(self, *, file: QuestionQueueImportFile) -> QuestionQueueImportPreview:
        extension = PurePath(file.filename).suffix.lower()
        if extension in self.rules.unsupported_legacy_excel_extensions:
            self.raise_invalid(
                [self.issue(message=f"Unsupported import file extension: {extension}.", row=None)],
            )
        if extension not in self.supported_extensions():
            self.raise_invalid(
                [
                    self.issue(
                        message=(
                            "Unsupported import file extension. Supported extensions: "
                            f"{', '.join(self.rules.supported_extensions_for_message)}."
                        ),
                        row=None,
                    ),
                ],
            )
        rows = self.parse_rows(file=file, extension=extension)
        if not rows:
            self.raise_invalid(
                [self.issue(message="Import file must contain at least one question.", row=None)],
            )
        return QuestionQueueImportPreview(rows=[self.preview_row(row=row) for row in rows])

    def parse_selected(
        self,
        *,
        file: QuestionQueueImportFile,
        selected_row_numbers: list[int],
    ) -> QueuedCompetencyMatrixQuestionsCreateParams:
        return self.preview(file=file).selected_questions(row_numbers=selected_row_numbers)

    def preview_row(self, *, row: ParsedQuestionRow) -> QuestionQueueImportPreviewRow:
        issues: list[QuestionQueueImportPreviewIssue] = []
        if not isinstance(row.question, str):
            issues.append(
                self.preview_issue(code=QuestionQueueImportIssueCodeEnum.QUESTION_NOT_TEXT),
            )
        else:
            question = self.normalize_question_text(value=row.question).strip()
            if not question:
                issues.append(
                    self.preview_issue(code=QuestionQueueImportIssueCodeEnum.QUESTION_BLANK),
                )
            elif len(question) > self.rules.question_max_length:
                issues.append(
                    self.preview_issue(code=QuestionQueueImportIssueCodeEnum.QUESTION_TOO_LONG),
                )
        if row.sheet is not None and not isinstance(row.sheet, str):
            issues.append(
                self.preview_issue(code=QuestionQueueImportIssueCodeEnum.SHEET_NOT_TEXT),
            )
        if row.grade is not None:
            if not isinstance(row.grade, str):
                issues.append(
                    self.preview_issue(code=QuestionQueueImportIssueCodeEnum.GRADE_NOT_TEXT),
                )
            elif self.normalize_optional_text(value=row.grade) is not None:
                grade = self.normalize_optional_text(value=row.grade)
                if grade not in {item.value for item in GradeEnum}:
                    issues.append(
                        self.preview_issue(code=QuestionQueueImportIssueCodeEnum.GRADE_INVALID),
                    )
        params = None
        if not issues:
            params = QueuedCompetencyMatrixQuestionCreateParams(
                question=self.normalize_question_text(value=cast("str", row.question)).strip(),
                sheet=self.normalize_optional_text(value=cast("str | None", row.sheet)),
                grade=self.normalize_optional_grade(value=cast("str | None", row.grade)),
            )
        return QuestionQueueImportPreviewRow(
            row_number=row.row_number,
            question=self.display_value(value=row.question, normalize=True),
            sheet=self.display_value(value=row.sheet, normalize=True),
            grade=self.display_value(value=row.grade, normalize=True),
            params=params,
            issues=tuple(issues),
        )

    def preview_issue(
        self,
        *,
        code: QuestionQueueImportIssueCodeEnum,
    ) -> QuestionQueueImportPreviewIssue:
        return QuestionQueueImportPreviewIssue(
            code=code,
            severity=QuestionQueueImportIssueSeverityEnum.ERROR,
            related_row_numbers=(),
        )

    def display_value(self, *, value: object | None, normalize: bool) -> str:
        if value is None:
            return ""
        text = value if isinstance(value, str) else str(value)
        if normalize:
            return self.normalize_question_text(value=text).strip()
        return text

    def parse(
        self,
        *,
        file: QuestionQueueImportFile,
    ) -> QueuedCompetencyMatrixQuestionsCreateParams:
        preview = self.preview(file=file)
        issues = [
            QuestionQueueImportIssue(
                message=self.preview_issue_message(code=issue.code, row_number=row.row_number),
                row_number=row.row_number,
            )
            for row in preview.rows
            for issue in row.issues
            if issue.severity == QuestionQueueImportIssueSeverityEnum.ERROR
        ]
        if issues:
            self.raise_invalid(issues)
        return QueuedCompetencyMatrixQuestionsCreateParams(
            questions=[row.params for row in preview.rows if row.params is not None],
        )

    def preview_issue_message(
        self,
        *,
        code: QuestionQueueImportIssueCodeEnum,
        row_number: int,
    ) -> str:
        messages = {
            QuestionQueueImportIssueCodeEnum.QUESTION_NOT_TEXT: (
                f"Row {row_number} question must be text."
            ),
            QuestionQueueImportIssueCodeEnum.QUESTION_BLANK: (
                f"Row {row_number} question must not be blank."
            ),
            QuestionQueueImportIssueCodeEnum.QUESTION_TOO_LONG: (
                f"Row {row_number} question must be at most "
                f"{self.rules.question_max_length} characters."
            ),
            QuestionQueueImportIssueCodeEnum.SHEET_NOT_TEXT: (
                f"Row {row_number} sheet must be text."
            ),
            QuestionQueueImportIssueCodeEnum.GRADE_NOT_TEXT: (
                f"Row {row_number} grade must be text."
            ),
            QuestionQueueImportIssueCodeEnum.GRADE_INVALID: (
                f"Row {row_number} grade must be one of: "
                f"{', '.join(grade.value for grade in GradeEnum)}."
            ),
        }
        return messages[code]

    def supported_extensions(self) -> frozenset[str]:
        return self.rules.supported_text_extensions | self.rules.supported_excel_extensions

    def parse_rows(
        self,
        *,
        file: QuestionQueueImportFile,
        extension: str,
    ) -> list[ParsedQuestionRow]:
        if extension == ".txt":
            return self.parse_txt(content=file.content)
        if extension == ".csv":
            return self.parse_csv(content=file.content)
        return self.parse_excel(content=file.content)

    def parse_txt(self, *, content: bytes) -> list[ParsedQuestionRow]:
        text = self.decode_text(content=content)
        return [
            ParsedQuestionRow(
                row_number=row_number,
                question=line.strip(),
                sheet=None,
                grade=None,
            )
            for row_number, line in enumerate(text.splitlines(), start=1)
        ]

    def parse_csv(self, *, content: bytes) -> list[ParsedQuestionRow]:
        text = self.decode_text(content=content)
        reader = csv.reader(StringIO(text), dialect=self.csv_dialect(text=text))
        rows = list(reader)
        if not rows:
            self.raise_invalid(
                [self.issue(message="Import file must contain at least one question.", row=None)],
            )

        column_indexes = self.csv_column_indexes(header=rows[0])
        return [
            ParsedQuestionRow(
                row_number=row_number,
                question=self.cell(row=row, index=column_indexes.question, missing_value=""),
                sheet=self.cell(row=row, index=column_indexes.sheet, missing_value=None),
                grade=self.cell(row=row, index=column_indexes.grade, missing_value=None),
            )
            for row_number, row in enumerate(rows[1:], start=2)
        ]

    def parse_excel(self, *, content: bytes) -> list[ParsedQuestionRow]:
        rows = self.excel_reader.read_rows(content=content)
        if not rows:
            self.raise_invalid(
                [self.issue(message="Import file must contain at least one question.", row=None)],
            )
        column_indexes, first_question_row_index = self.excel_column_indexes(rows=rows)
        return [
            ParsedQuestionRow(
                row_number=row_number,
                question=self.cell(row=row, index=column_indexes.question, missing_value=None),
                sheet=self.cell(row=row, index=column_indexes.sheet, missing_value=None),
                grade=self.cell(row=row, index=column_indexes.grade, missing_value=None),
            )
            for row_number, row in enumerate(
                rows[first_question_row_index:],
                start=first_question_row_index + 1,
            )
        ]

    def decode_text(self, *, content: bytes) -> str:
        try:
            return content.decode("utf-8-sig")
        except UnicodeDecodeError:
            self.raise_invalid(
                [self.issue(message="Import file must be UTF-8 encoded text.", row=None)],
            )

    def csv_dialect(self, *, text: str) -> type[csv.Dialect] | csv.Dialect:
        try:
            return csv.Sniffer().sniff(text[:2048], delimiters=self.rules.csv_delimiters)
        except csv.Error:
            return csv.excel

    def csv_column_indexes(self, *, header: list[str]) -> QuestionQueueImportColumnIndexes:
        return QuestionQueueImportColumnIndexes(
            question=self.question_column_index(header=header),
            sheet=self.optional_column_index(header=header, headers=self.rules.sheet_headers),
            grade=self.optional_column_index(header=header, headers=self.rules.grade_headers),
        )

    def question_column_index(self, *, header: tuple[object, ...] | list[str]) -> int:
        for index, value in enumerate(header):
            if isinstance(value, str) and value.strip().casefold() in self.rules.question_headers:
                return index
        self.raise_invalid(
            [
                self.issue(
                    message=(
                        "CSV header must contain one of: "
                        f"{', '.join(self.rules.question_headers_for_message)}."
                    ),
                    row=None,
                ),
            ],
        )
        raise AssertionError

    def optional_column_index(
        self,
        *,
        header: tuple[object, ...] | list[str],
        headers: frozenset[str],
    ) -> int | None:
        for index, value in enumerate(header):
            if isinstance(value, str) and value.strip().casefold() in headers:
                return index
        return None

    def excel_column_indexes(
        self,
        *,
        rows: list[tuple[object, ...]],
    ) -> tuple[QuestionQueueImportColumnIndexes, int]:
        header = rows[0]
        for value in header:
            if isinstance(value, str) and value.strip().casefold() in self.rules.question_headers:
                return (
                    QuestionQueueImportColumnIndexes(
                        question=self.question_column_index(header=header),
                        sheet=self.optional_column_index(
                            header=header,
                            headers=self.rules.sheet_headers,
                        ),
                        grade=self.optional_column_index(
                            header=header,
                            headers=self.rules.grade_headers,
                        ),
                    ),
                    1,
                )
        return QuestionQueueImportColumnIndexes(question=0, sheet=None, grade=None), 0

    def cell(
        self,
        *,
        row: tuple[object, ...] | list[str],
        index: int | None,
        missing_value: object | None,
    ) -> object | None:
        if index is None or index >= len(row):
            return missing_value
        return row[index]

    def normalize_question_text(self, *, value: str) -> str:
        return value.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")

    def normalize_optional_text(self, *, value: str | None) -> str | None:
        if value is None:
            return None
        text = self.normalize_question_text(value=value).strip()
        if not text:
            return None
        return text

    def normalize_optional_grade(self, *, value: str | None) -> GradeEnum | None:
        text = self.normalize_optional_text(value=value)
        if text is None:
            return None
        return GradeEnum(text)

    def issue(
        self,
        *,
        message: str,
        row: ParsedQuestionRow | None,
    ) -> QuestionQueueImportIssue:
        row_number = None if row is None else row.row_number
        return QuestionQueueImportIssue(
            message=message.format(row=row_number),
            row_number=row_number,
        )

    def raise_invalid(self, issues: list[QuestionQueueImportIssue]) -> NoReturn:
        raise QuestionQueueImportInvalidError(issues=issues)
