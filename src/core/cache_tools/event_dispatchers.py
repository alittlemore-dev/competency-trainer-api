from abc import ABC, abstractmethod


class CacheWarmTaskDispatcher(ABC):
    @abstractmethod
    async def enqueue(self, *, operation_id: str) -> None:
        raise NotImplementedError
