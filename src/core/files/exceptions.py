from core.exceptions import DomainError


class InvalidFileDataError(DomainError):
    message = "File data is invalid."


class ContentTypeNotAllowedError(InvalidFileDataError):
    message = "Content type is not allowed."

    def __init__(self, *, content_type: str) -> None:
        self.message = f"Content type '{content_type}' is not allowed."
        super().__init__()


class FileSizeTooLargeError(InvalidFileDataError):
    message = "File size is too large."

    def __init__(self, *, size_bytes: int, max_size_bytes: int) -> None:
        self.message = f"File size {size_bytes} exceeds limit {max_size_bytes}."
        super().__init__()


class NamespaceNotAllowedError(InvalidFileDataError):
    message = "Namespace not allowed."

    def __init__(self, *, namespace: str) -> None:
        self.message = f"Namespace '{namespace}' is not allowed."
        super().__init__()


class FilePurposeNotAllowedError(InvalidFileDataError):
    message = "File purpose is not allowed."


class FileNameInvalidError(InvalidFileDataError):
    message = "File name is invalid."


class FileImageOptimizationError(InvalidFileDataError):
    message = "File image data is invalid."


class FileClientInternalError(DomainError):
    message = "File client error"

    def __init__(self, *, message: str) -> None:
        self.message = message
        super().__init__()


class FileInUseError(DomainError):
    message = "File is used and cannot be deleted."
