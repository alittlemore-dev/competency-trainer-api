import hashlib
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO

from core.files.clients import FileClient
from core.files.enums import FilePurpose
from core.files.exceptions import (
    FileClientInternalError,
    FileInUseError,
    FilePurposeNotAllowedError,
)
from core.files.file_name_generators import FileNameGenerator
from core.files.processors import FileContentProcessor
from core.files.schemas import (
    FileOrphanCleanupConfig,
    FileOrphanCleanupResult,
    FileRead,
    FileServiceConfig,
    FileUpdateParams,
    FileUploadParams,
    StoredFile,
)
from core.files.storages import FileStorage


@dataclass(kw_only=True, slots=True, frozen=True)
class FileService:
    file_client: FileClient
    file_storage: FileStorage
    file_name_generator: FileNameGenerator
    file_content_processor: FileContentProcessor
    config: FileServiceConfig

    async def upload_file(
        self,
        *,
        params: FileUploadParams,
        current_datetime: datetime,
    ) -> FileRead:
        rule = self.config.rules.require(params.purpose)
        params.validate_name()
        params.validate_mime_type(allowed_mime_types=rule.allowed_mime_types)
        params.validate_size(max_size_bytes=rule.max_size_bytes)
        original_sha256 = hashlib.sha256(params.content).hexdigest()
        duplicate = await self.file_storage.find_file_by_original_sha256(
            namespace=self.config.namespace,
            purpose=params.purpose,
            original_sha256=original_sha256,
        )
        if duplicate is not None:
            if duplicate.orphaned_at is not None:
                duplicate = await self.file_storage.refresh_file_orphaned_at(
                    file_id=duplicate.id,
                    orphaned_at=current_datetime,
                )
            return self._to_read(file=duplicate)

        upload_params = self.file_content_processor.process(params=params)
        upload_params.validate_size(max_size_bytes=rule.max_size_bytes)
        relative_path = self.file_name_generator(
            folder=rule.folder,
            file_extension=upload_params.file_extension,
        )
        file = StoredFile(
            id=upload_params.id,
            purpose=upload_params.purpose,
            namespace=self.config.namespace,
            relative_path=relative_path,
            mime_type=upload_params.mime_type,
            size_bytes=upload_params.size_bytes,
            name=upload_params.name,
            original_name=upload_params.original_name,
            original_sha256=original_sha256,
            orphaned_at=current_datetime,
            created_at=current_datetime,
            updated_at=current_datetime,
        )
        file = await self.file_storage.create_file(file=file)
        await self.file_client.upload_file(
            file_data=BytesIO(upload_params.content),
            object_name=relative_path,
            namespace=self.config.namespace,
            content_type=upload_params.mime_type,
        )
        return self._to_read(file=file)

    async def get_file(self, *, file_id: str) -> FileRead:
        return self._to_read(file=await self.file_storage.get_file(file_id=file_id))

    async def list_files(self, *, purpose: FilePurpose) -> list[FileRead]:
        files = await self.file_storage.list_files(purpose=purpose)
        return [self._to_read(file=file) for file in files]

    async def update_file(
        self,
        *,
        file_id: str,
        params: FileUpdateParams,
        current_datetime: datetime,
    ) -> FileRead:
        params.validate_name()
        return self._to_read(
            file=await self.file_storage.update_file_name(
                file_id=file_id,
                name=params.name,
                updated_at=current_datetime,
            ),
        )

    async def ensure_files_allowed(
        self,
        *,
        file_ids: frozenset[str],
        purpose: FilePurpose,
    ) -> None:
        for file_id in sorted(file_ids):
            file = await self.file_storage.get_file(file_id=file_id)
            if file.purpose != purpose:
                raise FilePurposeNotAllowedError

    async def delete_file(self, *, file_id: str) -> None:
        await self.file_storage.lock_files(file_ids=frozenset({file_id}))
        if await self.file_storage.file_has_usages(file_id=file_id):
            raise FileInUseError
        file = await self.file_storage.get_file(file_id=file_id)
        await self.file_client.delete_file(
            object_name=file.relative_path,
            namespace=file.namespace,
        )
        await self.file_storage.delete_file(file_id=file_id)

    async def lock_file_usage_transitions(self, *, file_ids: frozenset[str]) -> None:
        if file_ids:
            await self.file_storage.lock_files(file_ids=file_ids)

    async def sync_file_usages(
        self,
        *,
        attached_file_ids: frozenset[str],
        detached_file_ids: frozenset[str],
        orphaned_at: datetime,
    ) -> None:
        transitioned_file_ids = attached_file_ids | detached_file_ids
        if transitioned_file_ids:
            await self.file_storage.lock_files(file_ids=transitioned_file_ids)
        if attached_file_ids:
            await self.file_storage.set_files_attached(file_ids=attached_file_ids)
        if detached_file_ids:
            await self.file_storage.set_files_orphaned_if_unused(
                file_ids=detached_file_ids,
                orphaned_at=orphaned_at,
            )

    def _to_read(self, *, file: StoredFile) -> FileRead:
        access_url = self.file_client.get_access_url(
            object_name=file.relative_path,
            namespace=file.namespace,
        )
        return FileRead(
            file=file,
            access_url=access_url,
            markdown_url=f"{access_url}#fileId={file.id}",
        )


@dataclass(kw_only=True, slots=True, frozen=True)
class FileOrphanCleanupService:
    file_client: FileClient
    file_storage: FileStorage
    config: FileOrphanCleanupConfig

    async def prune(self, *, cutoff: datetime) -> FileOrphanCleanupResult:
        candidates = await self.file_storage.list_orphaned_files_for_cleanup(
            namespace=self.config.namespace,
            cutoff=cutoff,
            limit=self.config.batch_size,
        )
        deleted_count = 0
        failed_count = 0
        skipped_in_use_count = 0
        for file in candidates:
            if await self.file_storage.file_has_usages(file_id=file.id):
                await self.file_storage.set_files_attached(file_ids=frozenset({file.id}))
                skipped_in_use_count += 1
                continue
            try:
                await self.file_client.delete_file(
                    object_name=file.relative_path,
                    namespace=file.namespace,
                )
            except FileClientInternalError:
                failed_count += 1
                continue
            await self.file_storage.delete_file(file_id=file.id)
            deleted_count += 1
        return FileOrphanCleanupResult(
            scanned_count=len(candidates.values),
            deleted_count=deleted_count,
            failed_count=failed_count,
            skipped_in_use_count=skipped_in_use_count,
        )
