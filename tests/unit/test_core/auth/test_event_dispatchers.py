import inspect

from core.auth.event_dispatchers import AuthEventReporter


class TestAuthEventReporter:
    def test_is_abstract_domain_port(self) -> None:
        assert inspect.isabstract(AuthEventReporter)
