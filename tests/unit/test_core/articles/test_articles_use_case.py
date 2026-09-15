from datetime import UTC, datetime
from unittest.mock import Mock, call

import pytest

from core.articles.exceptions import (
    ArticleFolderAlreadyExistsError,
    ArticleFolderNotFoundError,
    ArticleFolderPriorityInvalidError,
    ArticleNotFoundError,
    TagNotFoundError,
)
from core.articles.schemas import (
    ArticleCreateParams,
    ArticleFilters,
    ArticleFolderCreateParams,
    ArticleFolderPriorityUpdateParams,
    ArticleMetadata,
    ArticleTreeItemData,
    ArticleUpdateParams,
    PublishedArticleForSeo,
    PublishedArticlesForSeo,
    TagCreateParams,
    TagUpdateParams,
)
from core.articles.storages import ArticlesStorage
from core.articles.use_cases import ArticlesUseCase
from core.enums import PublishStatusEnum
from core.files.clients import FileClient
from core.files.enums import FilePurpose
from core.files.services import FileService
from core.i18n.enums import LanguageEnum
from tests.test_cases import TestCase


class TestArticlesUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.now = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
        self.storage = Mock(spec=ArticlesStorage)
        self.file_service = Mock(spec=FileService)
        self.file_client = Mock(spec=FileClient)
        self.use_case = ArticlesUseCase(
            storage=self.storage,
            file_service=self.file_service,
            file_client=self.file_client,
        )

    async def test_list_articles_builds_page_from_storage_rows(self) -> None:
        filters = ArticleFilters(
            page=1,
            page_size=10,
            language=LanguageEnum.RU,
            only_published=True,
            tag_slug="python",
            published_from=None,
            published_to=None,
            search_query=None,
            include_tags=True,
        )
        article = self.factory.core.article(title="Published article", slug="published-article")
        self.storage.list_articles.return_value = ([article], 11)

        result = await self.use_case.list_articles(filters=filters)

        assert result.values == [article]
        assert result.total_count == 11
        assert result.total_pages == 2
        self.storage.list_articles.assert_called_once_with(filters=filters)

    async def test_list_articles_requires_pagination_before_storage_call(self) -> None:
        with pytest.raises(ValueError, match="pagination required"):
            await self.use_case.list_articles(filters=ArticleFilters())

        self.storage.list_articles.assert_not_called()

    @pytest.mark.parametrize("only_with_published_articles", [False, True])
    async def test_list_tags_forwards_published_article_filter(
        self,
        only_with_published_articles: bool,
    ) -> None:
        tags = self.factory.core.tags(values=[self.factory.core.tag(tag_id=1)])
        self.storage.list_tags.return_value = tags

        result = await self.use_case.list_tags(
            language=LanguageEnum.EN,
            only_with_published_articles=only_with_published_articles,
        )

        assert result == tags
        self.storage.list_tags.assert_called_once_with(
            language=LanguageEnum.EN,
            only_with_published_articles=only_with_published_articles,
        )

    async def test_list_published_articles_for_seo_uses_shared_storage_list_and_available_articles(
        self,
    ) -> None:
        first_updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        first_article = self.factory.core.article(
            title="First article",
            slug="first-article",
            publish_status=PublishStatusEnum.PUBLISHED,
            updated_at="2026-01-01T00:00:00",
        )
        draft_article = self.factory.core.article(
            title="Draft article",
            slug="draft-article",
            publish_status=PublishStatusEnum.DRAFT,
            updated_at="2026-01-02T00:00:00",
        )
        self.storage.list_articles.return_value = ([first_article, draft_article], 2)

        result = await self.use_case.list_published_articles_for_seo()

        assert result == PublishedArticlesForSeo(
            values=[
                PublishedArticleForSeo(
                    slug="first-article",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    updated_at=first_updated_at,
                ),
            ],
        )
        self.storage.list_articles.assert_called_once_with(
            filters=ArticleFilters(
                only_published=True,
                include_tags=False,
                include_files=False,
                order_for_seo=True,
            ),
        )

    async def test_list_tree_builds_folders_from_storage_items(self) -> None:
        first_updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        second_updated_at = datetime(2026, 1, 2, tzinfo=UTC)
        self.storage.list_tree_items.return_value = [
            ArticleTreeItemData(
                folder_id=self.factory.core.hex_id(2),
                folder_key="backend",
                folder="Backend",
                title="Storage",
                slug="storage",
                publish_status=PublishStatusEnum.PUBLISHED,
                published_at=datetime(2026, 1, 1, tzinfo=UTC),
                updated_at=first_updated_at,
            ),
            ArticleTreeItemData(
                folder_id=self.factory.core.hex_id(1),
                folder_key="architecture",
                folder="Architecture",
                title="Boundaries",
                slug="boundaries",
                publish_status=PublishStatusEnum.DRAFT,
                published_at=None,
                updated_at=second_updated_at,
            ),
        ]

        result = await self.use_case.list_tree(
            only_published=False,
            language=LanguageEnum.EN,
        )

        assert [folder.folder for folder in result.folders] == ["Backend", "Architecture"]
        assert [item.slug for item in result.folders[0].articles] == ["storage"]
        assert [item.slug for item in result.folders[1].articles] == ["boundaries"]
        self.storage.list_tree_items.assert_called_once_with(
            only_published=False,
            language=LanguageEnum.EN,
        )

    async def test_get_article_rejects_draft_when_only_published(self) -> None:
        self.storage.get_article_by_slug.return_value = self.factory.core.article(
            slug="draft-article",
            publish_status=PublishStatusEnum.DRAFT,
        )

        with pytest.raises(ArticleNotFoundError):
            await self.use_case.get_article(
                slug="draft-article",
                only_published=True,
            )

    async def test_get_article_returns_draft_when_admin_requests_all_articles(self) -> None:
        expected = self.factory.core.article(
            slug="draft-article",
            publish_status=PublishStatusEnum.DRAFT,
        )
        self.storage.get_article_by_slug.return_value = expected

        result = await self.use_case.get_article(
            slug="draft-article",
            only_published=False,
        )

        assert result == expected
        self.storage.get_article_by_slug.assert_called_once_with(
            slug="draft-article",
            lock=False,
        )

    async def test_get_article_hydrates_cover_image_url_from_file_client(self) -> None:
        cover = self.factory.core.stored_file(
            file_id=30,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/detail-cover.png",
        )
        article = self.factory.core.article(
            slug="covered-article",
            metadata=ArticleMetadata(
                seo_title_ru=None,
                seo_title_en=None,
                seo_description_ru=None,
                seo_description_en=None,
                cover_image_file_id=cover.id,
                cover_image_file=cover,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
        )
        self.storage.get_article_by_slug.return_value = article
        self.file_client.get_access_url.return_value = "https://cdn.test/detail-cover.png"

        result = await self.use_case.get_article(slug="covered-article", only_published=False)

        assert result == article.with_cover_image_url(
            cover_image_url="https://cdn.test/detail-cover.png",
        )
        self.file_client.get_access_url.assert_called_once_with(
            object_name="article-cover-images/detail-cover.png",
            namespace="media",
        )

    async def test_list_articles_hydrates_cover_image_urls_from_file_client(self) -> None:
        cover = self.factory.core.stored_file(
            file_id=31,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            namespace="media",
            relative_path="article-cover-images/list-cover.png",
        )
        article = self.factory.core.article(
            slug="covered-list-article",
            metadata=ArticleMetadata(
                seo_title_ru=None,
                seo_title_en=None,
                seo_description_ru=None,
                seo_description_en=None,
                cover_image_file_id=cover.id,
                cover_image_file=cover,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
        )
        filters = ArticleFilters(
            page=1,
            page_size=10,
            language=LanguageEnum.EN,
            only_published=False,
            tag_slug=None,
            published_from=None,
            published_to=None,
            search_query=None,
        )
        self.storage.list_articles.return_value = ([article], 1)
        self.file_client.get_access_url.return_value = "https://cdn.test/list-cover.png"

        result = await self.use_case.list_articles(filters=filters)

        assert result.values == [
            article.with_cover_image_url(
                cover_image_url="https://cdn.test/list-cover.png",
            ),
        ]
        assert result.total_count == 1
        assert result.total_pages == 1
        self.file_client.get_access_url.assert_called_once_with(
            object_name="article-cover-images/list-cover.png",
            namespace="media",
        )

    async def test_get_article_clears_cover_image_url_when_file_metadata_is_missing(self) -> None:
        article = self.factory.core.article(
            slug="stale-cover-url",
            cover_image_file_id=None,
            cover_image_file=None,
            cover_image_url="https://cdn.test/stale-cover.png",
        )
        self.storage.get_article_by_slug.return_value = article

        result = await self.use_case.get_article(slug="stale-cover-url", only_published=False)

        assert result == article.with_cover_image_url(cover_image_url=None)
        self.file_client.get_access_url.assert_not_called()

    async def test_create_article_requires_all_tags_to_exist_and_be_active(self) -> None:
        tag_ids = [self.factory.core.hex_id(1), self.factory.core.hex_id(2)]
        params = ArticleCreateParams(
            id=self.factory.core.hex_id(10),
            slug="article",
            title_ru="Статья",
            title_en="Article",
            content_ru="Содержимое",
            content_en="Content",
            folder_id=self.factory.core.hex_id(3),
            author_username="admin",
            publish_status=PublishStatusEnum.DRAFT,
            metadata=ArticleMetadata(
                seo_title_ru=None,
                seo_title_en=None,
                seo_description_ru=None,
                seo_description_en=None,
                cover_image_file_id=None,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
            tag_ids=tag_ids,
        )
        self.storage.get_tags_by_ids.return_value = self.factory.core.tags(
            values=[self.factory.core.tag(tag_id=1)],
        )

        with pytest.raises(TagNotFoundError):
            await self.use_case.create_article(
                params=params,
                current_datetime=self.now,
            )

    async def test_create_article_persists_article_with_tags(self) -> None:
        tag_ids = [self.factory.core.hex_id(1)]
        article_id = self.factory.core.hex_id(10)
        params = ArticleCreateParams(
            id=article_id,
            slug="article",
            title_ru="Статья",
            title_en="Article",
            content_ru="Содержимое",
            content_en="Content",
            folder_id=self.factory.core.hex_id(3),
            author_username="admin",
            publish_status=PublishStatusEnum.DRAFT,
            metadata=ArticleMetadata(
                seo_title_ru="SEO статья",
                seo_title_en="SEO article",
                seo_description_ru="Описание для поиска",
                seo_description_en="Search description",
                cover_image_file_id=None,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru="Обложка",
                cover_image_alt_en="Cover",
            ),
            tag_ids=tag_ids,
        )
        tag = self.factory.core.tag(tag_id=1, slug="python")
        folder = self.factory.core.article_folder(
            folder_id=self.factory.core.hex_id(3),
            key="python",
            name_ru="Питон",
            name_en="Python",
        )
        expected = self.factory.core.article(
            article_id=article_id,
            slug="article",
            title_ru="Статья",
            title_en="Article",
            content_ru="Содержимое",
            content_en="Content",
            folder_id=folder.id,
            folder_key=folder.key,
            folder_ru="Питон",
            folder_en="Python",
            author_username="admin",
            publish_status=PublishStatusEnum.DRAFT,
            metadata=ArticleMetadata(
                seo_title_ru="SEO статья",
                seo_title_en="SEO article",
                seo_description_ru="Описание для поиска",
                seo_description_en="Search description",
                cover_image_file_id=None,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru="Обложка",
                cover_image_alt_en="Cover",
            ),
            tags=[tag],
        )
        self.storage.get_tags_by_ids.return_value = self.factory.core.tags(values=[tag])
        self.storage.get_folder_by_id.return_value = folder
        self.storage.create_article.return_value = expected

        result = await self.use_case.create_article(
            params=params,
            current_datetime=self.now,
        )

        assert result == expected
        self.storage.create_article.assert_called_once()
        created_article = self.storage.create_article.call_args.kwargs["article"]
        assert not hasattr(created_article, "title")
        assert not hasattr(created_article, "content")
        assert created_article.localized_title(language=LanguageEnum.RU) == "Статья"
        assert created_article.localized_content(language=LanguageEnum.RU) == "Содержимое"
        assert created_article.localized_folder(language=LanguageEnum.RU) == "Питон"
        assert created_article.folder.id == self.factory.core.hex_id(3)
        assert created_article.folder.key == "python"
        assert created_article.title_ru == "Статья"
        assert created_article.title_en == "Article"
        assert created_article.metadata == params.metadata
        assert created_article.content_file_ids == frozenset()
        assert created_article.author_username == "admin"
        assert created_article.tags.values == [tag]

    async def test_create_article_validates_and_syncs_managed_files(self) -> None:
        cover_file_id = self.factory.core.hex_id(30)
        inline_file_id = self.factory.core.hex_id(31)
        tag = self.factory.core.tag(tag_id=1, slug="python")
        folder = self.factory.core.article_folder(folder_id=self.factory.core.hex_id(3))
        params = ArticleCreateParams(
            id=self.factory.core.hex_id(10),
            slug="article",
            title_ru="Статья",
            title_en="Article",
            content_ru=f"![alt](https://cdn.test/content.png#fileId={inline_file_id})",
            content_en="Content",
            folder_id=folder.id,
            author_username="admin",
            publish_status=PublishStatusEnum.DRAFT,
            metadata=ArticleMetadata(
                seo_title_ru=None,
                seo_title_en=None,
                seo_description_ru=None,
                seo_description_en=None,
                cover_image_file_id=cover_file_id,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
            tag_ids=[tag.id],
        )
        self.storage.get_tags_by_ids.return_value = self.factory.core.tags(values=[tag])
        self.storage.get_folder_by_id.return_value = folder
        self.storage.create_article.return_value = self.factory.core.article(
            slug="article",
            content_file_ids=frozenset({inline_file_id}),
            cover_image_file_id=cover_file_id,
        )
        transition_order = Mock()
        transition_order.attach_mock(
            self.file_service.lock_file_usage_transitions,
            "lock_files",
        )
        transition_order.attach_mock(self.storage.create_article, "write_article")

        await self.use_case.create_article(
            params=params,
            current_datetime=self.now,
        )

        created_article = self.storage.create_article.call_args.kwargs["article"]
        assert created_article.metadata.cover_image_file_id == cover_file_id
        assert created_article.content_file_ids == frozenset({inline_file_id})
        self.file_service.ensure_files_allowed.assert_has_awaits(
            [
                call(
                    file_ids=frozenset({cover_file_id}),
                    purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                ),
                call(
                    file_ids=frozenset({inline_file_id}),
                    purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
                ),
            ],
        )
        self.file_service.sync_file_usages.assert_awaited_once_with(
            attached_file_ids=frozenset({cover_file_id, inline_file_id}),
            detached_file_ids=frozenset(),
            orphaned_at=self.now,
        )
        assert transition_order.mock_calls.index(
            call.lock_files(file_ids=frozenset({cover_file_id, inline_file_id})),
        ) < transition_order.mock_calls.index(call.write_article(article=created_article))

    async def test_create_article_requires_existing_folder_before_storage_write(self) -> None:
        params = ArticleCreateParams(
            id=self.factory.core.hex_id(10),
            slug="article",
            title_ru="Статья",
            title_en="Article",
            content_ru="Содержимое",
            content_en="Content",
            folder_id=self.factory.core.hex_id(99),
            author_username="admin",
            publish_status=PublishStatusEnum.DRAFT,
            metadata=ArticleMetadata(
                seo_title_ru=None,
                seo_title_en=None,
                seo_description_ru=None,
                seo_description_en=None,
                cover_image_file_id=None,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
            tag_ids=[],
        )
        self.storage.get_tags_by_ids.return_value = self.factory.core.tags(values=[])
        self.storage.get_folder_by_id.side_effect = ArticleFolderNotFoundError

        with pytest.raises(ArticleFolderNotFoundError):
            await self.use_case.create_article(
                params=params,
                current_datetime=self.now,
            )

        self.storage.create_article.assert_not_called()

    def test_article_create_params_builds_canonical_article(self) -> None:
        article_id = self.factory.core.hex_id(10)
        now = datetime(2026, 5, 31, 12, 0, tzinfo=UTC)
        tag = self.factory.core.tag(tag_id=1, slug="python")
        params = ArticleCreateParams(
            id=article_id,
            slug="article",
            title_ru="Статья",
            title_en="Article",
            content_ru="Содержимое",
            content_en="Content",
            folder_id=self.factory.core.hex_id(3),
            author_username="admin",
            publish_status=PublishStatusEnum.PUBLISHED,
            metadata=ArticleMetadata(
                seo_title_ru=None,
                seo_title_en=None,
                seo_description_ru=None,
                seo_description_en=None,
                cover_image_file_id=None,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
            tag_ids=[self.factory.core.hex_id(1)],
        )

        folder = self.factory.core.article_folder(
            folder_id=self.factory.core.hex_id(3),
            key="python",
            name_ru="Питон",
            name_en="Python",
        )

        article = params.to_article(
            now=now,
            folder=folder,
            tags=self.factory.core.tags(values=[tag]),
        )

        assert not hasattr(article, "title")
        assert not hasattr(article, "content")
        assert article.folder == folder
        assert article.localized_title(language=LanguageEnum.RU) == "Статья"
        assert article.localized_title(language=LanguageEnum.EN) == "Article"
        assert article.metadata == params.metadata
        assert article.published_at == now
        assert article.created_at == now
        assert article.updated_at == now
        assert article.tags.values == [tag]

    async def test_update_article_keeps_existing_author(self) -> None:
        old_cover_id = self.factory.core.hex_id(20)
        new_cover_id = self.factory.core.hex_id(21)
        removed_content_id = self.factory.core.hex_id(22)
        shared_content_id = self.factory.core.hex_id(23)
        added_content_id = self.factory.core.hex_id(24)
        tag = self.factory.core.tag(tag_id=1, slug="python")
        existing = self.factory.core.article(
            slug="old-article",
            author_username="original-author",
            cover_image_file_id=old_cover_id,
            content_file_ids=frozenset({removed_content_id, shared_content_id}),
            tags=[tag],
        )
        params = ArticleUpdateParams(
            slug="new-article",
            title_ru="Новая",
            title_en="New",
            content_ru=(
                f"![shared](https://cdn.test/shared.png#fileId={shared_content_id})"
                f"![added](https://cdn.test/added.png#fileId={added_content_id})"
            ),
            content_en="New content",
            folder_id=self.factory.core.hex_id(4),
            publish_status=PublishStatusEnum.PUBLISHED,
            metadata=ArticleMetadata(
                seo_title_ru="Новая SEO",
                seo_title_en="New SEO",
                seo_description_ru="Новое описание",
                seo_description_en="New description",
                cover_image_file_id=new_cover_id,
                cover_image_file=None,
                cover_image_url=None,
                cover_image_alt_ru=None,
                cover_image_alt_en=None,
            ),
            tag_ids=[self.factory.core.hex_id(1)],
        )
        self.storage.get_article_by_slug.return_value = existing
        self.storage.get_tags_by_ids.return_value = self.factory.core.tags(values=[tag])
        self.storage.get_folder_by_id.return_value = self.factory.core.article_folder(
            folder_id=self.factory.core.hex_id(4),
            key="architecture",
            name_ru="Архитектура",
            name_en="Architecture",
        )
        self.storage.update_article.return_value = self.factory.core.article(
            title="New",
            slug="new-article",
            author_username="original-author",
            publish_status=PublishStatusEnum.PUBLISHED,
            tags=[tag],
        )
        transition_order = Mock()
        transition_order.attach_mock(
            self.file_service.lock_file_usage_transitions,
            "lock_files",
        )
        transition_order.attach_mock(self.storage.update_article, "write_article")

        await self.use_case.update_article(
            slug="old-article",
            params=params,
            current_datetime=self.now,
        )

        updated_article = self.storage.update_article.call_args.kwargs["article"]
        assert updated_article.id == existing.id
        assert updated_article.author_username == "original-author"
        assert updated_article.title_ru == "Новая"
        assert updated_article.title_en == "New"
        assert updated_article.folder.id == self.factory.core.hex_id(4)
        assert updated_article.metadata == params.metadata
        assert not hasattr(updated_article, "title")
        self.storage.get_article_by_slug.assert_awaited_once_with(
            slug="old-article",
            lock=True,
        )
        assert transition_order.mock_calls.index(
            call.lock_files(
                file_ids=frozenset(
                    {
                        old_cover_id,
                        new_cover_id,
                        removed_content_id,
                        shared_content_id,
                        added_content_id,
                    },
                ),
            ),
        ) < transition_order.mock_calls.index(call.write_article(article=updated_article))
        self.file_service.sync_file_usages.assert_awaited_once_with(
            attached_file_ids=frozenset(
                {new_cover_id, shared_content_id, added_content_id},
            ),
            detached_file_ids=frozenset({old_cover_id, removed_content_id}),
            orphaned_at=self.now,
        )

    async def test_delete_article_orphans_all_managed_files_after_deletion(self) -> None:
        cover_file_id = self.factory.core.hex_id(30)
        content_file_id = self.factory.core.hex_id(31)
        existing = self.factory.core.article(
            slug="deleted-article",
            cover_image_file_id=cover_file_id,
            content_file_ids=frozenset({content_file_id}),
        )
        self.storage.get_article_by_slug.return_value = existing
        transition_order = Mock()
        transition_order.attach_mock(
            self.file_service.lock_file_usage_transitions,
            "lock_files",
        )
        transition_order.attach_mock(self.storage.delete_article, "write_article")

        await self.use_case.delete_article(
            slug=existing.slug,
            current_datetime=self.now,
        )

        self.storage.get_article_by_slug.assert_awaited_once_with(
            slug=existing.slug,
            lock=True,
        )
        assert transition_order.mock_calls.index(
            call.lock_files(file_ids=frozenset({cover_file_id, content_file_id})),
        ) < transition_order.mock_calls.index(call.write_article(slug=existing.slug))
        self.storage.delete_article.assert_awaited_once_with(slug=existing.slug)
        self.file_service.sync_file_usages.assert_awaited_once_with(
            attached_file_ids=frozenset(),
            detached_file_ids=frozenset({cover_file_id, content_file_id}),
            orphaned_at=self.now,
        )

    async def test_list_folders_delegates_to_storage(self) -> None:
        expected = self.factory.core.article_folders(
            values=[self.factory.core.article_folder(key="backend")],
        )
        self.storage.list_folders.return_value = expected

        result = await self.use_case.list_folders(language=LanguageEnum.EN)

        assert result == expected
        self.storage.list_folders.assert_called_once_with(language=LanguageEnum.EN)

    async def test_create_folder_delegates_to_storage(self) -> None:
        params = ArticleFolderCreateParams(
            id=self.factory.core.hex_id(11),
            key="backend",
            name_ru="Бэкенд",
            name_en="Backend",
        )
        expected = self.factory.core.article_folder(
            folder_id=self.factory.core.hex_id(11),
            key="backend",
            name_ru="Бэкенд",
            name_en="Backend",
        )
        self.storage.folder_key_exists.return_value = False
        self.storage.next_folder_priority.return_value = 1
        self.storage.create_folder.return_value = expected

        result = await self.use_case.create_folder(params=params)

        assert result == expected
        self.storage.folder_key_exists.assert_called_once_with(key="backend")
        self.storage.next_folder_priority.assert_called_once_with()
        self.storage.create_folder.assert_called_once_with(folder=expected)

    async def test_create_folder_rejects_existing_key_before_storage_write(self) -> None:
        params = ArticleFolderCreateParams(
            id=self.factory.core.hex_id(11),
            key="backend",
            name_ru="Бэкенд",
            name_en="Backend",
        )
        self.storage.folder_key_exists.return_value = True

        with pytest.raises(ArticleFolderAlreadyExistsError):
            await self.use_case.create_folder(params=params)

        self.storage.next_folder_priority.assert_not_called()
        self.storage.create_folder.assert_not_called()

    async def test_update_folder_priorities_rejects_incomplete_order(self) -> None:
        self.storage.list_folders.return_value = self.factory.core.article_folders(
            values=[
                self.factory.core.article_folder(folder_id=self.factory.core.hex_id(1)),
                self.factory.core.article_folder(folder_id=self.factory.core.hex_id(2)),
            ],
        )
        params = ArticleFolderPriorityUpdateParams(ordered_ids=(self.factory.core.hex_id(1),))

        with pytest.raises(ArticleFolderPriorityInvalidError):
            await self.use_case.update_folder_priorities(params=params)

        self.storage.update_folder_priorities.assert_not_called()

    async def test_switch_publish_status_delegates_to_storage(self) -> None:
        await self.use_case.switch_article_publish_status(
            slug="article",
            publish_status=PublishStatusEnum.PUBLISHED,
        )

        self.storage.update_article_publish_status.assert_called_once_with(
            slug="article",
            publish_status=PublishStatusEnum.PUBLISHED,
        )

    async def test_create_tag_delegates_to_storage(self) -> None:
        params = TagCreateParams(
            id=self.factory.core.hex_id(1),
            name_ru="Питон",
            name_en="Python",
            slug="python",
        )
        expected = self.factory.core.tag(
            tag_id=1,
            name_ru="Питон",
            name_en="Python",
            slug="python",
        )
        self.storage.create_tag.return_value = expected

        result = await self.use_case.create_tag(params=params)

        assert result == expected
        self.storage.create_tag.assert_called_once_with(tag=expected)

    async def test_update_tag_delegates_to_storage(self) -> None:
        params = TagUpdateParams(
            name_ru="Питон обновлённый",
            name_en="Python Updated",
            slug="python-updated",
        )
        expected = self.factory.core.tag(
            tag_id=1,
            name_ru="Питон обновлённый",
            name_en="Python Updated",
            slug="python-updated",
        )
        self.storage.update_tag.return_value = expected

        result = await self.use_case.update_tag(
            tag_id=self.factory.core.hex_id(1),
            params=params,
        )

        assert result == expected
        self.storage.update_tag.assert_called_once_with(tag=expected)
