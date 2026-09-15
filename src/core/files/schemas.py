from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from mimetypes import guess_extension
from pathlib import PurePath

from core.files.enums import FilePurpose
from core.files.exceptions import (
    ContentTypeNotAllowedError,
    FileNameInvalidError,
    FileSizeTooLargeError,
)
from core.files.types import Namespace
from core.schemas import ValuedDataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class FileRule:
    folder: str
    allowed_mime_types: frozenset[str]
    max_size_bytes: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FileRules:
    values: Mapping[FilePurpose, FileRule]

    def require(self, purpose: FilePurpose) -> FileRule:
        return self.values[purpose]


@dataclass(frozen=True, slots=True, kw_only=True)
class FileServiceConfig:
    namespace: Namespace
    rules: FileRules


@dataclass(frozen=True, slots=True, kw_only=True)
class FileOrphanCleanupConfig:
    namespace: Namespace
    batch_size: int


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredFile:
    id: str
    purpose: FilePurpose
    namespace: Namespace
    relative_path: str
    mime_type: str
    size_bytes: int
    name: str
    original_name: str
    original_sha256: str | None
    orphaned_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredFiles(ValuedDataclass[StoredFile]): ...


@dataclass(frozen=True, slots=True, kw_only=True)
class FileOrphanCleanupResult:
    scanned_count: int
    deleted_count: int
    failed_count: int
    skipped_in_use_count: int


@dataclass(frozen=True, slots=True, kw_only=True)
class FileUploadParams:
    id: str
    purpose: FilePurpose
    name: str
    original_name: str
    mime_type: str
    content: bytes

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    @property
    def file_extension(self) -> str:
        return guess_extension(self.mime_type) or PurePath(self.original_name).suffix

    def validate_mime_type(self, allowed_mime_types: frozenset[str]) -> None:
        if "*/*" in allowed_mime_types:
            return
        if self.mime_type not in allowed_mime_types:
            raise ContentTypeNotAllowedError(content_type=self.mime_type)

    def validate_size(self, max_size_bytes: int) -> None:
        if self.size_bytes > max_size_bytes:
            raise FileSizeTooLargeError(
                size_bytes=self.size_bytes,
                max_size_bytes=max_size_bytes,
            )

    def validate_name(self) -> None:
        if not self.name.strip():
            raise FileNameInvalidError


@dataclass(frozen=True, slots=True, kw_only=True)
class FileUpdateParams:
    name: str

    def validate_name(self) -> None:
        if not self.name.strip():
            raise FileNameInvalidError


@dataclass(frozen=True, slots=True, kw_only=True)
class FileRead:
    file: StoredFile
    access_url: str
    markdown_url: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FileUploadResult:
    url: str
    bucket: str
    object_name: str
    size: int
