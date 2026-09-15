from datetime import UTC, datetime, timedelta

import pytest_asyncio
from httpx import codes

from core.account.schemas import (
    ManagedAccount,
    ManagedAccountCreateOperationParams,
    ManagedAccountCreateParams,
    ManagedAccountFilters,
    ManagedAccountPasswordUpdateOperationParams,
    ManagedAccountPasswordUpdateParams,
    ManagedAccountRoleUpdateOperationParams,
    ManagedAccountRoleUpdateParams,
    ManagedAccountSession,
    ManagedAccountSessionRevocationResult,
    ManagedAccountSessionRevokeOperationParams,
    ManagedAccountSessions,
    ManagedAccountSessionsOperationParams,
    ManagedAccountSessionsRevokeOthersOperationParams,
    ManagedAccountTargetOperationParams,
)
from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.schemas import AuthSessionClientMetadata, JwtUser
from core.schemas import Secret
from tests.test_cases import ApiTestCase


class TestAdminAccountsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.use_case = await self.container.get_accounts_use_case()

    def test_list_accounts(self) -> None:
        self.use_case.list_accounts.return_value = self.factory.core.managed_accounts(
            values=[
                ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True),
                ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
                ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=False),
            ],
            total_count=3,
            total_pages=1,
        )

        response = self.api.get_admin_accounts(page=2, page_size=10)

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "totalCount": 3,
            "totalPages": 1,
            "accounts": [
                {"username": "Owner", "role": "owner", "isActive": True},
                {"username": "Admin", "role": "admin", "isActive": True},
                {"username": "Moderator", "role": "moderator", "isActive": False},
            ],
        }
        self.use_case.list_accounts.assert_called_once_with(
            filters=ManagedAccountFilters(page=2, page_size=10),
        )

    def test_create_account(self) -> None:
        self.use_case.create_account.return_value = ManagedAccount(
            username="Moderator_1",
            role=RoleEnum.MODERATOR,
            is_active=True,
        )

        response = self.api.post_create_admin_account(
            data={
                "username": "Moderator_1",
                "role": "moderator",
                "password": "password123",
                "isActive": True,
            },
        )

        self.asserts.status(response=response, expected_status=codes.CREATED)
        assert response.json() == {
            "username": "Moderator_1",
            "role": "moderator",
            "isActive": True,
        }
        self.use_case.create_account.assert_called_once_with(
            params=ManagedAccountCreateOperationParams(
                create_params=ManagedAccountCreateParams(
                    username="Moderator_1",
                    role=RoleEnum.MODERATOR,
                    password=Secret("password123"),
                    is_active=True,
                ),
                current_username="test",
            ),
        )

    def test_get_account(self) -> None:
        self.use_case.get_account.return_value = ManagedAccount(
            username="Admin",
            role=RoleEnum.ADMIN,
            is_active=True,
        )

        response = self.api.get_admin_account(username="ADMIN")

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"username": "Admin", "role": "admin", "isActive": True}
        self.use_case.get_account.assert_called_once_with(username="ADMIN")

    def test_update_role(self) -> None:
        self.use_case.update_role.return_value = ManagedAccount(
            username="Moderator",
            role=RoleEnum.ADMIN,
            is_active=True,
        )

        response = self.api.put_admin_account_role(
            username="Moderator",
            data={"role": "admin"},
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"username": "Moderator", "role": "admin", "isActive": True}
        self.use_case.update_role.assert_called_once_with(
            params=ManagedAccountRoleUpdateOperationParams(
                target_username="Moderator",
                role_params=ManagedAccountRoleUpdateParams(role=RoleEnum.ADMIN),
                current_username="test",
            ),
        )

    def test_update_password(self) -> None:
        self.use_case.update_password.return_value = ManagedAccount(
            username="test",
            role=RoleEnum.ADMIN,
            is_active=True,
        )

        response = self.api.put_admin_account_password(
            username="test",
            data={"password": "password123"},
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"username": "test", "role": "admin", "isActive": True}
        self.use_case.update_password.assert_called_once_with(
            params=ManagedAccountPasswordUpdateOperationParams(
                target_username="test",
                password_params=ManagedAccountPasswordUpdateParams(password=Secret("password123")),
                current_username="test",
            ),
        )

    def test_activate_account(self) -> None:
        self.use_case.activate_account.return_value = ManagedAccount(
            username="Moderator",
            role=RoleEnum.MODERATOR,
            is_active=True,
        )

        response = self.api.post_activate_admin_account(username="Moderator")

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"username": "Moderator", "role": "moderator", "isActive": True}
        self.use_case.activate_account.assert_called_once_with(
            params=ManagedAccountTargetOperationParams(
                target_username="Moderator",
                current_username="test",
            ),
        )

    def test_deactivate_account(self) -> None:
        self.use_case.deactivate_account.return_value = ManagedAccount(
            username="Moderator",
            role=RoleEnum.MODERATOR,
            is_active=False,
        )

        response = self.api.post_deactivate_admin_account(username="Moderator")

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "username": "Moderator",
            "role": "moderator",
            "isActive": False,
        }
        self.use_case.deactivate_account.assert_called_once_with(
            params=ManagedAccountTargetOperationParams(
                target_username="Moderator",
                current_username="test",
            ),
        )

    def test_delete_account(self) -> None:
        response = self.api.delete_admin_account(username="Moderator")

        self.asserts.status(response=response, expected_status=codes.NO_CONTENT)
        self.use_case.delete_account.assert_called_once_with(
            params=ManagedAccountTargetOperationParams(
                target_username="Moderator",
                current_username="test",
            ),
        )

    def test_list_account_sessions(self) -> None:
        self.use_case.list_account_sessions.return_value = ManagedAccountSessions(
            values=[
                managed_account_session(
                    session_id="10000000000040008000000000000001",
                    is_current=True,
                ),
                managed_account_session(
                    session_id="20000000000040008000000000000002",
                    is_current=False,
                ),
            ],
        )

        response = self.api.get_admin_account_sessions(username="Admin")

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {
            "sessions": [
                {
                    "id": "10000000000040008000000000000001",
                    "userAgentDisplay": "Firefox on Linux",
                    "userAgentBrowser": "Firefox",
                    "userAgentOs": "Linux",
                    "userAgentDevice": "desktop",
                    "authMethod": "password",
                    "createdAt": "2026-07-07T11:30:00+00:00",
                    "lastUsedAt": "2026-07-08T11:30:00+00:00",
                    "expiresAt": "2026-08-07T11:30:00+00:00",
                    "isCurrent": True,
                },
                {
                    "id": "20000000000040008000000000000002",
                    "userAgentDisplay": "Firefox on Linux",
                    "userAgentBrowser": "Firefox",
                    "userAgentOs": "Linux",
                    "userAgentDevice": "desktop",
                    "authMethod": "password",
                    "createdAt": "2026-07-07T11:30:00+00:00",
                    "lastUsedAt": "2026-07-08T11:30:00+00:00",
                    "expiresAt": "2026-08-07T11:30:00+00:00",
                    "isCurrent": False,
                },
            ],
        }
        self.use_case.list_account_sessions.assert_called_once_with(
            params=ManagedAccountSessionsOperationParams(
                target_username="Admin",
                current_username="test",
                current_session_id="10000000000040008000000000000001",
                current_datetime=datetime(2026, 7, 8, 11, 30, tzinfo=UTC),
            ),
        )

    def test_revoke_account_session(self) -> None:
        self.use_case.revoke_account_session.return_value = ManagedAccountSessionRevocationResult(
            current_session_revoked=True,
        )

        response = self.api.post_revoke_admin_account_session(
            username="Admin",
            session_id="10000000000040008000000000000001",
        )

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"currentSessionRevoked": True}
        self.use_case.revoke_account_session.assert_called_once_with(
            params=ManagedAccountSessionRevokeOperationParams(
                target_username="Admin",
                current_username="test",
                target_session_id="10000000000040008000000000000001",
                current_session_id="10000000000040008000000000000001",
            ),
        )

    def test_revoke_all_account_sessions(self) -> None:
        self.use_case.revoke_all_account_sessions.return_value = (
            ManagedAccountSessionRevocationResult(current_session_revoked=True)
        )

        response = self.api.post_revoke_all_admin_account_sessions(username="test")

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"currentSessionRevoked": True}
        self.use_case.revoke_all_account_sessions.assert_called_once_with(
            params=ManagedAccountSessionsOperationParams(
                target_username="test",
                current_username="test",
                current_session_id="10000000000040008000000000000001",
                current_datetime=datetime(2026, 7, 8, 11, 30, tzinfo=UTC),
            ),
        )

    def test_revoke_other_account_sessions(self) -> None:
        self.use_case.revoke_other_account_sessions.return_value = (
            ManagedAccountSessionRevocationResult(current_session_revoked=False)
        )

        response = self.api.post_revoke_other_admin_account_sessions(username="test")

        self.asserts.status(response=response, expected_status=codes.OK)
        assert response.json() == {"currentSessionRevoked": False}
        self.use_case.revoke_other_account_sessions.assert_called_once_with(
            params=ManagedAccountSessionsRevokeOthersOperationParams(
                target_username="test",
                current_username="test",
                current_session_id="10000000000040008000000000000001",
            ),
        )

    def test_create_account_validates_payload(self) -> None:
        response = self.api.post_create_admin_account(
            data={
                "username": "bad-name",
                "role": "user",
                "password": "short",
                "isActive": True,
            },
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.create_account.assert_not_called()

    def test_create_account_rejects_owner_role_at_api_boundary(self) -> None:
        response = self.api.post_create_admin_account(
            data={
                "username": "SecondOwner",
                "role": "owner",
                "password": "password123",
                "isActive": True,
            },
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.create_account.assert_not_called()

    def test_list_accounts_requires_pagination_query_params_at_api_boundary(self) -> None:
        response = self.api.get_admin_accounts(page=None, page_size=None)

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.list_accounts.assert_not_called()

    def test_role_update_rejects_regular_user_role(self) -> None:
        response = self.api.put_admin_account_role(
            username="Moderator",
            data={"role": "user"},
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.update_role.assert_not_called()

    def test_role_update_rejects_owner_role_at_api_boundary(self) -> None:
        response = self.api.put_admin_account_role(
            username="Admin",
            data={"role": "owner"},
        )

        self.asserts.status(response=response, expected_status=codes.BAD_REQUEST)
        self.use_case.update_role.assert_not_called()

    def test_requires_authentication(self) -> None:
        response = self.no_auth_api.get_admin_accounts()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
        self.use_case.list_accounts.assert_not_called()

    def test_allows_owner_role(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="owner",
            role=RoleEnum.OWNER,
        )
        self.use_case.list_accounts.return_value = self.factory.core.managed_accounts()

        response = self.api.get_admin_accounts()

        self.asserts.status(response=response, expected_status=codes.OK)

    def test_requires_team_manager_role(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )

        response = self.api.get_admin_accounts()

        self.asserts.status(response=response, expected_status=codes.UNAUTHORIZED)
        self.use_case.list_accounts.assert_not_called()


def managed_account_session(session_id: str, *, is_current: bool) -> ManagedAccountSession:
    now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
    return ManagedAccountSession(
        id=session_id,
        client_metadata=AuthSessionClientMetadata(
            user_agent_display="Firefox on Linux",
            user_agent_browser="Firefox",
            user_agent_os="Linux",
            user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
        ),
        auth_method=AuthSessionAuthMethodEnum.PASSWORD,
        created_at=now - timedelta(days=1),
        last_used_at=now,
        expires_at=now + timedelta(days=30),
        is_current=is_current,
    )
