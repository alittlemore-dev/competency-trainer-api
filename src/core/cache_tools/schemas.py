from dataclasses import dataclass
from datetime import datetime

from core.cache_tools.enums import CacheDomainEnum, CacheWarmOperationStatusEnum


@dataclass(kw_only=True, frozen=True, slots=True)
class CacheWarmSummary:
    attempted: int
    written: int
    skipped: int

    def as_dict(self) -> dict[str, int]:
        return {
            "attempted": self.attempted,
            "written": self.written,
            "skipped": self.skipped,
        }


@dataclass(kw_only=True, frozen=True, slots=True)
class CacheDomainStatus:
    domain: CacheDomainEnum
    key_count: int
    minimum_remaining_ttl_seconds: int | None
    non_expiring_key_count: int


@dataclass(kw_only=True, frozen=True, slots=True)
class CacheWarmOperation:
    operation_id: str
    status: CacheWarmOperationStatusEnum
    queued_at: datetime
    summary: CacheWarmSummary | None


@dataclass(kw_only=True, frozen=True, slots=True)
class CacheToolsStatus:
    enabled: bool
    configured_ttl_seconds: int
    scheduled_warm_interval_seconds: int
    domains: tuple[CacheDomainStatus, ...]
    last_manual_warm_operation: CacheWarmOperation | None


@dataclass(kw_only=True, frozen=True, slots=True)
class CacheToolsPolicy:
    enabled: bool
    configured_ttl_seconds: int
    scheduled_warm_interval_seconds: int
    domains: tuple[CacheDomainEnum, ...]
