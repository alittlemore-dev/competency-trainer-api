# ruff: noqa: S106
from typing import cast

import pytest
import pytest_asyncio
from sqlalchemy import Table
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.account.exceptions import ManagedAccountNotFoundError
from core.account.schemas import ManagedAccount, ManagedAccountFilters
from core.auth.enums import RoleEnum
from core.auth.exceptions import UserNotFoundError
from infra.postgresql.models import UserModel
from infra.postgresql.storages.users import UserAccountDatabaseStorage
from tests.test_cases import StorageTestCase


class TestUserAccountStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.storage = UserAccountDatabaseStorage(session=session)
        await self.storage_helper.create_users(
            users=[
                self.factory.core.user(
                    username="owner",
                    password_hash="password0",
                    role=RoleEnum.OWNER,
                    is_active=True,
                ),
                self.factory.core.user(
                    username="user1",
                    password_hash="password1",
                    role=RoleEnum.USER,
                ),
                self.factory.core.user(
                    username="user2",
                    password_hash="password2",
                    role=RoleEnum.ADMIN,
                    is_active=True,
                ),
                self.factory.core.user(
                    username="moderator",
                    password_hash="password3",
                    role=RoleEnum.MODERATOR,
                    is_active=False,
                ),
            ],
        )

    async def test_get_user_by_username_not_found(self) -> None:
        with pytest.raises(UserNotFoundError):
            await self.storage.get_user_by_username(username="NOT_FOUND")

    async def test_get_user_by_username(self) -> None:
        user = await self.storage.get_user_by_username(username="user1")
        assert user == self.factory.core.user(
            username="user1",
            password_hash="password1",
            role=RoleEnum.USER,
        )

    async def test_get_user_by_username_is_case_insensitive(self) -> None:
        user = await self.storage.get_user_by_username(username="USER2")

        assert user == self.factory.core.user(
            username="user2",
            password_hash="password2",
            role=RoleEnum.ADMIN,
        )

    async def test_get_user_by_username_returns_moderator_role(self) -> None:
        user = await self.storage.get_user_by_username(username="moderator")

        assert user == self.factory.core.user(
            username="moderator",
            password_hash="password3",
            role=RoleEnum.MODERATOR,
            is_active=False,
        )

    async def test_list_managed_accounts_excludes_regular_users(self) -> None:
        accounts, total_count = await self.storage.list_managed_accounts(
            filters=ManagedAccountFilters(page=1, page_size=10),
        )

        assert accounts == [
            ManagedAccount(username="moderator", role=RoleEnum.MODERATOR, is_active=False),
            ManagedAccount(username="owner", role=RoleEnum.OWNER, is_active=True),
            ManagedAccount(username="user2", role=RoleEnum.ADMIN, is_active=True),
        ]
        assert total_count == 3

    async def test_get_managed_account_rejects_regular_user(self) -> None:
        with pytest.raises(ManagedAccountNotFoundError):
            await self.storage.get_managed_account(username="user1")

    async def test_get_managed_account_is_case_insensitive(self) -> None:
        account = await self.storage.get_managed_account(username="USER2")

        assert account == ManagedAccount(username="user2", role=RoleEnum.ADMIN, is_active=True)

    async def test_create_managed_account_preserves_display_username(self) -> None:
        account = await self.storage.create_managed_account(
            username="Admin_Two",
            role=RoleEnum.ADMIN,
            password_hash="password4",
            is_active=True,
        )

        assert account == ManagedAccount(username="Admin_Two", role=RoleEnum.ADMIN, is_active=True)
        stored_user = await self.storage.get_user_by_username(username="admin_two")
        assert stored_user == self.factory.core.user(
            username="Admin_Two",
            password_hash="password4",
            role=RoleEnum.ADMIN,
        )

    async def test_create_managed_account_enforces_case_insensitive_username_uniqueness(
        self,
    ) -> None:
        with pytest.raises(IntegrityError):
            await self.storage.create_managed_account(
                username="USER2",
                role=RoleEnum.ADMIN,
                password_hash="password4",
                is_active=True,
            )

    async def test_update_managed_account_role(self) -> None:
        account = await self.storage.update_managed_account_role(
            username="MODERATOR",
            role=RoleEnum.ADMIN,
        )

        assert account == ManagedAccount(username="moderator", role=RoleEnum.ADMIN, is_active=False)

    async def test_update_managed_account_password(self) -> None:
        account = await self.storage.update_managed_account_password(
            username="MODERATOR",
            password_hash="new-password",
        )

        assert account == ManagedAccount(
            username="moderator",
            role=RoleEnum.MODERATOR,
            is_active=False,
        )
        stored_user = await self.storage.get_user_by_username(username="moderator")
        assert stored_user.password_hash.get_secret_value() == "new-password"

    async def test_activate_managed_account(self) -> None:
        account = await self.storage.activate_managed_account(username="MODERATOR")

        assert account == ManagedAccount(
            username="moderator",
            role=RoleEnum.MODERATOR,
            is_active=True,
        )

    async def test_deactivate_managed_account(self) -> None:
        account = await self.storage.deactivate_managed_account(username="USER2")

        assert account == ManagedAccount(username="user2", role=RoleEnum.ADMIN, is_active=False)

    async def test_delete_managed_account(self) -> None:
        await self.storage.delete_managed_account(username="MODERATOR")

        with pytest.raises(ManagedAccountNotFoundError):
            await self.storage.get_managed_account(username="moderator")

    async def test_single_owner_unique_index_rejects_second_owner(self) -> None:
        with pytest.raises(IntegrityError):
            await self.storage.create_managed_account(
                username="Owner_Two",
                role=RoleEnum.OWNER,
                password_hash="password4",
                is_active=True,
            )

    async def test_user_model_declares_managed_account_indexes(self) -> None:
        user_table = cast("Table", UserModel.__table__)

        assert {index.name for index in user_table.indexes} >= {
            "users_username_lower_uniq",
            "users_managed_accounts_list_idx",
            "users_single_owner_uniq",
        }
