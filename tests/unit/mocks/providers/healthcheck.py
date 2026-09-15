from unittest.mock import Mock

from dishka import Provider, Scope, provide

from infra.healthcheck import ReadinessChecker


class MockHealthcheckProvider(Provider):
    def __init__(self) -> None:
        super().__init__()
        self.checker = Mock(spec=ReadinessChecker)

    @provide(scope=Scope.APP)
    async def provide_readiness_checker(self) -> ReadinessChecker:
        return self.checker
