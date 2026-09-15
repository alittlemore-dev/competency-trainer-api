import pytest_asyncio
from httpx import codes

from tests.test_cases import ApiTestCase


class TestSheetsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_list(self) -> None:
        self.use_case.list_sheets.return_value = self.factory.core.sheets(
            values=[
                self.factory.core.sheet(key="python", name_ru="Питон", name_en="Python"),
                self.factory.core.sheet(key="sql", name_ru="SQL", name_en="SQL"),
            ],
        )
        response = self.api.get_competency_matrix_sheets(language="en")
        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "sheets": [
                {"key": "python", "name": "Python"},
                {"key": "sql", "name": "SQL"},
            ],
        }
        self.use_case.list_sheets.assert_called_once_with()

    def test_list_requires_explicit_language(self) -> None:
        response = self.api.get_competency_matrix_sheets(language=None)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.list_sheets.assert_not_called()
