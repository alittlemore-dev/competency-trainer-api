import pytest_asyncio
from httpx import codes

from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from tests.test_cases import ApiTestCase


class TestDeleteItemAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_delete_item_not_found(self) -> None:
        self.use_case.delete_item.side_effect = CompetencyMatrixItemNotFoundError()
        response = self.api.delete_item(pk=self.factory.core.hex_id(1))
        assert response.status_code == codes.NOT_FOUND
        assert response.json() == {
            "code": "client_error",
            "type": "not_found",
            "message": "Competency matrix item not found",
            "attr": None,
            "location": None,
        }

    def test_delete_item(self) -> None:
        response = self.api.delete_item(pk=self.factory.core.hex_id(1))
        assert response.status_code == codes.NO_CONTENT
        self.use_case.delete_item.assert_called_once_with(item_id=self.factory.core.hex_id(1))
