from unittest.mock import AsyncMock, Mock, patch

import pytest

from core.files.clients import FileClient
from entrypoints.litestar.cli.commands.storage import init_buckets_command


class TestStorageCliCommands:
    async def test_init_buckets_command_initializes_storage_and_closes_container(self) -> None:
        providers = (Mock(),)
        file_client = Mock(spec=FileClient)
        file_client.init_storage = AsyncMock()
        command_container = Mock()
        command_container.get = AsyncMock(return_value=file_client)
        command_container.close = AsyncMock()

        with (
            patch(
                "entrypoints.litestar.cli.commands.storage.get_providers",
                return_value=providers,
            ),
            patch(
                "entrypoints.litestar.cli.commands.storage.make_async_container",
                return_value=command_container,
            ) as make_async_container,
        ):
            await init_buckets_command()

        make_async_container.assert_called_once_with(*providers)
        command_container.get.assert_awaited_once_with(FileClient)
        file_client.init_storage.assert_awaited_once_with()
        command_container.close.assert_awaited_once_with()

    async def test_init_buckets_command_closes_container_when_storage_initialization_fails(
        self,
    ) -> None:
        storage_error = RuntimeError("storage initialization failed")
        providers = (Mock(),)
        file_client = Mock(spec=FileClient)
        file_client.init_storage = AsyncMock(side_effect=storage_error)
        command_container = Mock()
        command_container.get = AsyncMock(return_value=file_client)
        command_container.close = AsyncMock()

        with (
            patch(
                "entrypoints.litestar.cli.commands.storage.get_providers",
                return_value=providers,
            ),
            patch(
                "entrypoints.litestar.cli.commands.storage.make_async_container",
                return_value=command_container,
            ),
            pytest.raises(RuntimeError, match="storage initialization failed"),
        ):
            await init_buckets_command()

        command_container.close.assert_awaited_once_with()
