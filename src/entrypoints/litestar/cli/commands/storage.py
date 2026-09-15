from dishka import make_async_container

from core.files.clients import FileClient
from infra.ioc.registry import get_providers


async def init_buckets_command() -> None:
    command_container = make_async_container(*get_providers())
    try:
        file_client = await command_container.get(FileClient)
        await file_client.init_storage()
    finally:
        await command_container.close()
