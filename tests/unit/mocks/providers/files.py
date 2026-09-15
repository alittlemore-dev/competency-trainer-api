import time
from unittest.mock import Mock

from dishka import Provider, Scope, provide

from core.files.clients import FileClient
from core.files.file_name_generators import FileNameGenerator
from core.files.services import FileService
from core.files.storages import FileStorage
from infra.s3.clients import S3ClientBundle


class MockFilesProvider(Provider):
    def __init__(self, timestamp: int | None = None, random_suffix: str | None = None) -> None:
        super().__init__()
        self.timestamp = timestamp or int(time.time() * 1_000_000)
        self.random_suffix = random_suffix or "abcd1234"

    @provide(scope=Scope.APP)
    async def provide_file_name_generator(self) -> FileNameGenerator:
        def mock_call(folder: str | None, file_extension: str) -> str:
            normalized_extension = FileNameGenerator.normalize_extension(file_extension)
            file_name = f"{self.timestamp}_{self.random_suffix}{normalized_extension}"
            path = "/".join([(folder or "").strip("/"), file_name])
            return path.removeprefix("/")

        return Mock(spec=FileNameGenerator, side_effect=mock_call)

    @provide(scope=Scope.APP)
    async def provide_s3_clients(self) -> S3ClientBundle:
        return S3ClientBundle(
            internal=Mock(name="internal_s3_client"),
            public=Mock(name="public_s3_client"),
        )

    @provide(scope=Scope.APP)
    async def provide_file_client(self) -> FileClient:
        return Mock(spec=FileClient)

    @provide(scope=Scope.APP)
    async def provide_file_storage(self) -> FileStorage:
        return Mock(spec=FileStorage)

    @provide(scope=Scope.APP)
    async def provide_file_service(self) -> FileService:
        return Mock(spec=FileService)
