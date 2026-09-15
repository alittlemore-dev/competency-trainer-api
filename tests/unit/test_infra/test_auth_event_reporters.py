from unittest.mock import patch

from core.auth.enums import RoleEnum
from infra.auth.event_dispatchers import StructlogAuthEventReporter


class TestStructlogAuthEventReporter:
    def test_reports_login_user_not_found_without_raw_credentials(self) -> None:
        reporter = StructlogAuthEventReporter()

        with patch("infra.auth.event_dispatchers.logger") as mock_logger:
            reporter.report_login_user_not_found(username="test")

        mock_logger.warning.assert_called_once_with(
            event="No user in db from username form field",
            username="test",
        )

    def test_reports_role_denial_without_raw_credentials(self) -> None:
        reporter = StructlogAuthEventReporter()

        with patch("infra.auth.event_dispatchers.logger") as mock_logger:
            reporter.report_login_role_forbidden(
                username="test",
                required_role=RoleEnum.ADMIN,
            )

        mock_logger.warning.assert_called_once_with(
            "User has no role admin",
            username="test",
        )
