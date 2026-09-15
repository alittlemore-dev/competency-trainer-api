from litestar import Litestar
from litestar.exceptions import ImproperlyConfiguredException

from entrypoints.litestar.response_cache import ResponseCacheDomainStore
from infra.config.constants import constants
from infra.config.loggers import logger
from infra.config.settings import settings


async def invalidate_cache_command(app: Litestar) -> None:
    if not settings.app.use_cache:
        return
    store = app.stores.get(constants.response_cache.store_name)
    if not isinstance(store, ResponseCacheDomainStore):
        msg = "Response cache store must be domain-routed."
        raise ImproperlyConfiguredException(msg)
    await store.delete_all()
    logger.info("Response cache invalidated.")
