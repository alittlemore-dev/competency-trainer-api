from core.exceptions import EntryNotFoundError


class ContactMeRequestNotFoundError(EntryNotFoundError):
    message = "Contact me request not found"
