import uuid

import structlog.contextvars
from litestar.middleware import ASGIMiddleware
from litestar.types import ASGIApp, Receive, Scope, Send

from infra.config.loggers import logger


class RequestIdLoggingMiddleware(ASGIMiddleware):
    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        structlog.contextvars.unbind_contextvars("request_id")
        structlog.contextvars.bind_contextvars(request_id=uuid.uuid4().__str__())
        await next_app(scope, receive, send)


class LogExceptionMiddleware(ASGIMiddleware):
    async def handle(self, scope: Scope, receive: Receive, send: Send, next_app: ASGIApp) -> None:
        try:
            await next_app(scope, receive, send)
        except Exception as exc:
            logger.exception(str(exc))
            raise
