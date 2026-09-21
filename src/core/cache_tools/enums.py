from enum import StrEnum


class CacheDomainEnum(StrEnum):
    ARTICLES = "articles"
    COMPETENCY_MATRIX = "competency_matrix"


class CacheWarmOperationStatusEnum(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
