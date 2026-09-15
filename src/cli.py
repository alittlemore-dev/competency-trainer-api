from litestar import Litestar

from entrypoints.litestar.initializers.main import create_cli_app
from entrypoints.litestar.lifespan.main import app_lifespan
from infra.ioc.container import container


def create_cli() -> Litestar:
    return create_cli_app(lifespan=[app_lifespan], container=container)
