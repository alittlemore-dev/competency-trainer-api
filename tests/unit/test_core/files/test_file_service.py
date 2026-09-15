import hashlib
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import Mock, call

import pytest
import pytest_asyncio

from core.files.clients import FileClient
from core.files.enums import FilePurpose
from core.files.exceptions import (
    ContentTypeNotAllowedError,
    FileInUseError,
    FileNameInvalidError,
    FilePurposeNotAllowedError,
    FileSizeTooLargeError,
)
from core.files.file_name_generators import FileNameGenerator
from core.files.processors import FileContentProcessor
from core.files.schemas import (
    FileRead,
    FileRule,
    FileRules,
    FileServiceConfig,
    FileUpdateParams,
    FileUploadParams,
    FileUploadResult,
    StoredFile,
)
from core.files.services import FileService
from core.files.storages import FileStorage
from tests.test_cases import TestCase


class TestFileService(TestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.now = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
        self.file_client = Mock(spec=FileClient)
        self.file_storage = Mock(spec=FileStorage)
        self.file_name_generator = Mock(spec=FileNameGenerator)
        self.file_name_generator.return_value = "article-content-images/file-id.png"
        self.file_content_processor = Mock(spec=FileContentProcessor)
        self.file_content_processor.process.side_effect = lambda *, params: params
        self.file_storage.find_file_by_original_sha256.return_value = None
        self.service = FileService(
            file_client=self.file_client,
            file_storage=self.file_storage,
            file_name_generator=self.file_name_generator,
            file_content_processor=self.file_content_processor,
            config=FileServiceConfig(
                namespace="media",
                rules=FileRules(
                    values={
                        FilePurpose.ARTICLE_CONTENT_IMAGE: FileRule(
                            folder="article-content-images",
                            allowed_mime_types=frozenset({"image/png", "image/webp"}),
                            max_size_bytes=4,
                        ),
                        FilePurpose.ARTICLE_COVER_IMAGE: FileRule(
                            folder="article-cover-images",
                            allowed_mime_types=frozenset({"image/png", "image/webp"}),
                            max_size_bytes=8,
                        ),
                        FilePurpose.ATTACHMENT: FileRule(
                            folder="attachments",
                            allowed_mime_types=frozenset({"application/pdf"}),
                            max_size_bytes=16,
                        ),
                    },
                ),
            ),
        )

    async def test_upload_file_validates_uploads_and_persists_metadata(self) -> None:
        stored_file = StoredFile(
            id="file-id",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            namespace="media",
            relative_path="article-content-images/file-id.png",
            mime_type="image/png",
            size_bytes=4,
            name="Inline image",
            original_name="original.png",
            original_sha256=sha256_hex(b"data"),
            orphaned_at=self.now,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_client.upload_file.return_value = FileUploadResult(
            url="https://s3.example.test/media/article-content-images/file-id.png",
            bucket="media",
            object_name="article-content-images/file-id.png",
            size=4,
        )
        self.file_client.get_access_url.return_value = (
            "https://s3.example.test/media/article-content-images/file-id.png"
        )
        self.file_storage.create_file.return_value = stored_file

        result = await self.service.upload_file(
            current_datetime=self.now,
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                name="Inline image",
                original_name="original.png",
                mime_type="image/png",
                content=b"data",
            ),
        )

        assert result == FileRead(
            file=stored_file,
            access_url="https://s3.example.test/media/article-content-images/file-id.png",
            markdown_url="https://s3.example.test/media/article-content-images/file-id.png#fileId=file-id",
        )
        self.file_name_generator.assert_called_once_with(
            folder="article-content-images",
            file_extension=".png",
        )
        self.file_content_processor.process.assert_called_once()
        self.file_client.upload_file.assert_awaited_once()
        upload_call = self.file_client.upload_file.await_args.kwargs
        assert isinstance(upload_call["file_data"], BytesIO)
        assert upload_call["file_data"].getvalue() == b"data"
        assert upload_call["object_name"] == "article-content-images/file-id.png"
        assert upload_call["namespace"] == "media"
        assert upload_call["content_type"] == "image/png"
        self.file_storage.create_file.assert_awaited_once_with(file=stored_file)

    async def test_upload_file_persists_optimized_image_metadata_and_content(self) -> None:
        self.file_name_generator.return_value = "article-cover-images/file-id.webp"
        optimized_params = FileUploadParams(
            id="file-id",
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            name="Cover",
            original_name="cover.png",
            mime_type="image/webp",
            content=b"webp",
        )
        self.file_content_processor.process.side_effect = None
        self.file_content_processor.process.return_value = optimized_params
        stored_file = StoredFile(
            id="file-id",
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/file-id.webp",
            mime_type="image/webp",
            size_bytes=4,
            name="Cover",
            original_name="cover.png",
            original_sha256=sha256_hex(b"png-data"),
            orphaned_at=self.now,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_client.upload_file.return_value = FileUploadResult(
            url="https://s3.example.test/media/article-cover-images/file-id.webp",
            bucket="media",
            object_name="article-cover-images/file-id.webp",
            size=4,
        )
        self.file_client.get_access_url.return_value = (
            "https://s3.example.test/media/article-cover-images/file-id.webp"
        )
        self.file_storage.create_file.return_value = stored_file

        result = await self.service.upload_file(
            current_datetime=self.now,
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                name="Cover",
                original_name="cover.png",
                mime_type="image/png",
                content=b"png-data",
            ),
        )

        assert result.file == stored_file
        self.file_content_processor.process.assert_called_once()
        self.file_name_generator.assert_called_once_with(
            folder="article-cover-images",
            file_extension=".webp",
        )
        upload_call = self.file_client.upload_file.await_args.kwargs
        assert upload_call["file_data"].getvalue() == b"webp"
        assert upload_call["object_name"] == "article-cover-images/file-id.webp"
        assert upload_call["content_type"] == "image/webp"
        self.file_storage.create_file.assert_awaited_once_with(file=stored_file)

    async def test_upload_file_returns_existing_file_for_duplicate_original_hash(self) -> None:
        duplicate = StoredFile(
            id="existing-id",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            namespace="media",
            relative_path="article-content-images/existing.webp",
            mime_type="image/webp",
            size_bytes=3,
            name="Already uploaded",
            original_name="previous.png",
            original_sha256=sha256_hex(b"same"),
            orphaned_at=None,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.find_file_by_original_sha256.return_value = duplicate
        self.file_client.get_access_url.return_value = (
            "https://s3.example.test/media/article-content-images/existing.webp"
        )

        result = await self.service.upload_file(
            current_datetime=self.now,
            params=FileUploadParams(
                id="new-id",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                name="New requested name",
                original_name="duplicate.png",
                mime_type="image/png",
                content=b"same",
            ),
        )

        assert result == FileRead(
            file=duplicate,
            access_url="https://s3.example.test/media/article-content-images/existing.webp",
            markdown_url="https://s3.example.test/media/article-content-images/existing.webp#fileId=existing-id",
        )
        self.file_storage.find_file_by_original_sha256.assert_awaited_once_with(
            namespace="media",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            original_sha256=sha256_hex(b"same"),
        )
        self.file_storage.refresh_file_orphaned_at.assert_not_called()
        self.file_content_processor.process.assert_not_called()
        self.file_name_generator.assert_not_called()
        self.file_storage.create_file.assert_not_called()
        self.file_client.upload_file.assert_not_called()

    async def test_upload_file_refreshes_orphan_grace_period_for_duplicate(self) -> None:
        previous_orphaned_at = datetime(2026, 6, 1, 10, 0, tzinfo=UTC)
        duplicate = self.factory.core.stored_file(
            file_id="existing-id",
            original_sha256=sha256_hex(b"same"),
            orphaned_at=previous_orphaned_at,
        )
        refreshed = self.factory.core.stored_file(
            file_id="existing-id",
            original_sha256=sha256_hex(b"same"),
            orphaned_at=self.now,
        )
        self.file_storage.find_file_by_original_sha256.return_value = duplicate
        self.file_storage.refresh_file_orphaned_at.return_value = refreshed
        self.file_client.get_access_url.return_value = "https://cdn.test/existing.png"

        result = await self.service.upload_file(
            current_datetime=self.now,
            params=FileUploadParams(
                id="new-id",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                name="Duplicate",
                original_name="duplicate.png",
                mime_type="image/png",
                content=b"same",
            ),
        )

        assert result.file == refreshed
        self.file_storage.refresh_file_orphaned_at.assert_awaited_once_with(
            file_id=duplicate.id,
            orphaned_at=self.now,
        )
        self.file_client.upload_file.assert_not_called()

    async def test_upload_file_dedupes_same_original_only_within_requested_purpose(self) -> None:
        self.file_name_generator.return_value = "article-cover-images/file-id.png"
        stored_file = StoredFile(
            id="file-id",
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/file-id.png",
            mime_type="image/png",
            size_bytes=4,
            name="Cover",
            original_name="cover.png",
            original_sha256=sha256_hex(b"data"),
            orphaned_at=self.now,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.create_file.return_value = stored_file
        self.file_client.get_access_url.return_value = (
            "https://s3.example.test/media/article-cover-images/file-id.png"
        )

        result = await self.service.upload_file(
            current_datetime=self.now,
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                name="Cover",
                original_name="cover.png",
                mime_type="image/png",
                content=b"data",
            ),
        )

        assert result.file == stored_file
        self.file_storage.find_file_by_original_sha256.assert_awaited_once_with(
            namespace="media",
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            original_sha256=sha256_hex(b"data"),
        )
        self.file_content_processor.process.assert_called_once()
        self.file_storage.create_file.assert_awaited_once_with(file=stored_file)

    async def test_upload_file_does_not_write_object_when_metadata_write_fails(self) -> None:
        self.file_storage.create_file.side_effect = RuntimeError("db write failed")

        with pytest.raises(RuntimeError, match="db write failed"):
            await self.service.upload_file(
                current_datetime=self.now,
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                    name="Inline image",
                    original_name="original.png",
                    mime_type="image/png",
                    content=b"data",
                ),
            )

        self.file_client.upload_file.assert_not_called()

    async def test_upload_file_rejects_disallowed_mime_type_before_external_io(self) -> None:
        with pytest.raises(ContentTypeNotAllowedError):
            await self.service.upload_file(
                current_datetime=self.now,
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                    name="Inline image",
                    original_name="original.txt",
                    mime_type="text/plain",
                    content=b"data",
                ),
            )

        self.file_client.upload_file.assert_not_called()
        self.file_storage.create_file.assert_not_called()

    async def test_upload_file_rejects_pdf_cover_before_external_io(self) -> None:
        with pytest.raises(ContentTypeNotAllowedError):
            await self.service.upload_file(
                current_datetime=self.now,
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                    name="Cover",
                    original_name="cover.pdf",
                    mime_type="application/pdf",
                    content=b"%PDF",
                ),
            )

        self.file_storage.find_file_by_original_sha256.assert_not_called()
        self.file_content_processor.process.assert_not_called()
        self.file_client.upload_file.assert_not_called()
        self.file_storage.create_file.assert_not_called()

    async def test_upload_file_accepts_pdf_attachment(self) -> None:
        self.file_name_generator.return_value = "attachments/file-id.pdf"
        stored_file = StoredFile(
            id="file-id",
            purpose=FilePurpose.ATTACHMENT,
            namespace="media",
            relative_path="attachments/file-id.pdf",
            mime_type="application/pdf",
            size_bytes=8,
            name="Document",
            original_name="document.pdf",
            original_sha256=sha256_hex(b"%PDF-1.7"),
            orphaned_at=self.now,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.create_file.return_value = stored_file
        self.file_client.get_access_url.return_value = (
            "https://s3.example.test/media/attachments/file-id.pdf"
        )

        result = await self.service.upload_file(
            current_datetime=self.now,
            params=FileUploadParams(
                id="file-id",
                purpose=FilePurpose.ATTACHMENT,
                name="Document",
                original_name="document.pdf",
                mime_type="application/pdf",
                content=b"%PDF-1.7",
            ),
        )

        assert result.file == stored_file
        self.file_storage.find_file_by_original_sha256.assert_awaited_once_with(
            namespace="media",
            purpose=FilePurpose.ATTACHMENT,
            original_sha256=sha256_hex(b"%PDF-1.7"),
        )
        self.file_content_processor.process.assert_called_once()
        self.file_storage.create_file.assert_awaited_once_with(file=stored_file)

    async def test_upload_file_rejects_too_large_content_before_external_io(self) -> None:
        with pytest.raises(FileSizeTooLargeError):
            await self.service.upload_file(
                current_datetime=self.now,
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                    name="Inline image",
                    original_name="original.png",
                    mime_type="image/png",
                    content=b"large",
                ),
            )

        self.file_client.upload_file.assert_not_called()
        self.file_storage.create_file.assert_not_called()

    async def test_upload_file_rejects_blank_display_name_before_external_io(self) -> None:
        with pytest.raises(FileNameInvalidError):
            await self.service.upload_file(
                current_datetime=self.now,
                params=FileUploadParams(
                    id="file-id",
                    purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                    name="   ",
                    original_name="original.png",
                    mime_type="image/png",
                    content=b"data",
                ),
            )

        self.file_client.upload_file.assert_not_called()
        self.file_storage.create_file.assert_not_called()

    async def test_update_file_name_returns_updated_file_with_access_url(self) -> None:
        stored_file = StoredFile(
            id="file-id",
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/file-id.png",
            mime_type="image/png",
            size_bytes=4,
            name="Updated cover",
            original_name="cover.png",
            original_sha256=None,
            orphaned_at=None,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.update_file_name.return_value = stored_file
        self.file_client.get_access_url.return_value = (
            "https://s3.example.test/media/article-cover-images/file-id.png"
        )

        result = await self.service.update_file(
            file_id="file-id",
            params=FileUpdateParams(name="Updated cover"),
            current_datetime=self.now,
        )

        assert result == FileRead(
            file=stored_file,
            access_url="https://s3.example.test/media/article-cover-images/file-id.png",
            markdown_url="https://s3.example.test/media/article-cover-images/file-id.png#fileId=file-id",
        )
        self.file_storage.update_file_name.assert_awaited_once_with(
            file_id="file-id",
            name="Updated cover",
            updated_at=self.now,
        )
        self.file_client.upload_file.assert_not_called()

    async def test_update_file_name_rejects_blank_display_name_before_storage_call(self) -> None:
        with pytest.raises(FileNameInvalidError):
            await self.service.update_file(
                file_id="file-id",
                params=FileUpdateParams(name=" "),
                current_datetime=self.now,
            )

        self.file_storage.update_file_name.assert_not_called()

    async def test_ensure_files_allowed_accepts_files_with_expected_purpose(self) -> None:
        stored_file = StoredFile(
            id="cover-id",
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/cover.png",
            mime_type="image/png",
            size_bytes=4,
            name="Cover",
            original_name="cover.png",
            original_sha256=None,
            orphaned_at=None,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.get_file.return_value = stored_file

        await self.service.ensure_files_allowed(
            file_ids=frozenset({"cover-id"}),
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
        )

        self.file_storage.get_file.assert_awaited_once_with(file_id="cover-id")

    async def test_ensure_files_allowed_rejects_files_with_different_purpose(self) -> None:
        stored_file = StoredFile(
            id="inline-id",
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            namespace="media",
            relative_path="article-content-images/image.png",
            mime_type="image/png",
            size_bytes=4,
            name="Inline image",
            original_name="image.png",
            original_sha256=None,
            orphaned_at=None,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.get_file.return_value = stored_file

        with pytest.raises(FilePurposeNotAllowedError):
            await self.service.ensure_files_allowed(
                file_ids=frozenset({"inline-id"}),
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            )

    async def test_delete_file_rejects_file_with_usages_before_external_io(self) -> None:
        self.file_storage.file_has_usages.return_value = True

        with pytest.raises(FileInUseError):
            await self.service.delete_file(file_id="file-id")

        self.file_storage.lock_files.assert_awaited_once_with(
            file_ids=frozenset({"file-id"}),
        )
        self.file_client.delete_file.assert_not_called()
        self.file_storage.delete_file.assert_not_called()

    async def test_delete_file_deletes_object_before_metadata(self) -> None:
        stored_file = StoredFile(
            id="file-id",
            purpose=FilePurpose.ATTACHMENT,
            namespace="media",
            relative_path="attachments/file-id.pdf",
            mime_type="application/pdf",
            size_bytes=4,
            name="Attachment",
            original_name="attachment.pdf",
            original_sha256=None,
            orphaned_at=self.now,
            created_at=self.now,
            updated_at=self.now,
        )
        self.file_storage.file_has_usages.return_value = False
        self.file_storage.get_file.return_value = stored_file
        deletion_order = Mock()
        deletion_order.attach_mock(self.file_storage.lock_files, "lock")
        deletion_order.attach_mock(self.file_storage.file_has_usages, "check_usages")
        deletion_order.attach_mock(self.file_client.delete_file, "delete_object")
        deletion_order.attach_mock(self.file_storage.delete_file, "delete_metadata")

        await self.service.delete_file(file_id="file-id")

        self.file_client.delete_file.assert_awaited_once_with(
            object_name="attachments/file-id.pdf",
            namespace="media",
        )
        self.file_storage.delete_file.assert_awaited_once_with(file_id="file-id")
        assert deletion_order.mock_calls == [
            call.lock(file_ids=frozenset({"file-id"})),
            call.check_usages(file_id="file-id"),
            call.delete_object(
                object_name="attachments/file-id.pdf",
                namespace="media",
            ),
            call.delete_metadata(file_id="file-id"),
        ]

    async def test_sync_file_usages_attaches_current_and_orphans_removed_files(self) -> None:
        await self.service.sync_file_usages(
            attached_file_ids=frozenset({"cover-id", "content-id"}),
            detached_file_ids=frozenset({"old-cover-id", "old-content-id"}),
            orphaned_at=self.now,
        )

        self.file_storage.lock_files.assert_awaited_once_with(
            file_ids=frozenset({"cover-id", "content-id", "old-cover-id", "old-content-id"}),
        )
        self.file_storage.set_files_attached.assert_awaited_once_with(
            file_ids=frozenset({"cover-id", "content-id"}),
        )
        self.file_storage.set_files_orphaned_if_unused.assert_awaited_once_with(
            file_ids=frozenset({"old-cover-id", "old-content-id"}),
            orphaned_at=self.now,
        )


def sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
