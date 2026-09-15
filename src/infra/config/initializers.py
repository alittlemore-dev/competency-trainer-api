import asyncio

import pem
import sentry_sdk
from sentry_sdk.integrations.litestar import LitestarIntegration

from infra.config.loggers import logger
from infra.config.settings import settings
from infra.postgresql.utils import migrate


def init_sentry() -> None:
    if not settings.sentry.use:
        # Keep local development from sending events to Sentry; production enables it explicitly.
        # The debug flag is enough because this project currently has only local and
        # production modes.
        return
    sentry_sdk.init(
        dsn=settings.sentry.dsn,
        send_default_pii=True,
        traces_sample_rate=1.0,
        enable_logs=True,
        profile_lifecycle="trace",
        integrations=[LitestarIntegration()],
    )


def check_certs_exists() -> None:
    if not pem.parse(settings.auth.public_key.get_secret_value()):
        msg = "Public key certificate is not valid. Check your .env file or environment variables."
        raise RuntimeError(msg)
    if not pem.parse(settings.auth.private_key.get_secret_value()):
        msg = "Private key certificate is not valid. Check your .env file or environment variables."
        raise RuntimeError(msg)


async def monitor_event_loop_lag(loop: asyncio.AbstractEventLoop) -> None:
    start = loop.time()
    sleep_interval = 1
    current_coro_name = "monitor_event_loop_lag"
    coro_name = "RequestResponseCycle.run_asgi"
    not_detected_code = "NOT_DETECTED"

    while loop.is_running():
        await asyncio.sleep(sleep_interval)
        diff = loop.time() - start
        lag = diff - sleep_interval
        if lag > 1:
            coros = {
                task._coro.cr_code.co_qualname: task  # type: ignore[attr-defined]  # noqa: SLF001
                for task in asyncio.all_tasks(loop)
                if task._coro.cr_code.co_name != current_coro_name  # type: ignore[attr-defined]  # noqa: SLF001
            }
            coro_names = ", ".join(coros.keys())
            call_graph = (
                asyncio.format_call_graph(coros[coro_name])
                if coro_name in coros
                else not_detected_code
            )
            if call_graph == not_detected_code:
                msg = (
                    "Call graph with running endpoint not detected. "
                    "Maybe it changed due to framework update"
                )
                logger.warning(msg, all_coros=coro_names)
            logger.warning(
                "Event loop has lag",
                lag=lag,
                coroutine_names=coro_names,
                call_graph=call_graph,
            )
        start = loop.time()


def before_app_create() -> None:
    loop = asyncio.get_running_loop()
    init_sentry()
    check_certs_exists()
    # TODO: move migrate to separated task in docker-compose
    migrate("head")
    loop.create_task(monitor_event_loop_lag(loop))  # noqa: RUF006
