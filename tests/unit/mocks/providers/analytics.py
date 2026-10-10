from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.analytics.schemas import AnalyticsConfig, AnalyticsReport
from core.analytics.use_cases import AnalyticsUseCase
from core.schemas import Secret


class MockAnalyticsProvider(Provider):
    @provide(scope=Scope.APP)
    def provide_config(self) -> AnalyticsConfig:
        return AnalyticsConfig(
            secret=Secret("anonymous-analytics-test-secret"), receipt_retention_days=1
        )

    @provide(scope=Scope.APP)
    def provide_use_case(self) -> AnalyticsUseCase:
        mock = Mock(spec=AnalyticsUseCase)
        mock.get_report.return_value = AnalyticsReport(daily=[], current_reactions={})
        return mock
