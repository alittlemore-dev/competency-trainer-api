# ruff: noqa: S106
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, call

import pytest
import pytest_asyncio

from core.account.enums import ManagedAccountActionEnum
from core.account.exceptions import (
    AccountUsernameAlreadyExistsError,
    InvalidManagedAccountRoleError,
    ManagedAccountActionForbiddenError,
    ManagedAccountNotFoundError,
    SelfAccountActionForbiddenError,
)
from core.account.schemas import (
    ManagedAccount,
    ManagedAccountCreateOperationParams,
    ManagedAccountCreateParams,
    ManagedAccountFilters,
    ManagedAccountPasswordUpdateOperationParams,
    ManagedAccountPasswordUpdateParams,
    ManagedAccountRoleUpdateOperationParams,
    ManagedAccountRoleUpdateParams,
    ManagedAccounts,
    ManagedAccountSessionRevokeOperationParams,
    ManagedAccountSessionsOperationParams,
    ManagedAccountSessionsRevokeOthersOperationParams,
    ManagedAccountTargetOperationParams,
)
from core.account.storages import ManagedAccountStorage
from core.account.use_cases import AccountsUseCase
from core.auth.enums import AuthSessionAuthMethodEnum, AuthSessionDeviceTypeEnum, RoleEnum
from core.auth.exceptions import UserNotFoundError
from core.auth.password_hashers import PasswordHasher
from core.auth.schemas import AuthSession, AuthSessionClientMetadata
from core.auth.storages import AuthSessionStorage
from core.auth.types import SessionSecretHash
from core.schemas import Secret
from tests.test_cases import TestCase


class TestManagedAccount(TestCase):
    @pytest.mark.parametrize(
        "action_name",
        [
            "UPDATE_ROLE",
            "ACTIVATE",
            "DEACTIVATE",
            "DELETE",
        ],
    )
    def test_forbids_self_management_actions(self, action_name: str) -> None:
        account = ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True)

        with pytest.raises(SelfAccountActionForbiddenError):
            account.ensure_can_manage_account(
                target=ManagedAccount(username="owner", role=RoleEnum.OWNER, is_active=True),
                action=getattr(ManagedAccountActionEnum, action_name),
            )

    def test_allows_self_password_update(self) -> None:
        account = ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True)

        account.ensure_can_manage_account(
            target=ManagedAccount(username="owner", role=RoleEnum.OWNER, is_active=True),
            action=ManagedAccountActionEnum.UPDATE_PASSWORD,
        )

    def test_owner_can_manage_admin_accounts(self) -> None:
        owner = ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True)

        owner.ensure_can_manage_account(
            target=ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            action=ManagedAccountActionEnum.DEACTIVATE,
        )

    def test_admin_can_manage_moderator_accounts(self) -> None:
        admin = ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True)

        admin.ensure_can_manage_account(
            target=ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            action=ManagedAccountActionEnum.UPDATE_PASSWORD,
        )

    @pytest.mark.parametrize("target_role", [RoleEnum.OWNER, RoleEnum.ADMIN])
    def test_admin_cannot_manage_owner_or_admin_accounts(self, target_role: RoleEnum) -> None:
        admin = ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True)

        with pytest.raises(ManagedAccountActionForbiddenError):
            admin.ensure_can_manage_account(
                target=ManagedAccount(username="Target", role=target_role, is_active=True),
                action=ManagedAccountActionEnum.UPDATE_PASSWORD,
            )

    @pytest.mark.parametrize(
        ("account", "expected"),
        [
            (ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True), True),
            (ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=False), False),
            (ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True), False),
            (ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True), False),
        ],
    )
    def test_is_active_owner(self, account: ManagedAccount, expected: bool) -> None:
        assert account.is_active_owner is expected


class TestAccountsUseCase(TestCase):
    @pytest_asyncio.fixture(autouse=True, loop_scope="session")
    async def setup(self) -> None:
        self.now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
        self.storage = Mock(spec=ManagedAccountStorage)
        self.auth_session_storage = Mock(spec=AuthSessionStorage)
        self.hasher = Mock(spec=PasswordHasher)
        self.hasher.hash_password.return_value = "hashed-password"
        self.use_case = AccountsUseCase(
            storage=self.storage,
            hasher=self.hasher,
            auth_session_storage=self.auth_session_storage,
        )

    async def test_list_accounts_builds_page(self) -> None:
        filters = ManagedAccountFilters(page=2, page_size=10)
        account = ManagedAccount(
            username="Admin",
            role=RoleEnum.ADMIN,
            is_active=True,
        )
        self.storage.list_managed_accounts.return_value = ([account], 11)

        accounts = await self.use_case.list_accounts(filters=filters)

        assert accounts == ManagedAccounts(values=[account], total_count=11, total_pages=2)
        self.storage.list_managed_accounts.assert_called_once_with(filters=filters)

    async def test_list_account_sessions_marks_current_session_after_permission_check(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]
        self.auth_session_storage.list_user_sessions.return_value = [
            auth_session(session_id="session-current"),
            auth_session(session_id="session-other"),
        ]

        sessions = await self.use_case.list_account_sessions(
            params=ManagedAccountSessionsOperationParams(
                target_username="Moderator",
                current_username="Admin",
                current_session_id="session-current",
                current_datetime=self.now,
            ),
        )

        assert [session.id for session in sessions.values] == ["session-current", "session-other"]
        assert [session.is_current for session in sessions.values] == [True, False]
        self.auth_session_storage.list_user_sessions.assert_called_once_with(
            username="Moderator",
            active_at=self.now,
        )

    async def test_admin_cannot_list_other_admin_sessions(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="OtherAdmin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.list_account_sessions(
                params=ManagedAccountSessionsOperationParams(
                    target_username="OtherAdmin",
                    current_username="Admin",
                    current_session_id="session-current",
                    current_datetime=self.now,
                ),
            )

        self.auth_session_storage.list_user_sessions.assert_not_called()

    async def test_revoke_account_session_reports_when_current_session_was_revoked(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        result = await self.use_case.revoke_account_session(
            params=ManagedAccountSessionRevokeOperationParams(
                target_username="Admin",
                current_username="Admin",
                target_session_id="session-current",
                current_session_id="session-current",
            ),
        )

        assert result.current_session_revoked is True
        self.auth_session_storage.revoke_user_session.assert_called_once_with(
            username="Admin",
            session_id="session-current",
        )

    async def test_revoke_all_account_sessions_reports_current_session_for_self(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True),
            ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True),
        ]

        result = await self.use_case.revoke_all_account_sessions(
            params=ManagedAccountSessionsOperationParams(
                target_username="Owner",
                current_username="Owner",
                current_session_id="session-current",
                current_datetime=self.now,
            ),
        )

        assert result.current_session_revoked is True
        self.auth_session_storage.revoke_user_sessions.assert_called_once_with(username="Owner")

    async def test_revoke_other_account_sessions_is_self_only(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.revoke_other_account_sessions(
                params=ManagedAccountSessionsRevokeOthersOperationParams(
                    target_username="Moderator",
                    current_username="Admin",
                    current_session_id="session-current",
                ),
            )

        self.auth_session_storage.revoke_user_sessions_except.assert_not_called()

    async def test_revoke_other_account_sessions_preserves_current_session_for_self(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        result = await self.use_case.revoke_other_account_sessions(
            params=ManagedAccountSessionsRevokeOthersOperationParams(
                target_username="Admin",
                current_username="Admin",
                current_session_id="session-current",
            ),
        )

        assert result.current_session_revoked is False
        self.auth_session_storage.revoke_user_sessions_except.assert_called_once_with(
            username="Admin",
            except_session_id="session-current",
        )

    async def test_create_account_rejects_regular_user_role(self) -> None:
        params = ManagedAccountCreateParams(
            username="Writer",
            role=RoleEnum.USER,
            password=Secret("password123"),
            is_active=True,
        )
        self.storage.get_managed_account.return_value = ManagedAccount(
            username="Owner",
            role=RoleEnum.OWNER,
            is_active=True,
        )

        with pytest.raises(InvalidManagedAccountRoleError):
            await self.use_case.create_account(
                params=ManagedAccountCreateOperationParams(
                    create_params=params,
                    current_username="Owner",
                ),
            )

        self.storage.create_managed_account.assert_not_called()

    async def test_create_account_rejects_owner_role(self) -> None:
        params = ManagedAccountCreateParams(
            username="SecondOwner",
            role=RoleEnum.OWNER,
            password=Secret("password123"),
            is_active=True,
        )
        self.storage.get_managed_account.return_value = ManagedAccount(
            username="Owner",
            role=RoleEnum.OWNER,
            is_active=True,
        )

        with pytest.raises(InvalidManagedAccountRoleError):
            await self.use_case.create_account(
                params=ManagedAccountCreateOperationParams(
                    create_params=params,
                    current_username="Owner",
                ),
            )

        self.storage.create_managed_account.assert_not_called()

    async def test_admin_cannot_create_admin_account(self) -> None:
        params = ManagedAccountCreateParams(
            username="AdminTwo",
            role=RoleEnum.ADMIN,
            password=Secret("password123"),
            is_active=True,
        )
        self.storage.get_managed_account.return_value = ManagedAccount(
            username="Admin",
            role=RoleEnum.ADMIN,
            is_active=True,
        )

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.create_account(
                params=ManagedAccountCreateOperationParams(
                    create_params=params,
                    current_username="Admin",
                ),
            )

        self.storage.create_managed_account.assert_not_called()

    async def test_create_account_rejects_existing_username_case_insensitively(self) -> None:
        params = ManagedAccountCreateParams(
            username="Admin",
            role=RoleEnum.ADMIN,
            password=Secret("password123"),
            is_active=True,
        )
        self.storage.get_managed_account.return_value = ManagedAccount(
            username="Owner",
            role=RoleEnum.OWNER,
            is_active=True,
        )
        self.storage.get_user_by_username.return_value = self.factory.core.user(
            username="admin",
            role=RoleEnum.ADMIN,
        )

        with pytest.raises(AccountUsernameAlreadyExistsError):
            await self.use_case.create_account(
                params=ManagedAccountCreateOperationParams(
                    create_params=params,
                    current_username="Owner",
                ),
            )

        self.storage.get_managed_account.assert_called_once_with(username="Owner")
        self.storage.get_user_by_username.assert_called_once_with(username="Admin")
        self.storage.create_managed_account.assert_not_called()

    async def test_owner_creates_admin_account(self) -> None:
        params = ManagedAccountCreateParams(
            username="Admin_1",
            role=RoleEnum.ADMIN,
            password=Secret("password123"),
            is_active=True,
        )
        created_account = ManagedAccount(
            username="Admin_1",
            role=RoleEnum.ADMIN,
            is_active=True,
        )
        self.storage.get_managed_account.return_value = ManagedAccount(
            username="Owner",
            role=RoleEnum.OWNER,
            is_active=True,
        )
        self.storage.get_user_by_username.side_effect = UserNotFoundError
        self.storage.create_managed_account.return_value = created_account

        account = await self.use_case.create_account(
            params=ManagedAccountCreateOperationParams(
                create_params=params,
                current_username="Owner",
            ),
        )

        assert account == created_account
        self.storage.create_managed_account.assert_called_once_with(
            username="Admin_1",
            role=RoleEnum.ADMIN,
            password_hash="hashed-password",
            is_active=True,
        )

    async def test_admin_creates_moderator_account(self) -> None:
        params = ManagedAccountCreateParams(
            username="Moderator_1",
            role=RoleEnum.MODERATOR,
            password=Secret("password123"),
            is_active=True,
        )
        created_account = ManagedAccount(
            username="Moderator_1",
            role=RoleEnum.MODERATOR,
            is_active=True,
        )
        self.storage.get_managed_account.return_value = ManagedAccount(
            username="Admin",
            role=RoleEnum.ADMIN,
            is_active=True,
        )
        self.storage.get_user_by_username.side_effect = UserNotFoundError
        self.storage.create_managed_account.return_value = created_account

        account = await self.use_case.create_account(
            params=ManagedAccountCreateOperationParams(
                create_params=params,
                current_username="Admin",
            ),
        )

        assert account == created_account
        self.hasher.hash_password.assert_called_once_with("password123")
        self.storage.create_managed_account.assert_called_once_with(
            username="Moderator_1",
            role=RoleEnum.MODERATOR,
            password_hash="hashed-password",
            is_active=True,
        )

    async def test_update_role_rejects_self_action(self) -> None:
        params = ManagedAccountRoleUpdateParams(role=RoleEnum.MODERATOR)
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(SelfAccountActionForbiddenError):
            await self.use_case.update_role(
                params=ManagedAccountRoleUpdateOperationParams(
                    target_username="Admin",
                    role_params=params,
                    current_username="admin",
                ),
            )

        self.storage.update_managed_account_role.assert_not_called()

    async def test_update_role_rejects_regular_user_role(self) -> None:
        params = ManagedAccountRoleUpdateParams(role=RoleEnum.USER)

        with pytest.raises(InvalidManagedAccountRoleError):
            await self.use_case.update_role(
                params=ManagedAccountRoleUpdateOperationParams(
                    target_username="Moderator",
                    role_params=params,
                    current_username="Admin",
                ),
            )

        self.storage.update_managed_account_role.assert_not_called()

    async def test_admin_cannot_promote_moderator_to_admin(self) -> None:
        params = ManagedAccountRoleUpdateParams(role=RoleEnum.ADMIN)
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.update_role(
                params=ManagedAccountRoleUpdateOperationParams(
                    target_username="Moderator",
                    role_params=params,
                    current_username="Admin",
                ),
            )

        self.storage.update_managed_account_role.assert_not_called()

    async def test_admin_cannot_update_moderator_role(self) -> None:
        params = ManagedAccountRoleUpdateParams(role=RoleEnum.MODERATOR)
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.update_role(
                params=ManagedAccountRoleUpdateOperationParams(
                    target_username="Moderator",
                    role_params=params,
                    current_username="Admin",
                ),
            )

        self.storage.update_managed_account_role.assert_not_called()

    async def test_owner_updates_admin_role(self) -> None:
        params = ManagedAccountRoleUpdateParams(role=RoleEnum.MODERATOR)
        updated_account = ManagedAccount(
            username="Admin",
            role=RoleEnum.MODERATOR,
            is_active=True,
        )
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True),
        ]
        self.storage.update_managed_account_role.return_value = updated_account

        account = await self.use_case.update_role(
            params=ManagedAccountRoleUpdateOperationParams(
                target_username="Admin",
                role_params=params,
                current_username="Owner",
            ),
        )

        assert account == updated_account
        self.storage.update_managed_account_role.assert_called_once_with(
            username="Admin",
            role=RoleEnum.MODERATOR,
        )

    async def test_update_password_allows_self_action(self) -> None:
        params = ManagedAccountPasswordUpdateParams(password=Secret("password123"))
        updated_account = ManagedAccount(
            username="Admin",
            role=RoleEnum.ADMIN,
            is_active=True,
        )
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]
        self.storage.update_managed_account_password.return_value = updated_account

        account = await self.use_case.update_password(
            params=ManagedAccountPasswordUpdateOperationParams(
                target_username="Admin",
                password_params=params,
                current_username="Admin",
            ),
        )

        assert account == updated_account
        assert self.storage.get_managed_account.call_args_list == [
            call(username="Admin"),
            call(username="Admin"),
        ]
        self.hasher.hash_password.assert_called_once_with("password123")
        self.storage.update_managed_account_password.assert_called_once_with(
            username="Admin",
            password_hash="hashed-password",
        )
        self.auth_session_storage.revoke_user_sessions.assert_called_once_with(username="Admin")

    async def test_update_password_requires_current_managed_account(self) -> None:
        params = ManagedAccountPasswordUpdateParams(password=Secret("password123"))
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccountNotFoundError,
        ]

        with pytest.raises(ManagedAccountNotFoundError):
            await self.use_case.update_password(
                params=ManagedAccountPasswordUpdateOperationParams(
                    target_username="Moderator",
                    password_params=params,
                    current_username="MissingAdmin",
                ),
            )

        self.storage.update_managed_account_password.assert_not_called()
        self.auth_session_storage.revoke_user_sessions.assert_not_called()

    async def test_update_password_does_not_revoke_sessions_when_storage_update_fails(self) -> None:
        params = ManagedAccountPasswordUpdateParams(password=Secret("password123"))
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]
        self.storage.update_managed_account_password.side_effect = ManagedAccountNotFoundError

        with pytest.raises(ManagedAccountNotFoundError):
            await self.use_case.update_password(
                params=ManagedAccountPasswordUpdateOperationParams(
                    target_username="Moderator",
                    password_params=params,
                    current_username="Admin",
                ),
            )

        self.auth_session_storage.revoke_user_sessions.assert_not_called()

    async def test_deactivate_rejects_self_action(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(SelfAccountActionForbiddenError):
            await self.use_case.deactivate_account(
                params=ManagedAccountTargetOperationParams(
                    target_username="Admin",
                    current_username="admin",
                ),
            )

        self.storage.deactivate_managed_account.assert_not_called()

    async def test_admin_cannot_deactivate_admin(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="OtherAdmin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.deactivate_account(
                params=ManagedAccountTargetOperationParams(
                    target_username="OtherAdmin",
                    current_username="Admin",
                ),
            )

        self.storage.deactivate_managed_account.assert_not_called()

    async def test_deactivate_revokes_target_sessions_after_deactivation(self) -> None:
        deactivated_account = ManagedAccount(
            username="Moderator",
            role=RoleEnum.MODERATOR,
            is_active=False,
        )
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]
        self.storage.deactivate_managed_account.return_value = deactivated_account

        account = await self.use_case.deactivate_account(
            params=ManagedAccountTargetOperationParams(
                target_username="Moderator",
                current_username="Admin",
            ),
        )

        assert account == deactivated_account
        self.auth_session_storage.revoke_user_sessions.assert_called_once_with(
            username="Moderator",
        )

    async def test_activate_delegates_to_storage(self) -> None:
        activated_account = ManagedAccount(
            username="Moderator",
            role=RoleEnum.MODERATOR,
            is_active=True,
        )
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=False),
            ManagedAccount(username="Owner", role=RoleEnum.OWNER, is_active=True),
        ]
        self.storage.activate_managed_account.return_value = activated_account

        account = await self.use_case.activate_account(
            params=ManagedAccountTargetOperationParams(
                target_username="Moderator",
                current_username="Owner",
            ),
        )

        assert account == activated_account
        assert self.storage.get_managed_account.call_args_list == [
            call(username="Moderator"),
            call(username="Owner"),
        ]
        self.storage.activate_managed_account.assert_called_once_with(username="Moderator")

    async def test_activate_rejects_self_action(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=False),
            ManagedAccount(username="admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(SelfAccountActionForbiddenError):
            await self.use_case.activate_account(
                params=ManagedAccountTargetOperationParams(
                    target_username="Admin",
                    current_username="admin",
                ),
            )

        self.storage.activate_managed_account.assert_not_called()

    async def test_delete_rejects_self_action(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(SelfAccountActionForbiddenError):
            await self.use_case.delete_account(
                params=ManagedAccountTargetOperationParams(
                    target_username="Admin",
                    current_username="admin",
                ),
            )

        self.storage.delete_managed_account.assert_not_called()

    async def test_admin_cannot_delete_admin(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="OtherAdmin", role=RoleEnum.ADMIN, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        with pytest.raises(ManagedAccountActionForbiddenError):
            await self.use_case.delete_account(
                params=ManagedAccountTargetOperationParams(
                    target_username="OtherAdmin",
                    current_username="Admin",
                ),
            )

        self.storage.delete_managed_account.assert_not_called()

    async def test_delete_revokes_target_sessions_after_delete(self) -> None:
        self.storage.get_managed_account.side_effect = [
            ManagedAccount(username="Moderator", role=RoleEnum.MODERATOR, is_active=True),
            ManagedAccount(username="Admin", role=RoleEnum.ADMIN, is_active=True),
        ]

        await self.use_case.delete_account(
            params=ManagedAccountTargetOperationParams(
                target_username="Moderator",
                current_username="Admin",
            ),
        )

        self.storage.delete_managed_account.assert_called_once_with(username="Moderator")
        self.auth_session_storage.revoke_user_sessions.assert_called_once_with(
            username="Moderator",
        )


def auth_session(session_id: str) -> AuthSession:
    now = datetime(2026, 7, 8, 11, 30, tzinfo=UTC)
    return AuthSession(
        id=session_id,
        username="Moderator",
        secret_hash=SessionSecretHash("a" * 64),
        expires_at=now + timedelta(days=30),
        absolute_expires_at=now + timedelta(days=30),
        is_revoked=False,
        created_at=now - timedelta(days=1),
        last_used_at=now,
        auth_method=AuthSessionAuthMethodEnum.PASSWORD,
        client_metadata=AuthSessionClientMetadata(
            user_agent_display="Firefox on Linux",
            user_agent_browser="Firefox",
            user_agent_os="Linux",
            user_agent_device=AuthSessionDeviceTypeEnum.DESKTOP,
        ),
    )
