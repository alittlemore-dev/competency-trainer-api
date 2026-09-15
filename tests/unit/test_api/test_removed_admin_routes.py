import pytest
from httpx import codes

from tests.test_cases import ApiTestCase


class TestRemovedAdminRoutes(ApiTestCase):
    @pytest.mark.parametrize(
        "path",
        [
            "/api/admin/knowledge/people",
            "/api/admin/knowledge/dates",
            "/api/admin/knowledge/tags",
            "/api/admin/knowledge/files/11111111111111111111111111111111",
            "/api/admin/calendar?referenceDate=2026-08-14&window=month",
            "/api/admin/resumes",
            "/api/admin/resumes/11111111111111111111111111111111",
            "/api/admin/resumes/11111111111111111111111111111111/export",
        ],
    )
    def test_removed_admin_get_route_returns_framework_not_found(self, path: str) -> None:
        response = self.api.client.get(path)

        assert response.status_code == codes.NOT_FOUND, response.content
