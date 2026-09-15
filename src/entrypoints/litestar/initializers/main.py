from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager

from dishka import AsyncContainer
from dishka.integrations.litestar import setup_dishka
from litestar import Litestar, Router
from litestar.config.response_cache import ResponseCacheConfig
from litestar.logging import StructLoggingConfig
from litestar.middleware import DefineMiddleware
from litestar.middleware.logging import LoggingMiddleware, LoggingMiddlewareConfig
from litestar.openapi import OpenAPIConfig
from litestar.openapi.plugins import SwaggerRenderPlugin
from litestar.plugins import PluginProtocol
from litestar.plugins.pydantic import PydanticPlugin
from litestar.plugins.structlog import StructlogConfig, StructlogPlugin
from litestar.stores.base import Store
from litestar.stores.valkey import ValkeyStore
from litestar.types import Middleware

from entrypoints.litestar.api.agent_access.endpoints import agent_api_router
from entrypoints.litestar.api.routers import api_router
from entrypoints.litestar.cli.plugins import CLIPlugin
from entrypoints.litestar.exception_handlers import get_litestar_exception_handlers
from entrypoints.litestar.middlewares.agent_audit import AgentOutcomeAuditMiddleware
from entrypoints.litestar.middlewares.auth import AuthenticationMiddleware
from entrypoints.litestar.middlewares.logging import (
    LogExceptionMiddleware,
    RequestIdLoggingMiddleware,
)
from entrypoints.litestar.openapi_metadata import install_openapi_request_body_metadata
from entrypoints.litestar.public.endpoints import public_router
from entrypoints.litestar.response_cache import ResponseCacheDomain, ResponseCacheDomainStore
from infra.config import loggers
from infra.config.constants import constants
from infra.config.settings import settings

Lifespan = Sequence[Callable[[Litestar], AbstractAsyncContextManager] | AbstractAsyncContextManager]


def create_response_cache_domain_store() -> ResponseCacheDomainStore:
    return ResponseCacheDomainStore(
        stores={
            domain: ValkeyStore.with_client(
                url=settings.valkey.url_for_http_cache.get_secret_value(),
                db=constants.valkey.databases.response_cache,
                port=settings.valkey.port,
                namespace=f"{constants.valkey.namespaces.framework}_{domain.value}",
            )
            for domain in ResponseCacheDomain
        },
    )


def create_stores() -> dict[str, Store]:
    store_name = constants.response_cache.store_name
    response_cache_domain_store = (
        create_response_cache_domain_store() if settings.app.use_cache else None
    )
    return {
        **(
            {
                store_name: response_cache_domain_store,
                **{
                    f"{store_name}_{domain.value}": store
                    for domain, store in response_cache_domain_store.stores.items()
                },
            }
            if response_cache_domain_store is not None
            else {}
        ),
    }


def create_openapi_config() -> OpenAPIConfig:
    return OpenAPIConfig(
        title="docs",
        version="0.1.0",
        path="/api/docs",
        render_plugins=[SwaggerRenderPlugin()],
    )


def create_logging_middleware_config() -> LoggingMiddlewareConfig:
    return LoggingMiddlewareConfig(
        request_log_fields=["path", "method", "path_params"],
        response_log_fields=["status_code"],
        middleware_class=LoggingMiddleware,
    )


def create_plugins() -> list[PluginProtocol]:
    project_logging_config = loggers.build_project_logging_config(debug=settings.app.debug)
    logging_config = StructLoggingConfig(
        log_exceptions="always",
        processors=project_logging_config.processors,
        wrapper_class=project_logging_config.wrapper_class,
        logger_factory=project_logging_config.logger_factory,
        cache_logger_on_first_use=project_logging_config.cache_logger_on_first_use,
    )
    return [
        StructlogPlugin(
            config=StructlogConfig(
                structlog_logging_config=logging_config,
                middleware_logging_config=create_logging_middleware_config(),
            ),
        ),
        PydanticPlugin(prefer_alias=True),
    ]


def create_middlewares(container: AsyncContainer) -> list[Middleware]:
    return [
        RequestIdLoggingMiddleware(),
        LogExceptionMiddleware(),
        DefineMiddleware(
            AuthenticationMiddleware,
            token_header_name=settings.auth.token_header_name,
            token_prefix=settings.auth.token_prefix,
            container=container,
            exclude=["/api/docs"],
            exclude_from_auth_key="exclude_from_auth",
            exclude_http_methods=None,
            scopes=None,
        ),
    ]


def create_routers() -> list[Router]:
    return [api_router, public_router, agent_api_router]


def create_cli_app(
    lifespan: Lifespan,
    container: AsyncContainer,
) -> Litestar:
    loggers.configure_project_logging(debug=settings.app.debug)
    app = Litestar(
        lifespan=lifespan,
        debug=settings.app.debug,
        exception_handlers=get_litestar_exception_handlers(),
        stores=create_stores(),
        plugins=[CLIPlugin()],
        openapi_config=create_openapi_config(),
    )
    setup_dishka(container=container, app=app)
    return app


def create_litestar_app(
    lifespan: Lifespan,
    container: AsyncContainer,
    extra_plugins: Sequence[PluginProtocol],
    extra_middlewares: Sequence[Middleware],
) -> Litestar:
    loggers.configure_project_logging(debug=settings.app.debug)
    app = Litestar(
        route_handlers=create_routers(),
        lifespan=lifespan,
        debug=settings.app.debug,
        exception_handlers=get_litestar_exception_handlers(),
        stores=create_stores(),
        response_cache_config=(
            ResponseCacheConfig(store=constants.response_cache.store_name)
            if settings.app.use_cache
            else None
        ),
        middleware=[*create_middlewares(container), *extra_middlewares],
        plugins=[*create_plugins(), *extra_plugins],
        openapi_config=create_openapi_config(),
    )
    setup_dishka(container=container, app=app)
    app.asgi_handler = AgentOutcomeAuditMiddleware(
        app=app.asgi_handler,
        container=container,
    )
    install_openapi_request_body_metadata()
    return app
