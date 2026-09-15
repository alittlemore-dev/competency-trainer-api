from dataclasses import dataclass

from entrypoints.litestar.response_cache import ResponseCacheDomainStore
from entrypoints.taskiq.cache_warm.targets import CacheWarmTarget
from infra.config.constants import constants


@dataclass(frozen=True, slots=True)
class ResponseCacheWarmWriter:
    store: ResponseCacheDomainStore

    async def write_target(self, target: CacheWarmTarget) -> None:
        await self.store.set(
            key=target.build_cache_key(),
            value=target.response_cache_payload(),
            expires_in=constants.response_cache.default_ttl_seconds,
        )
