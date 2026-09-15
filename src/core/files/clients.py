from abc import ABC, abstractmethod
from io import BytesIO

from core.files.schemas import FileUploadResult


class FileClient(ABC):
    @abstractmethod
    async def ensure_namespace_exists(self, namespace: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def upload_file(
        self,
        file_data: BytesIO,
        object_name: str,
        namespace: str,
        content_type: str,
    ) -> FileUploadResult:
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, object_name: str, namespace: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def init_storage(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_access_url(self, object_name: str, namespace: str) -> str:
        raise NotImplementedError
