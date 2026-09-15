from litestar.middleware.logging import LoggingMiddleware

from entrypoints.litestar.initializers.main import create_logging_middleware_config


def test_request_logging_uses_standard_middleware_without_raw_query_values() -> None:
    config = create_logging_middleware_config()

    assert config.request_log_fields == ("path", "method", "path_params")
    assert config.middleware_class is LoggingMiddleware
