from abc import ABC, abstractmethod

from core.cache_tools.enums import CacheDomainEnum
from core.cache_tools.schemas import CacheDomainStatus, CacheWarmOperation


class ResponseCacheStatusStorage(ABC):
    @abstractmethod
    async def get_domain_status(self, *, domain: CacheDomainEnum) -> CacheDomainStatus:
        raise NotImplementedError


class ResponseCacheInvalidationStorage(ABC):
    @abstractmethod
    async def clear_domains(self, *, domains: tuple[CacheDomainEnum, ...]) -> None:
        raise NotImplementedError


class CacheWarmOperationStorage(ABC):
    @abstractmethod
    async def create(self, *, operation: CacheWarmOperation) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update(self, *, operation: CacheWarmOperation) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get(self, *, operation_id: str) -> CacheWarmOperation | None:
        raise NotImplementedError

    @abstractmethod
    async def get_latest(self) -> CacheWarmOperation | None:
        raise NotImplementedError
