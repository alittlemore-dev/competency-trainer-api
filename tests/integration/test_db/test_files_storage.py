import asyncio
from datetime import UTC, datetime
from typing import cast

import pytest
import pytest_asyncio
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.exceptions import EntryNotFoundError
from core.files.enums import FilePurpose
from core.files.types import Namespace
from infra.postgresql.models import ArticleModel
from infra.postgresql.storages.files import FilesDatabaseStorage
from tests.helpers.storage import StorageHelper
from tests.test_cases import StorageTestCase


class TestFilesDatabaseStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.storage = FilesDatabaseStorage(session=self.db_session)

    async def test_create_get_list_update_and_delete_file(self) -> None:
        older = self.factory.core.stored_file(
            file_id=1,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/older.png",
            name="Older",
            original_name="older.png",
            created_at=datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 7, 3, 10, 0, tzinfo=UTC),
        )
        newer = self.factory.core.stored_file(
            file_id=2,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/newer.png",
            name="Newer",
            original_name="newer.png",
            created_at=datetime(2026, 7, 3, 11, 0, tzinfo=UTC),
            updated_at=datetime(2026, 7, 3, 11, 0, tzinfo=UTC),
        )
        attachment = self.factory.core.stored_file(
            file_id=3,
            purpose=FilePurpose.ATTACHMENT,
            relative_path="attachments/document.pdf",
            mime_type="application/pdf",
            name="Document",
            original_name="document.pdf",
        )

        created = await self.storage.create_file(file=older)
        await self.storage.create_file(file=newer)
        await self.storage.create_file(file=attachment)

        result = await self.storage.get_file(file_id=older.id)
        article_images = await self.storage.list_files(
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
        )
        renamed = await self.storage.update_file_name(
            file_id=older.id,
            name="Renamed older",
            updated_at=datetime(2026, 7, 3, 12, 0, tzinfo=UTC),
        )
        await self.storage.delete_file(file_id=older.id)

        assert created == older
        assert result == older
        assert [file.id for file in article_images] == [newer.id, older.id]
        assert renamed.name == "Renamed older"
        assert renamed.updated_at == datetime(2026, 7, 3, 12, 0, tzinfo=UTC)
        with pytest.raises(EntryNotFoundError):
            await self.storage.get_file(file_id=older.id)

    async def test_file_has_usages_checks_article_cover_and_content_links(self) -> None:
        cover = self.factory.core.stored_file(
            file_id=10,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/cover.png",
            name="Cover",
            original_name="cover.png",
        )
        content = self.factory.core.stored_file(
            file_id=11,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/content.png",
            name="Content image",
            original_name="content.png",
        )
        unused = self.factory.core.stored_file(
            file_id=12,
            purpose=FilePurpose.ATTACHMENT,
            relative_path="attachments/unused.txt",
            mime_type="text/plain",
            name="Unused",
            original_name="unused.txt",
        )
        await self.storage.create_file(file=cover)
        await self.storage.create_file(file=content)
        await self.storage.create_file(file=unused)
        await self.storage_helper.create_article(
            article=self.factory.core.article(
                slug="managed-file-usages",
                cover_image_file_id=cover.id,
                content_file_ids=frozenset({content.id}),
            ),
        )

        assert await self.storage.file_has_usages(file_id=cover.id)
        assert await self.storage.file_has_usages(file_id=content.id)
        assert not await self.storage.file_has_usages(file_id=unused.id)

    async def test_find_file_by_original_sha256_is_scoped_by_namespace_and_purpose(self) -> None:
        original_sha256 = "a" * 64
        other_namespace = cast("Namespace", "other-media")
        matching = self.factory.core.stored_file(
            file_id=30,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            namespace="media",
            relative_path="article-content-images/matching.png",
            name="Matching",
            original_name="matching.png",
            original_sha256=original_sha256,
            created_at=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
            updated_at=datetime(2026, 7, 3, 9, 0, tzinfo=UTC),
        )
        same_hash_cover = self.factory.core.stored_file(
            file_id=31,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/cover.png",
            name="Cover",
            original_name="cover.png",
            original_sha256=original_sha256,
        )
        same_hash_other_namespace = self.factory.core.stored_file(
            file_id=32,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            namespace=other_namespace,
            relative_path="article-content-images/other.png",
            name="Other namespace",
            original_name="other.png",
            original_sha256=original_sha256,
        )
        null_hash = self.factory.core.stored_file(
            file_id=33,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            namespace="media",
            relative_path="article-content-images/null.png",
            name="No hash",
            original_name="null.png",
            original_sha256=None,
        )
        await self.storage.create_file(file=matching)
        await self.storage.create_file(file=same_hash_cover)
        await self.storage.create_file(file=same_hash_other_namespace)
        await self.storage.create_file(file=null_hash)

        assert (
            await self.storage.find_file_by_original_sha256(
                namespace="media",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                original_sha256=original_sha256,
            )
        ) == matching
        assert (
            await self.storage.find_file_by_original_sha256(
                namespace="media",
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                original_sha256=original_sha256,
            )
        ) == same_hash_cover
        assert (
            await self.storage.find_file_by_original_sha256(
                namespace=other_namespace,
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                original_sha256=original_sha256,
            )
        ) == same_hash_other_namespace
        assert (
            await self.storage.find_file_by_original_sha256(
                namespace="media",
                purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                original_sha256="b" * 64,
            )
            is None
        )

    async def test_delete_file_is_restricted_by_article_foreign_keys(self) -> None:
        cover = self.factory.core.stored_file(
            file_id=20,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/restricted-cover.png",
            name="Restricted cover",
            original_name="cover.png",
        )
        await self.storage.create_file(file=cover)
        await self.storage_helper.create_article(
            article=self.factory.core.article(
                slug="delete-restricted-by-cover",
                cover_image_file_id=cover.id,
            ),
        )

        with pytest.raises(IntegrityError):
            await self.storage.delete_file(file_id=cover.id)
        await self.db_session.rollback()

    async def test_attachment_and_orphan_transitions_preserve_shared_usages(self) -> None:
        orphaned_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
        shared = self.factory.core.stored_file(
            file_id=40,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/shared.png",
            orphaned_at=orphaned_at,
        )
        unused = self.factory.core.stored_file(
            file_id=41,
            purpose=FilePurpose.ATTACHMENT,
            relative_path="attachments/unused.pdf",
            orphaned_at=orphaned_at,
        )
        await self.storage.create_file(file=shared)
        await self.storage.create_file(file=unused)
        await self.storage_helper.create_article(
            article=self.factory.core.article(
                slug="shared-file-usage",
                content_file_ids=frozenset({shared.id}),
            ),
        )

        await self.storage.set_files_attached(file_ids=frozenset({shared.id, unused.id}))
        await self.storage.set_files_orphaned_if_unused(
            file_ids=frozenset({shared.id, unused.id}),
            orphaned_at=orphaned_at,
        )

        assert (await self.storage.get_file(file_id=shared.id)).orphaned_at is None
        assert (await self.storage.get_file(file_id=unused.id)).orphaned_at == orphaned_at

    async def test_concurrent_final_detaches_serialize_on_the_file_row(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        orphaned_at = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
        shared = self.factory.core.stored_file(
            file_id=42,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/concurrent-shared.png",
            orphaned_at=None,
        )
        async with session_maker() as seed_session:
            seed_storage = FilesDatabaseStorage(session=seed_session)
            seed_helper = StorageHelper(session=seed_session)
            await seed_storage.create_file(file=shared)
            await seed_helper.create_article(
                article=self.factory.core.article(
                    slug="concurrent-detach-a",
                    cover_image_file_id=shared.id,
                ),
            )
            await seed_helper.create_article(
                article=self.factory.core.article(
                    slug="concurrent-detach-b",
                    cover_image_file_id=shared.id,
                ),
            )
            await seed_session.commit()

        async with session_maker() as first_session, session_maker() as second_session:
            await first_session.execute(
                update(ArticleModel)
                .where(ArticleModel.slug == "concurrent-detach-a")
                .values(cover_image_file_id=None),
            )
            await second_session.execute(
                update(ArticleModel)
                .where(ArticleModel.slug == "concurrent-detach-b")
                .values(cover_image_file_id=None),
            )
            first_storage = FilesDatabaseStorage(session=first_session)
            second_storage = FilesDatabaseStorage(session=second_session)

            await first_storage.set_files_orphaned_if_unused(
                file_ids=frozenset({shared.id}),
                orphaned_at=orphaned_at,
            )
            second_transition = asyncio.create_task(
                second_storage.set_files_orphaned_if_unused(
                    file_ids=frozenset({shared.id}),
                    orphaned_at=orphaned_at,
                ),
            )
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(second_transition), timeout=0.1)

            await first_session.commit()
            await second_transition
            await second_session.commit()

        async with session_maker() as verification_session:
            stored = await FilesDatabaseStorage(session=verification_session).get_file(
                file_id=shared.id,
            )
            assert stored.orphaned_at == orphaned_at

    async def test_article_attach_blocks_delete_lock_until_usage_is_visible(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        file = self.factory.core.stored_file(
            file_id=45,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/concurrent-attach.png",
        )
        async with session_maker() as seed_session:
            await FilesDatabaseStorage(session=seed_session).create_file(file=file)
            await seed_session.commit()

        async with session_maker() as attach_session, session_maker() as delete_session:
            await StorageHelper(session=attach_session).create_article(
                article=self.factory.core.article(
                    slug="concurrent-attach",
                    cover_image_file_id=file.id,
                ),
            )
            delete_storage = FilesDatabaseStorage(session=delete_session)
            delete_lock = asyncio.create_task(
                delete_storage.lock_files(file_ids=frozenset({file.id})),
            )
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(delete_lock), timeout=0.1)

            await attach_session.commit()
            await delete_lock

            assert await delete_storage.file_has_usages(file_id=file.id) is True
            await delete_session.rollback()

    async def test_sorted_file_locks_serialize_concurrent_cover_swaps(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        first_file = self.factory.core.stored_file(
            file_id=43,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/swap-a.png",
            orphaned_at=None,
        )
        second_file = self.factory.core.stored_file(
            file_id=44,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/swap-b.png",
            orphaned_at=None,
        )
        async with session_maker() as seed_session:
            seed_storage = FilesDatabaseStorage(session=seed_session)
            seed_helper = StorageHelper(session=seed_session)
            await seed_storage.create_file(file=first_file)
            await seed_storage.create_file(file=second_file)
            await seed_helper.create_article(
                article=self.factory.core.article(
                    slug="cover-swap-a",
                    cover_image_file_id=first_file.id,
                ),
            )
            await seed_helper.create_article(
                article=self.factory.core.article(
                    slug="cover-swap-b",
                    cover_image_file_id=second_file.id,
                ),
            )
            await seed_session.commit()

        swapped_ids = frozenset({first_file.id, second_file.id})
        async with session_maker() as first_session, session_maker() as second_session:
            first_storage = FilesDatabaseStorage(session=first_session)
            second_storage = FilesDatabaseStorage(session=second_session)
            await first_storage.lock_files(file_ids=swapped_ids)
            await first_session.execute(
                update(ArticleModel)
                .where(ArticleModel.slug == "cover-swap-a")
                .values(cover_image_file_id=second_file.id),
            )

            second_lock = asyncio.create_task(second_storage.lock_files(file_ids=swapped_ids))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(second_lock), timeout=0.1)

            await first_session.commit()
            await second_lock
            await second_session.execute(
                update(ArticleModel)
                .where(ArticleModel.slug == "cover-swap-b")
                .values(cover_image_file_id=first_file.id),
            )
            await second_session.commit()

    async def test_list_orphaned_files_for_cleanup_filters_orders_and_limits(self) -> None:
        cutoff = datetime(2026, 7, 10, tzinfo=UTC)
        expected_files: list[tuple[datetime, str]] = []
        for number in range(101):
            orphaned_at = datetime(2026, 7, 1, tzinfo=UTC).replace(second=number % 60)
            purpose = list(FilePurpose)[number % len(FilePurpose)]
            file = self.factory.core.stored_file(
                file_id=1000 + number,
                purpose=purpose,
                relative_path=f"cleanup/{number}",
                orphaned_at=orphaned_at,
            )
            await self.storage.create_file(file=file)
            expected_files.append((orphaned_at, file.id))
        exact_cutoff = self.factory.core.stored_file(
            file_id=1200,
            relative_path="cleanup/exact-cutoff",
            orphaned_at=cutoff,
        )
        attached = self.factory.core.stored_file(
            file_id=1201,
            relative_path="cleanup/attached",
            orphaned_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        await self.storage.create_file(file=exact_cutoff)
        await self.storage.create_file(file=attached)
        await self.storage_helper.create_article(
            article=self.factory.core.article(
                slug="cleanup-attached",
                content_file_ids=frozenset({attached.id}),
            ),
        )

        result = await self.storage.list_orphaned_files_for_cleanup(
            namespace="media",
            cutoff=cutoff,
            limit=100,
        )

        expected_files.sort()
        assert [file.id for file in result] == [file_id for _, file_id in expected_files[:100]]
        assert {file.purpose for file in result} == set(FilePurpose)
        assert exact_cutoff.id not in {file.id for file in result}
        assert attached.id not in {file.id for file in result}

    async def test_cleanup_selection_skips_rows_locked_by_another_worker(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        cutoff = datetime(2026, 7, 10, tzinfo=UTC)
        file = self.factory.core.stored_file(
            file_id=1300,
            relative_path="cleanup/locked",
            orphaned_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
        async with session_maker() as seed_session:
            await FilesDatabaseStorage(session=seed_session).create_file(file=file)
            await seed_session.commit()

        async with session_maker() as first_session, session_maker() as second_session:
            first_result = await FilesDatabaseStorage(
                session=first_session,
            ).list_orphaned_files_for_cleanup(
                namespace="media",
                cutoff=cutoff,
                limit=100,
            )
            second_result = await FilesDatabaseStorage(
                session=second_session,
            ).list_orphaned_files_for_cleanup(
                namespace="media",
                cutoff=cutoff,
                limit=100,
            )

            assert [candidate.id for candidate in first_result] == [file.id]
            assert second_result.values == []
