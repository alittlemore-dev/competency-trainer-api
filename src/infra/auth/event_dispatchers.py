from dataclasses import dataclass

from core.auth.enums import RoleEnum
from core.auth.event_dispatchers import AuthEventReporter
from infra.config.loggers import logger


@dataclass(frozen=True, slots=True)
class StructlogAuthEventReporter(AuthEventReporter):
    def report_login_user_not_found(self, *, username: str) -> None:
        logger.warning(event="No user in db from username form field", username=username)

    def report_login_role_forbidden(self, *, username: str, required_role: RoleEnum) -> None:
        logger.warning(f"User has no role {required_role.value}", username=username)

    def report_login_inactive_user(self, *, username: str) -> None:
        logger.warning(event="Inactive user requested login", username=username)

    def report_login_password_verification_failed(self, *, username: str) -> None:
        logger.warning(
            "incorrect credentials (passwords not suit)",
            username=username,
        )

    def report_authentication_revoked_token_used(self) -> None:
        logger.warning(event="Revoked token used for authentication")

    def report_authentication_user_not_found(self, *, username: str) -> None:
        logger.warning(event="No user in db from token payload", username=username)

    def report_authentication_role_forbidden(
        self,
        *,
        username: str,
        required_role: RoleEnum,
    ) -> None:
        logger.warning(f"User has no role {required_role.value}", username=username)

    def report_authentication_inactive_user(self, *, username: str) -> None:
        logger.warning(event="Inactive user used token for authentication", username=username)

    def report_logout_invalid_token(self) -> None:
        logger.warning(event="Logout requested with invalid token")

    def report_logout_token_without_remaining_lifetime(self) -> None:
        logger.warning(event="Logout requested with token that cannot be revoked")
