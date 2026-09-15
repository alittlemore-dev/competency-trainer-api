from io import BytesIO
from zipfile import BadZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from core.competency_matrix.exceptions import (
    QuestionQueueImportInvalidError,
    QuestionQueueImportIssue,
)
from core.competency_matrix.readers import QuestionQueueImportExcelReader


class OpenpyxlQuestionQueueImportExcelReader(QuestionQueueImportExcelReader):
    def read_rows(self, *, content: bytes) -> list[tuple[object, ...]]:
        try:
            workbook = load_workbook(
                filename=BytesIO(content),
                read_only=True,
                data_only=True,
                keep_links=False,
            )
        except (BadZipFile, InvalidFileException, KeyError, OSError, ValueError) as exc:
            raise QuestionQueueImportInvalidError(
                issues=[
                    QuestionQueueImportIssue(
                        message="Excel file could not be read.",
                        row_number=None,
                    ),
                ],
            ) from exc

        try:
            worksheet = workbook.worksheets[0]
            return [tuple(row) for row in worksheet.iter_rows(values_only=True)]
        finally:
            workbook.close()
