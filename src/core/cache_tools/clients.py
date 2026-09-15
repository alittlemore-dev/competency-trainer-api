from abc import ABC, abstractmethod

from core.cache_tools.schemas import CacheWarmSummary


class CacheWarmExecutor(ABC):
    @abstractmethod
    async def warm_all(self) -> CacheWarmSummary:
        raise NotImplementedError
