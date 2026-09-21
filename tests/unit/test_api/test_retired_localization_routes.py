import pytest
from httpx import codes

from tests.test_cases import ApiTestCase


class TestRetiredLocalizationRoutes(ApiTestCase):
    @pytest.mark.parametrize(
        "path", ["/api/i18n/languages", "/api/i18n/bundles/ru", "/api/i18n/bundles/en"]
    )
    def test_localization_is_owned_by_standalone_service(self, path: str) -> None:
        response = self.api.client.get(path)

        assert response.status_code == codes.NOT_FOUND
