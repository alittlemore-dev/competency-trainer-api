from litestar.connection import ASGIConnection
from litestar.handlers import BaseRouteHandler

from core.auth.exceptions import UnauthorizedError


class AdminUserGuard:
    def __call__(self, connection: ASGIConnection, _: BaseRouteHandler) -> None:
        if not connection.user.is_admin:
            raise UnauthorizedError


class OwnerGuard:
    def __call__(self, connection: ASGIConnection, _: BaseRouteHandler) -> None:
        if not connection.user.is_owner:
            raise UnauthorizedError


class TeamManagerGuard:
    def __call__(self, connection: ASGIConnection, _: BaseRouteHandler) -> None:
        if not connection.user.can_manage_team:
            raise UnauthorizedError


class ContentManagerGuard:
    def __call__(self, connection: ASGIConnection, _: BaseRouteHandler) -> None:
        if not connection.user.can_manage_content:
            raise UnauthorizedError


admin_user_guard = AdminUserGuard()
owner_guard = OwnerGuard()
team_manager_guard = TeamManagerGuard()
content_manager_guard = ContentManagerGuard()
