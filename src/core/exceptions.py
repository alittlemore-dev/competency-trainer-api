class DomainError(Exception):
    message: str

    def __init__(self) -> None:
        super().__init__(self.message)

    def __str__(self) -> str:
        return self.message


class EntryNotFoundError(DomainError):
    message = "Entry not found"
