from abc import ABC, abstractmethod
from datetime import datetime

from core.files.enums import FilePurpose
from core.files.schemas import StoredFile, StoredFiles
from core.files.types import Namespace


class FileStorage(ABC):
    @abstractmethod
    async def create_file(self, *, file: StoredFile) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    async def get_file(self, *, file_id: str) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    async def list_files(self, *, purpose: FilePurpose) -> StoredFiles:
        raise NotImplementedError

    @abstractmethod
    async def find_file_by_original_sha256(
        self,
        *,
        namespace: Namespace,
        purpose: FilePurpose,
        original_sha256: str,
    ) -> StoredFile | None:
        raise NotImplementedError

    @abstractmethod
    async def refresh_file_orphaned_at(
        self,
        *,
        file_id: str,
        orphaned_at: datetime,
    ) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    async def update_file_name(
        self,
        *,
        file_id: str,
        name: str,
        updated_at: datetime,
    ) -> StoredFile:
        raise NotImplementedError

    @abstractmethod
    async def file_has_usages(self, *, file_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def lock_files(self, *, file_ids: frozenset[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def set_files_attached(self, *, file_ids: frozenset[str]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def set_files_orphaned_if_unused(
        self,
        *,
        file_ids: frozenset[str],
        orphaned_at: datetime,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def list_orphaned_files_for_cleanup(
        self,
        *,
        namespace: Namespace,
        cutoff: datetime,
        limit: int,
    ) -> StoredFiles:
        raise NotImplementedError

    @abstractmethod
    async def delete_file(self, *, file_id: str) -> None:
        raise NotImplementedError
