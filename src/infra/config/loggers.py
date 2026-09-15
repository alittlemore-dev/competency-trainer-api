import logging
from collections.abc import Callable
from dataclasses import dataclass

import ecs_logging
import structlog
from structlog.typing import BindableLogger, Processor, WrappedLogger


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectLoggingConfig:
    processors: list[Processor]
    wrapper_class: type[BindableLogger]
    logger_factory: Callable[..., WrappedLogger]
    cache_logger_on_first_use: bool


def build_project_logging_config(*, debug: bool) -> ProjectLoggingConfig:
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.UnicodeDecoder(),
        structlog.dev.set_exc_info,
        structlog.processors.StackInfoRenderer(),
    ]
    wrapper_class = structlog.make_filtering_bound_logger(logging.INFO)
    if debug:
        processors.extend(
            [
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
                structlog.dev.ConsoleRenderer(),
            ],
        )
        wrapper_class = structlog.make_filtering_bound_logger(logging.DEBUG)
    else:
        processors.append(ecs_logging.StructlogFormatter())  # type: ignore[arg-type]
    return ProjectLoggingConfig(
        processors=processors,
        wrapper_class=wrapper_class,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def configure_project_logging(*, debug: bool) -> ProjectLoggingConfig:
    config = build_project_logging_config(debug=debug)
    structlog.configure(
        processors=config.processors,
        wrapper_class=config.wrapper_class,
        logger_factory=config.logger_factory,
        cache_logger_on_first_use=config.cache_logger_on_first_use,
    )
    return config


logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def log_sanitized_exception(*, event: str, error: Exception, **safe_context: object) -> None:
    logger.error(
        event,
        exception_type=type(error).__name__,
        **safe_context,
    )
