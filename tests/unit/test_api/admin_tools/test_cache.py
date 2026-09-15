from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import codes

from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.cache_tools.enums import CacheDomainEnum, CacheWarmOperationStatusEnum
from core.cache_tools.exceptions import CacheWarmOperationNotFoundError
from core.cache_tools.schemas import (
    CacheDomainStatus,
    CacheToolsStatus,
    CacheWarmOperation,
    CacheWarmSummary,
)
from entrypoints.litestar.api.admin_tools.endpoints import AdminToolsApiController
from tests.test_cases import ApiTestCase

QUEUED_AT = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def cache_status() -> CacheToolsStatus:
    return CacheToolsStatus(
        enabled=True,
        configured_ttl_seconds=86_400,
        scheduled_warm_interval_seconds=3_600,
        domains=(
            CacheDomainStatus(
                domain=CacheDomainEnum.I18N,
                key_count=3,
                minimum_remaining_ttl_seconds=120,
                non_expiring_key_count=1,
            ),
            CacheDomainStatus(
                domain=CacheDomainEnum.ARTICLES,
                key_count=0,
                minimum_remaining_ttl_seconds=None,
                non_expiring_key_count=0,
            ),
            CacheDomainStatus(
                domain=CacheDomainEnum.COMPETENCY_MATRIX,
                key_count=5,
                minimum_remaining_ttl_seconds=30,
                non_expiring_key_count=0,
            ),
        ),
        last_manual_warm_operation=CacheWarmOperation(
            operation_id="previous-operation",
            status=CacheWarmOperationStatusEnum.SUCCEEDED,
            queued_at=QUEUED_AT,
            summary=CacheWarmSummary(attempted=8, written=8, skipped=0),
        ),
    )


class TestAdminToolsCacheAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_cache_tools_use_case()
        self.policy = await self.container.get_cache_tools_policy()

    def test_get_cache_status(self) -> None:
        self.use_case.get_status.return_value = cache_status()

        response = self.api.get_admin_tools_cache()

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "enabled": True,
            "configuredTtlSeconds": 86_400,
            "scheduledWarmIntervalSeconds": 3_600,
            "domains": [
                {
                    "domain": "i18n",
                    "keyCount": 3,
                    "minimumRemainingTtlSeconds": 120,
                    "nonExpiringKeyCount": 1,
                },
                {
                    "domain": "articles",
                    "keyCount": 0,
                    "minimumRemainingTtlSeconds": None,
                    "nonExpiringKeyCount": 0,
                },
                {
                    "domain": "competency_matrix",
                    "keyCount": 5,
                    "minimumRemainingTtlSeconds": 30,
                    "nonExpiringKeyCount": 0,
                },
            ],
            "lastManualWarmOperation": {
                "operationId": "previous-operation",
                "status": "succeeded",
                "queuedAt": "2026-07-16T12:00:00Z",
                "summary": {"attempted": 8, "written": 8, "skipped": 0},
            },
        }
        self.use_case.get_status.assert_awaited_once_with(policy=self.policy)

    def test_clear_cache_returns_refreshed_status_without_warming(self) -> None:
        self.use_case.clear.return_value = cache_status()

        response = self.api.post_admin_tools_cache_clear()

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json()["domains"][0]["keyCount"] == 3
        self.use_case.clear.assert_awaited_once_with(policy=self.policy)
        self.use_case.enqueue_manual_warm.assert_not_awaited()

    def test_manual_warm_returns_pollable_queued_operation(self) -> None:
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.QUEUED,
            queued_at=QUEUED_AT,
            summary=None,
        )
        self.use_case.enqueue_manual_warm.return_value = operation

        response = self.api.post_admin_tools_cache_warm()

        self.asserts.status(response=response, expected_status=codes.ACCEPTED)
        assert response.json() == {
            "operationId": "operation-id",
            "status": "queued",
            "queuedAt": "2026-07-16T12:00:00Z",
            "summary": None,
        }

    def test_get_manual_warm_operation_for_polling(self) -> None:
        operation = CacheWarmOperation(
            operation_id="operation-id",
            status=CacheWarmOperationStatusEnum.RUNNING,
            queued_at=QUEUED_AT,
            summary=None,
        )
        self.use_case.get_manual_warm_operation.return_value = operation

        response = self.api.get_admin_tools_cache_warm_operation(
            operation_id="operation-id",
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json()["status"] == "running"
        self.use_case.get_manual_warm_operation.assert_awaited_once_with(
            operation_id="operation-id",
        )

    def test_unknown_manual_warm_operation_returns_not_found(self) -> None:
        self.use_case.get_manual_warm_operation.side_effect = CacheWarmOperationNotFoundError()

        response = self.api.get_admin_tools_cache_warm_operation(operation_id="missing")

        self.asserts.status(response=response, expected_status=codes.NOT_FOUND)


class TestAdminToolsCacheAccess(ApiTestCase):
    @pytest.fixture
    def jwt_admin(self) -> JwtUser:
        return JwtUser(username="moderator", role=RoleEnum.MODERATOR)

    def test_moderator_cannot_clear_or_warm_cache(self) -> None:
        clear_response = self.api.post_admin_tools_cache_clear()
        warm_response = self.api.post_admin_tools_cache_warm()

        self.asserts.status(response=clear_response, expected_status=codes.UNAUTHORIZED)
        self.asserts.status(response=warm_response, expected_status=codes.UNAUTHORIZED)


class TestAdminToolsCacheRouteMetadata:
    def test_cache_tool_handlers_are_not_cached(self) -> None:
        assert AdminToolsApiController.get_cache_status.cache is False
        assert AdminToolsApiController.clear_cache.cache is False
        assert AdminToolsApiController.warm_cache.cache is False
        assert AdminToolsApiController.get_cache_warm_operation.cache is False
