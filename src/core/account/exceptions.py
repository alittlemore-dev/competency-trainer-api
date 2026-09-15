from core.exceptions import DomainError, EntryNotFoundError


class ManagedAccountNotFoundError(EntryNotFoundError):
    message = "Managed account not found"


class AccountUsernameAlreadyExistsError(DomainError):
    message = "Account username already exists"


class InvalidManagedAccountRoleError(DomainError):
    message = "Managed account role must be admin or moderator"


class SelfAccountActionForbiddenError(DomainError):
    message = "Cannot perform this action on your own account"


class ManagedAccountActionForbiddenError(DomainError):
    message = "Cannot perform this action on this managed account"
