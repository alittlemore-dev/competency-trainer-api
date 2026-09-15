from core.exceptions import DomainError, EntryNotFoundError


class ArticleNotFoundError(EntryNotFoundError):
    message = "Article not found"


class TagNotFoundError(EntryNotFoundError):
    message = "Tag not found"


class ArticleFolderNotFoundError(EntryNotFoundError):
    message = "Article folder not found"


class ArticleFolderAlreadyExistsError(DomainError):
    message = "Article folder already exists"


class ArticleFolderPriorityInvalidError(DomainError):
    message = "Article folder priority order is invalid"
