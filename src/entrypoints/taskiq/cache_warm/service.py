from collections.abc import Iterable
from dataclasses import dataclass

from core.cache_tools.clients import CacheWarmExecutor
from core.cache_tools.schemas import CacheWarmSummary
from entrypoints.litestar.response_cache import ResponseCacheDomain
from entrypoints.taskiq.cache_warm.targets import ResponseCacheWarmTargetCollector
from entrypoints.taskiq.cache_warm.writer import ResponseCacheWarmWriter

__all__ = ("CacheWarmSummary", "ResponseCacheWarmService")


@dataclass(frozen=True, slots=True)
class ResponseCacheWarmService(CacheWarmExecutor):
    target_collector: ResponseCacheWarmTargetCollector
    writer: ResponseCacheWarmWriter
    use_cache: bool
    supported_domains: tuple[ResponseCacheDomain, ...]

    async def warm_all(self) -> CacheWarmSummary:
        return await self.warm_domains(domains=self.supported_domains)

    async def warm_domain(self, *, domain: ResponseCacheDomain) -> CacheWarmSummary:
        if not self.can_warm_domain(domain=domain):
            return CacheWarmSummary(attempted=0, written=0, skipped=1)
        return await self.warm_domains(domains=(domain,))

    async def warm_domains(self, *, domains: Iterable[ResponseCacheDomain]) -> CacheWarmSummary:
        requested_domains = tuple(domains)
        warmable_domains = tuple(
            domain for domain in requested_domains if self.can_warm_domain(domain=domain)
        )
        skipped_domains_count = len(requested_domains) - len(warmable_domains)
        if not self.use_cache:
            return CacheWarmSummary(
                attempted=0,
                written=0,
                skipped=len(requested_domains),
            )

        targets = await self.target_collector.collect(domains=warmable_domains)
        for target in targets:
            await self.writer.write_target(target)
        return CacheWarmSummary(
            attempted=len(targets),
            written=len(targets),
            skipped=skipped_domains_count,
        )

    def can_warm_domain(self, *, domain: ResponseCacheDomain) -> bool:
        return domain in self.supported_domains
