from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest

from core.files.clients import FileClient
from core.files.exceptions import FileClientInternalError
from core.files.schemas import FileOrphanCleanupConfig, FileOrphanCleanupResult, StoredFiles
from core.files.services import FileOrphanCleanupService
from core.files.storages import FileStorage
from tests.test_cases import TestCase


class TestFileOrphanCleanupService(TestCase):
    async def test_prune_deletes_objects_before_metadata_and_returns_counts(self) -> None:
        cutoff = datetime(2026, 7, 1, tzinfo=UTC)
        first = self.factory.core.stored_file(file_id=1, orphaned_at=cutoff)
        second = self.factory.core.stored_file(file_id=2, orphaned_at=cutoff)
        client = Mock(spec=FileClient)
        storage = Mock(spec=FileStorage)
        storage.list_orphaned_files_for_cleanup.return_value = StoredFiles(
            values=[first, second],
        )
        storage.file_has_usages.return_value = False
        service = FileOrphanCleanupService(
            file_client=client,
            file_storage=storage,
            config=FileOrphanCleanupConfig(namespace="media", batch_size=100),
        )

        result = await service.prune(cutoff=cutoff)

        assert result == FileOrphanCleanupResult(
            scanned_count=2,
            deleted_count=2,
            failed_count=0,
            skipped_in_use_count=0,
        )
        storage.list_orphaned_files_for_cleanup.assert_awaited_once_with(
            namespace="media",
            cutoff=cutoff,
            limit=100,
        )
        client.delete_file.assert_has_awaits(
            [
                call(object_name=first.relative_path, namespace="media"),
                call(object_name=second.relative_path, namespace="media"),
            ],
        )
        storage.delete_file.assert_has_awaits(
            [call(file_id=first.id), call(file_id=second.id)],
        )

    async def test_prune_keeps_metadata_after_client_error_and_continues(self) -> None:
        cutoff = datetime(2026, 7, 1, tzinfo=UTC)
        failed = self.factory.core.stored_file(file_id=1, orphaned_at=cutoff)
        deleted = self.factory.core.stored_file(file_id=2, orphaned_at=cutoff)
        client = Mock(spec=FileClient)
        client.delete_file.side_effect = [
            FileClientInternalError(message="MinIO failed"),
            None,
        ]
        storage = Mock(spec=FileStorage)
        storage.list_orphaned_files_for_cleanup.return_value = StoredFiles(
            values=[failed, deleted],
        )
        storage.file_has_usages.return_value = False
        service = FileOrphanCleanupService(
            file_client=client,
            file_storage=storage,
            config=FileOrphanCleanupConfig(namespace="media", batch_size=100),
        )

        result = await service.prune(cutoff=cutoff)

        assert result.failed_count == 1
        assert result.deleted_count == 1
        storage.delete_file.assert_awaited_once_with(file_id=deleted.id)

    async def test_prune_clears_orphan_marker_when_usage_reappeared(self) -> None:
        cutoff = datetime(2026, 7, 1, tzinfo=UTC)
        file = self.factory.core.stored_file(file_id=1, orphaned_at=cutoff)
        client = Mock(spec=FileClient)
        storage = Mock(spec=FileStorage)
        storage.list_orphaned_files_for_cleanup.return_value = StoredFiles(values=[file])
        storage.file_has_usages.return_value = True
        service = FileOrphanCleanupService(
            file_client=client,
            file_storage=storage,
            config=FileOrphanCleanupConfig(namespace="media", batch_size=100),
        )

        result = await service.prune(cutoff=cutoff)

        assert result == FileOrphanCleanupResult(
            scanned_count=1,
            deleted_count=0,
            failed_count=0,
            skipped_in_use_count=1,
        )
        storage.set_files_attached.assert_awaited_once_with(file_ids=frozenset({file.id}))
        client.delete_file.assert_not_called()
        storage.delete_file.assert_not_called()

    async def test_prune_propagates_unexpected_errors(self) -> None:
        cutoff = datetime(2026, 7, 1, tzinfo=UTC)
        file = self.factory.core.stored_file(file_id=1, orphaned_at=cutoff)
        client = Mock(spec=FileClient)
        client.delete_file.side_effect = RuntimeError("unexpected")
        storage = Mock(spec=FileStorage)
        storage.list_orphaned_files_for_cleanup.return_value = StoredFiles(values=[file])
        storage.file_has_usages.return_value = False
        service = FileOrphanCleanupService(
            file_client=client,
            file_storage=storage,
            config=FileOrphanCleanupConfig(namespace="media", batch_size=100),
        )

        with pytest.raises(RuntimeError, match="unexpected"):
            await service.prune(cutoff=cutoff)

        storage.delete_file.assert_not_called()
