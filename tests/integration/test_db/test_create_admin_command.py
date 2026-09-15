# ruff: noqa: S106
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.enums import RoleEnum
from entrypoints.litestar.cli.commands.admin import create_admin_command
from infra.postgresql.storages.users import UserAccountDatabaseStorage
from tests.test_cases import StorageTestCase


class TestCreateSuperuserCommand(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, session: AsyncSession) -> None:
        self.user_storage = UserAccountDatabaseStorage(session=session)

    async def test_existing_user_is_not_overwritten(self) -> None:
        existing_user = self.factory.core.user(
            username="admin",
            password_hash="existing-password-hash",
            role=RoleEnum.USER,
        )
        await self.storage_helper.create_user(existing_user)
        await self.db_session.commit()

        await create_admin_command(username="admin", password="new-password")
        self.db_session.expire_all()

        user = await self.user_storage.get_user_by_username(username="admin")

        assert user == existing_user

    async def test_new_superuser_is_created_as_owner(self) -> None:
        await create_admin_command(username="owner", password="new-password")
        self.db_session.expire_all()

        user = await self.user_storage.get_user_by_username(username="owner")

        assert user.role == RoleEnum.OWNER
        assert user.is_active is True
