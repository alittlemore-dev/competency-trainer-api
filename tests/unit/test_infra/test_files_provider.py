from types import TracebackType
from unittest.mock import Mock, patch

from dishka import Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncSession

from core.files.schemas import FileOrphanCleanupConfig
from core.files.services import FileOrphanCleanupService
from core.files.storages import FileStorage
from infra.ioc.prodivers.files_provider import FilesProvider
from infra.s3.clients import S3ClientBundle


class MockSessionProvider(Provider):
    @provide(scope=Scope.REQUEST)
    async def provide_async_session(self) -> AsyncSession:
        return Mock(spec=AsyncSession)


class S3ContextManagerDouble:
    def __init__(self, client: Mock) -> None:
        self.client = client
        self.entered = False
        self.exited = False
        self.exit_args: (
            tuple[type[BaseException] | None, BaseException | None, TracebackType | None] | None
        ) = None

    async def __aenter__(self) -> Mock:
        self.entered = True
        return self.client

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.exited = True
        self.exit_args = (exc_type, exc_value, traceback)


class S3SessionDouble:
    def __init__(self) -> None:
        self.internal_client = Mock(name="internal_s3_client")
        self.public_client = Mock(name="public_s3_client")
        self.internal_context_manager = S3ContextManagerDouble(client=self.internal_client)
        self.public_context_manager = S3ContextManagerDouble(client=self.public_client)
        self.create_client = Mock(
            side_effect=[
                self.internal_context_manager,
                self.public_context_manager,
            ],
        )


class TestFilesProvider:
    async def test_orphan_cleanup_service_targets_only_public_media_namespace(self) -> None:
        provider = FilesProvider()
        file_client = Mock()
        file_storage = Mock(spec=FileStorage)

        service = await provider.provide_file_orphan_cleanup_service(
            file_client=file_client,
            file_storage=file_storage,
        )

        assert service == FileOrphanCleanupService(
            file_client=file_client,
            file_storage=file_storage,
            config=FileOrphanCleanupConfig(
                namespace="media",
                batch_size=100,
            ),
        )

    async def test_s3_clients_exit_contexts_when_container_closes(self) -> None:
        session = S3SessionDouble()

        with (
            patch("infra.ioc.prodivers.files_provider.get_session", return_value=session),
            patch("infra.ioc.prodivers.files_provider.settings") as mock_settings,
        ):
            mock_settings.minio.region = "test-region"
            mock_settings.minio.access_key = "test-access-key"
            mock_settings.minio.secret_key.get_secret_value.return_value = "test-secret-key"
            mock_settings.minio.internal_endpoint_url = "http://minio:9000"
            mock_settings.minio.public_endpoint_url = "https://s3.example.test"
            container = make_async_container(FilesProvider(), MockSessionProvider())
            try:
                provided_clients = await container.get(S3ClientBundle)
            finally:
                await container.close()

        assert provided_clients == S3ClientBundle(
            internal=session.internal_client,
            public=session.public_client,
        )
        assert session.create_client.call_count == 2
        first_call, second_call = session.create_client.call_args_list
        assert first_call.kwargs["endpoint_url"] == "http://minio:9000"
        assert second_call.kwargs["endpoint_url"] == "https://s3.example.test"
        assert first_call.kwargs["region_name"] == "test-region"
        assert second_call.kwargs["region_name"] == "test-region"
        assert session.internal_context_manager.entered is True
        assert session.public_context_manager.entered is True
        assert session.internal_context_manager.exited is True
        assert session.public_context_manager.exited is True
        assert session.internal_context_manager.exit_args == (None, None, None)
        assert session.public_context_manager.exit_args == (None, None, None)
