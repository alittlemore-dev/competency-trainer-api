import pytest_asyncio
from httpx import codes

from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.schemas import CompetencyMatrixItemPublishStatusSwitchParams
from core.enums import PublishStatusEnum
from tests.test_cases import ApiTestCase


class TestSetDraftStatusToItemAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_set_draft_status_to_competency_matrix_item_not_found(self) -> None:
        self.use_case.switch_item_publish_status.side_effect = CompetencyMatrixItemNotFoundError()
        response = self.api.post_set_draft_status_to_item(pk=-100)
        assert response.status_code == codes.NOT_FOUND, response.content
        assert response.json() == {
            "code": "client_error",
            "type": "not_found",
            "message": "Competency matrix item not found",
            "attr": None,
            "location": None,
        }

    def test_set_draft_status_to_competency_matrix_item(self) -> None:
        response = self.api.post_set_draft_status_to_item(pk=1)
        assert response.status_code == codes.NO_CONTENT, response.content
        self.use_case.switch_item_publish_status.assert_called_once_with(
            params=CompetencyMatrixItemPublishStatusSwitchParams(
                item_id=self.factory.core.hex_id(1),
                publish_status=PublishStatusEnum.DRAFT,
            ),
        )
