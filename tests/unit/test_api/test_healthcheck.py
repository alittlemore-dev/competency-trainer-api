from verbose_http_exceptions import status

from infra.healthcheck import ReadinessCheckError
from tests.test_cases import ApiTestCase


class TestHealthCheckAPI(ApiTestCase):
    def test_healthcheck(self) -> None:
        response = self.api.get_health()
        assert response.status_code == status.HTTP_200_OK

    async def test_ready_returns_ok_when_dependencies_are_available(self) -> None:
        checker = await self.container.get_readiness_checker()

        response = self.api.get_health_ready()

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b""
        checker.check.assert_awaited_once_with()

    async def test_ready_returns_service_unavailable_when_dependency_fails(self) -> None:
        checker = await self.container.get_readiness_checker()
        checker.check.side_effect = ReadinessCheckError

        response = self.api.get_health_ready()

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.content == b""
