from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser


class TestRoles:
    def test_owner_has_all_roles_and_team_access(self) -> None:
        user = JwtUser(username="owner", role=RoleEnum.OWNER)

        assert user.is_owner is True
        assert user.is_admin is False
        assert user.can_manage_team is True
        assert user.can_manage_content is True
        assert user.has_role(RoleEnum.OWNER) is True
        assert user.has_role(RoleEnum.ADMIN) is True
        assert user.has_role(RoleEnum.MODERATOR) is True
        assert user.has_role(RoleEnum.USER) is True
        assert user.has_role(RoleEnum.ANON) is True

    def test_admin_has_team_and_content_access_without_owner_role(self) -> None:
        user = JwtUser(username="admin", role=RoleEnum.ADMIN)

        assert user.is_owner is False
        assert user.is_admin is True
        assert user.can_manage_team is True
        assert user.can_manage_content is True
        assert user.has_role(RoleEnum.OWNER) is False
        assert user.has_role(RoleEnum.ADMIN) is True
        assert user.has_role(RoleEnum.MODERATOR) is True
        assert user.has_role(RoleEnum.USER) is True
        assert user.has_role(RoleEnum.ANON) is True

    def test_moderator_has_content_access_without_admin_access(self) -> None:
        user = JwtUser(username="moderator", role=RoleEnum.MODERATOR)

        assert user.is_moderator is True
        assert user.is_admin is False
        assert user.can_manage_team is False
        assert user.can_manage_content is True
        assert user.has_role(RoleEnum.OWNER) is False
        assert user.has_role(RoleEnum.ADMIN) is False
        assert user.has_role(RoleEnum.MODERATOR) is True
        assert user.has_role(RoleEnum.USER) is True
        assert user.has_role(RoleEnum.ANON) is True

    def test_regular_user_does_not_have_content_or_admin_access(self) -> None:
        user = JwtUser(username="user", role=RoleEnum.USER)

        assert user.can_manage_team is False
        assert user.can_manage_content is False
        assert user.has_role(RoleEnum.OWNER) is False
        assert user.has_role(RoleEnum.MODERATOR) is False
        assert user.has_role(RoleEnum.ADMIN) is False
