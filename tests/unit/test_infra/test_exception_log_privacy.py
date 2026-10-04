import sys
from uuid import uuid4

from structlog.dev import ConsoleRenderer

from infra.config.loggers import build_project_logging_config


def test_debug_exception_logs_exclude_credential_locals() -> None:
    config = build_project_logging_config(debug=True)
    renderer = next(item for item in config.processors if isinstance(item, ConsoleRenderer))
    credential = uuid4().hex
    supplied = uuid4().hex
    try:
        sensitive_request_failure(credential=credential, supplied=supplied)
    except RuntimeError:
        rendered = renderer(None, "error", {"event": "Request failed", "exc_info": sys.exc_info()})
    assert credential not in rendered
    assert supplied not in rendered
    assert "Request failed" in rendered
    assert "RuntimeError" in rendered


def sensitive_request_failure(*, credential: str, supplied: str) -> None:
    assert credential
    assert supplied
    message = "Request could not be completed"
    raise RuntimeError(message)
