from abc import ABC, abstractmethod
from datetime import date

from core.analytics.schemas import AnalyticsConfig, AnalyticsDaily, AnalyticsFilters, AnalyticsVisit


class AnalyticsStorage(ABC):
    @abstractmethod
    async def record_visit(
        self, *, visit: AnalyticsVisit, day: date, config: AnalyticsConfig
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_daily(self, *, filters: AnalyticsFilters) -> list[AnalyticsDaily]:
        raise NotImplementedError
