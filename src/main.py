from litestar import Litestar

from entrypoints.litestar.initializers.main import create_litestar_app
from entrypoints.litestar.lifespan.main import app_lifespan
from infra.ioc.container import container


def create_app() -> Litestar:
    return create_litestar_app(
        lifespan=[app_lifespan],
        container=container,
        extra_plugins=[],
        extra_middlewares=[],
    )
