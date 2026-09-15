from enum import StrEnum


class CacheDomainEnum(StrEnum):
    I18N = "i18n"
    ARTICLES = "articles"
    COMPETENCY_MATRIX = "competency_matrix"


class CacheWarmOperationStatusEnum(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
