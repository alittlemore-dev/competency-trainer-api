from abc import ABC, abstractmethod

from core.auth.enums import RoleEnum


class AuthEventReporter(ABC):
    @abstractmethod
    def report_login_user_not_found(self, *, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_login_role_forbidden(self, *, username: str, required_role: RoleEnum) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_login_inactive_user(self, *, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_login_password_verification_failed(self, *, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_authentication_revoked_token_used(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_authentication_user_not_found(self, *, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_authentication_role_forbidden(
        self,
        *,
        username: str,
        required_role: RoleEnum,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_authentication_inactive_user(self, *, username: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_logout_invalid_token(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def report_logout_token_without_remaining_lifetime(self) -> None:
        raise NotImplementedError
