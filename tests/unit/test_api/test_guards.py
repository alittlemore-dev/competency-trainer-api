from typing import Any, cast
from unittest.mock import Mock

import pytest
from litestar.connection import ASGIConnection
from litestar.handlers import BaseRouteHandler

from core.identity import RoleEnum, UnauthorizedError, UserIdentity
from entrypoints.litestar.guards import (
    content_manager_guard,
    owner_guard,
    team_manager_guard,
)


class FakeConnection:
    def __init__(self, user: UserIdentity) -> None:
        self.user = user


def make_connection(user: UserIdentity) -> ASGIConnection[Any, Any, Any, Any]:
    return cast("ASGIConnection[Any, Any, Any, Any]", FakeConnection(user))


def make_route_handler() -> BaseRouteHandler:
    return cast("BaseRouteHandler", Mock())


class TestGuards:
    def test_owner_guard_allows_owner(self) -> None:
        connection = make_connection(UserIdentity(username="owner", role=RoleEnum.OWNER))

        owner_guard(connection, make_route_handler())

    @pytest.mark.parametrize(
        "role",
        [RoleEnum.ANON, RoleEnum.USER, RoleEnum.MODERATOR, RoleEnum.ADMIN],
    )
    def test_owner_guard_rejects_every_non_owner_role(self, role: RoleEnum) -> None:
        connection = make_connection(UserIdentity(username=role.value, role=role))

        with pytest.raises(UnauthorizedError):
            owner_guard(connection, make_route_handler())

    @pytest.mark.parametrize("role", [RoleEnum.OWNER, RoleEnum.ADMIN])
    def test_team_manager_guard_allows_team_roles(self, role: RoleEnum) -> None:
        connection = make_connection(UserIdentity(username=role.value, role=role))

        team_manager_guard(connection, make_route_handler())

    def test_team_manager_guard_rejects_moderator(self) -> None:
        admin_connection = make_connection(UserIdentity(username="admin", role=RoleEnum.ADMIN))
        moderator_connection = make_connection(
            UserIdentity(username="moderator", role=RoleEnum.MODERATOR),
        )

        team_manager_guard(admin_connection, make_route_handler())
        with pytest.raises(UnauthorizedError):
            team_manager_guard(moderator_connection, make_route_handler())

    @pytest.mark.parametrize("role", [RoleEnum.OWNER, RoleEnum.ADMIN, RoleEnum.MODERATOR])
    def test_content_manager_guard_allows_content_roles(self, role: RoleEnum) -> None:
        connection = make_connection(UserIdentity(username=role.value, role=role))

        content_manager_guard(connection, make_route_handler())

    def test_content_manager_guard_rejects_regular_user(self) -> None:
        connection = make_connection(UserIdentity(username="user", role=RoleEnum.USER))

        with pytest.raises(UnauthorizedError):
            content_manager_guard(connection, make_route_handler())
