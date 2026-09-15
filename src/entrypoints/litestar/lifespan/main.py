from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from litestar import Litestar

from infra.config.initializers import before_app_create


@asynccontextmanager
async def app_lifespan(app: Litestar) -> AsyncGenerator[None]:
    before_app_create()
    yield
    await app.state.dishka_container.close()
