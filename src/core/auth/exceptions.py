from core.exceptions import DomainError, EntryNotFoundError


class UnauthorizedError(DomainError):
    message = "Unauthorized error"


class ForbiddenError(DomainError):
    message = "Forbidden error"


class UserNotFoundError(EntryNotFoundError):
    message = "User not found"


class AuthSessionNotFoundError(EntryNotFoundError):
    message = "Auth session not found"
