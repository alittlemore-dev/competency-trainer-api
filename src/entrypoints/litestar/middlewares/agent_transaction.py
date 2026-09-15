from typing import cast

from dishka import AsyncContainer
from litestar.status_codes import HTTP_400_BAD_REQUEST
from litestar.types import ASGIApp, Message, Receive, Scope, Send

from infra.postgresql.transactions import DatabaseTransactionState


class AgentTransactionMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_container = cast("AsyncContainer", scope["state"]["dishka_container"])
        transaction_state = await request_container.get(DatabaseTransactionState)

        async def transaction_send(message: Message) -> None:
            if (
                message["type"] == "http.response.start"
                and message["status"] >= HTTP_400_BAD_REQUEST
            ):
                transaction_state.rollback_required = True
            await send(message)

        await self.app(scope, receive, transaction_send)
