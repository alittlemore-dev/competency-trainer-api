from core.exceptions import EntryNotFoundError


class CacheWarmOperationNotFoundError(EntryNotFoundError):
    message = "Cache warm operation not found"
