from io import BytesIO

import pytest
from openpyxl import Workbook

from core.competency_matrix.exceptions import QuestionQueueImportInvalidError
from infra.openpyxl.readers import OpenpyxlQuestionQueueImportExcelReader


class TestOpenpyxlQuestionQueueImportExcelReader:
    def test_reads_first_sheet_values_from_xlsx(self) -> None:
        reader = OpenpyxlQuestionQueueImportExcelReader()

        rows = reader.read_rows(content=xlsx_bytes([["questions"], ["What is PEP 8?"]]))

        assert rows == [("questions",), ("What is PEP 8?",)]

    def test_reads_first_sheet_values_from_xlsm(self) -> None:
        reader = OpenpyxlQuestionQueueImportExcelReader()

        rows = reader.read_rows(content=xlsx_bytes([["What is PEP 8?"]]))

        assert rows == [("What is PEP 8?",)]

    def test_invalid_excel_bytes_raise_import_error_without_leaking_openpyxl_error(self) -> None:
        reader = OpenpyxlQuestionQueueImportExcelReader()

        with pytest.raises(QuestionQueueImportInvalidError) as exc_info:
            reader.read_rows(content=b"not an excel file")

        assert [issue.message for issue in exc_info.value.issues] == [
            "Excel file could not be read.",
        ]
        assert [issue.attr_name for issue in exc_info.value.issues] == ["file"]


def xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    return stream.getvalue()
