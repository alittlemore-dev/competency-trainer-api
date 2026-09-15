from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import codes

from core.auth.enums import RoleEnum
from core.auth.schemas import (
    AuthSessionCleanupParams,
    AuthSessionCleanupPolicy,
    AuthSessionCleanupResult,
    AuthSessionCleanupStatus,
    JwtUser,
)
from entrypoints.litestar.api.admin_tools.endpoints import AdminToolsApiController
from entrypoints.litestar.guards import team_manager_guard
from tests.test_cases import ApiTestCase

CURRENT_DATETIME = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)


class TestAdminToolsAuthSessionsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_auth_session_cleanup_use_case()

    def test_get_auth_sessions_status(self) -> None:
        self.use_case.get_cleanup_status.return_value = AuthSessionCleanupStatus(
            expired_count=3,
            expiring_soon_count=4,
            expiring_soon_days=7,
            scheduled_prune_interval_seconds=86_400,
        )

        response = self.api.get_admin_tools_auth_sessions()

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "expiredCount": 3,
            "expiringSoonCount": 4,
            "expiringSoonDays": 7,
            "scheduledPruneIntervalSeconds": 86_400,
        }
        self.use_case.get_cleanup_status.assert_awaited_once_with(
            policy=AuthSessionCleanupPolicy(
                expiring_soon_days=7,
                scheduled_prune_interval_seconds=86_400,
            ),
            params=AuthSessionCleanupParams(current_datetime=CURRENT_DATETIME),
        )

    def test_prune_auth_sessions_returns_refreshed_status(self) -> None:
        self.use_case.prune_expired_sessions.return_value = AuthSessionCleanupResult(
            deleted_count=3,
            expired_count=0,
            expiring_soon_count=4,
            expiring_soon_days=7,
            scheduled_prune_interval_seconds=86_400,
        )

        response = self.api.post_admin_tools_auth_sessions_prune()

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "deletedCount": 3,
            "expiredCount": 0,
            "expiringSoonCount": 4,
            "expiringSoonDays": 7,
            "scheduledPruneIntervalSeconds": 86_400,
        }
        self.use_case.prune_expired_sessions.assert_awaited_once_with(
            policy=AuthSessionCleanupPolicy(
                expiring_soon_days=7,
                scheduled_prune_interval_seconds=86_400,
            ),
            params=AuthSessionCleanupParams(current_datetime=CURRENT_DATETIME),
        )


class TestAdminToolsAuthSessionsAccess(ApiTestCase):
    @pytest.fixture(params=[RoleEnum.OWNER, RoleEnum.ADMIN])
    def jwt_admin(self, request: pytest.FixtureRequest) -> JwtUser:
        return JwtUser(username=request.param.value, role=request.param)

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        use_case = await self.container.get_auth_session_cleanup_use_case()
        use_case.get_cleanup_status.return_value = AuthSessionCleanupStatus(
            expired_count=0,
            expiring_soon_count=0,
            expiring_soon_days=7,
            scheduled_prune_interval_seconds=86_400,
        )

    def test_team_manager_can_get_auth_sessions_status(self) -> None:
        response = self.api.get_admin_tools_auth_sessions()

        self.asserts.status(response=response, expected_status=codes.OK)


class TestNonTeamManagerAdminToolsAuthSessionsAccess(ApiTestCase):
    @pytest.fixture
    def jwt_admin(self) -> JwtUser:
        return JwtUser(username="moderator", role=RoleEnum.MODERATOR)

    def test_moderator_cannot_get_auth_sessions_status(self) -> None:
        response = self.api.get_admin_tools_auth_sessions()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)

    def test_moderator_cannot_prune_auth_sessions(self) -> None:
        response = self.api.post_admin_tools_auth_sessions_prune()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)


class TestAnonymousAdminToolsAuthSessionsAccess(ApiTestCase):
    def test_anonymous_cannot_access_auth_session_tools(self) -> None:
        response = self.no_auth_api.get_admin_tools_auth_sessions()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)


class TestAdminToolsAuthSessionsRouteMetadata:
    def test_controller_uses_team_manager_guard(self) -> None:
        assert AdminToolsApiController.guards == [team_manager_guard]

    def test_auth_session_tool_handlers_are_not_cached(self) -> None:
        assert AdminToolsApiController.get_auth_sessions_status.cache is False
        assert AdminToolsApiController.prune_auth_sessions.cache is False
