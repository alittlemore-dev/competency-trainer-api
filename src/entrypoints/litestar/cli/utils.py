import asyncio
from collections.abc import Coroutine
from typing import Any


def run_sync[T](coro: Coroutine[Any, Any, T], /) -> T:
    return asyncio.run(coro)
