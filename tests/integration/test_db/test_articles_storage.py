import asyncio
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.articles.exceptions import (
    ArticleFolderNotFoundError,
    ArticleNotFoundError,
    TagNotFoundError,
)
from core.articles.schemas import ArticleFilters
from core.enums import PublishStatusEnum
from core.files.enums import FilePurpose
from core.i18n.enums import LanguageEnum
from infra.postgresql.models import ArticleFileUsageModel, ArticleModel, ArticleToTagSecondaryModel
from infra.postgresql.storages.articles import ArticlesDatabaseStorage
from tests.helpers.storage import StorageHelper
from tests.test_cases import StorageTestCase


class TestArticlesDatabaseStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.storage = ArticlesDatabaseStorage(session=self.db_session)

    async def test_get_article_by_slug_success(self) -> None:
        tag = self.factory.core.tag(tag_id=self.factory.core.hex_id(1), slug="python")
        django_tag = self.factory.core.tag(
            tag_id=self.factory.core.hex_id(2),
            name="Django",
            slug="django",
        )
        await self.storage_helper.create_tags(tags=[tag, django_tag])
        await self.storage_helper.create_article(
            article=self.factory.core.article(
                title="Test Article",
                content="Test content",
                slug="test-article",
                folder="Python",
                tags=[tag, django_tag],
                publish_status=PublishStatusEnum.PUBLISHED,
                published_at="2024-01-01T00:00:00",
                created_at="2024-01-01T00:00:00",
                updated_at="2024-01-01T00:00:00",
            ),
        )

        result = await self.storage.get_article_by_slug(
            slug="test-article",
            lock=False,
        )

        assert result.localized_title(language=LanguageEnum.RU) == "Test Article"
        assert self.collections.slugs(result.tags) == ["python", "django"]

    async def test_get_article_by_slug_returns_canonical_translations(self) -> None:
        cover = self.factory.core.stored_file(
            file_id=100,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/localized-cover.png",
            name="Localized cover",
            original_name="cover.png",
        )
        await self.storage_helper.create_file(cover)
        await self.storage_helper.create_article(
            article=self.factory.core.article(
                title_ru="Русская статья",
                title_en="English article",
                content_ru="Русское содержимое",
                content_en="English content",
                folder_ru="Русская папка",
                folder_en="English folder",
                slug="localized-article",
                seo_title_ru="SEO русская статья",
                seo_title_en="SEO English article",
                seo_description_ru="Описание русской статьи",
                seo_description_en="English article description",
                cover_image_file_id=cover.id,
                cover_image_alt_ru="Обложка",
                cover_image_alt_en="Cover",
            ),
        )

        result = await self.storage.get_article_by_slug(
            slug="localized-article",
            lock=False,
        )

        assert not hasattr(result, "title")
        assert not hasattr(result, "content")
        assert result.folder.id == self.factory.core.hex_id_from_text("article-folder:general")
        assert result.folder.key == "general"
        assert result.localized_title(language=LanguageEnum.RU) == "Русская статья"
        assert result.localized_content(language=LanguageEnum.RU) == "Русское содержимое"
        assert result.localized_folder(language=LanguageEnum.RU) == "Русская папка"
        assert result.localized_title(language=LanguageEnum.EN) == "English article"
        assert result.localized_content(language=LanguageEnum.EN) == "English content"
        assert result.localized_folder(language=LanguageEnum.EN) == "English folder"
        assert result.metadata.seo_title_ru == "SEO русская статья"
        assert result.metadata.seo_title_en == "SEO English article"
        assert result.metadata.seo_description_ru == "Описание русской статьи"
        assert result.metadata.seo_description_en == "English article description"
        assert result.metadata.cover_image_file_id == cover.id
        assert result.metadata.cover_image_url is None
        assert result.metadata.cover_image_file == cover
        assert result.metadata.cover_image_alt_ru == "Обложка"
        assert result.metadata.cover_image_alt_en == "Cover"

    async def test_create_and_update_article_syncs_managed_file_links(self) -> None:
        cover = self.factory.core.stored_file(
            file_id=110,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/initial-cover.png",
            name="Initial cover",
            original_name="initial-cover.png",
        )
        updated_cover = self.factory.core.stored_file(
            file_id=111,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/updated-cover.png",
            name="Updated cover",
            original_name="updated-cover.png",
        )
        first_content = self.factory.core.stored_file(
            file_id=112,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/first-content.png",
            name="First content",
            original_name="first-content.png",
        )
        second_content = self.factory.core.stored_file(
            file_id=113,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/second-content.png",
            name="Second content",
            original_name="second-content.png",
        )
        for file in (cover, updated_cover, first_content, second_content):
            await self.storage_helper.create_file(file)
        article_folder = self.factory.core.article_folder()
        await self.storage_helper.ensure_article_folder(folder=article_folder)

        created = await self.storage.create_article(
            article=self.factory.core.article(
                slug="managed-file-links",
                folder_id=article_folder.id,
                cover_image_file_id=cover.id,
                content_file_ids=frozenset({first_content.id}),
            ),
        )
        updated = await self.storage.update_article(
            article=self.factory.core.article(
                article_id=created.id,
                slug="managed-file-links",
                folder_id=article_folder.id,
                cover_image_file_id=updated_cover.id,
                content_file_ids=frozenset({second_content.id}),
            ),
        )
        usage_file_ids = await self.db_session.scalars(
            select(ArticleFileUsageModel.file_id)
            .where(ArticleFileUsageModel.article_id == created.id)
            .order_by(ArticleFileUsageModel.file_id),
        )

        assert created.metadata.cover_image_file_id == cover.id
        assert created.metadata.cover_image_url is None
        assert created.metadata.cover_image_file == cover
        assert created.content_file_ids == frozenset({first_content.id})
        assert updated.metadata.cover_image_file_id == updated_cover.id
        assert updated.metadata.cover_image_url is None
        assert updated.metadata.cover_image_file == updated_cover
        assert updated.content_file_ids == frozenset({second_content.id})
        assert list(usage_file_ids) == [second_content.id]

    async def test_update_article_with_unchanged_file_usage_is_idempotent(self) -> None:
        content_image = self.factory.core.stored_file(
            file_id=114,
            purpose=FilePurpose.ARTICLE_CONTENT_IMAGE,
            relative_path="article-content-images/unchanged-content.png",
            name="Unchanged content",
            original_name="unchanged-content.png",
        )
        await self.storage_helper.create_file(content_image)
        article = self.factory.core.article(
            slug="unchanged-file-usage",
            content_file_ids=frozenset({content_image.id}),
        )
        await self.storage_helper.ensure_article_folder(folder=article.folder)
        created = await self.storage.create_article(article=article)

        updated = await self.storage.update_article(article=created)

        assert updated.content_file_ids == frozenset({content_image.id})

    async def test_update_article_with_unchanged_tags_is_idempotent(self) -> None:
        python = self.factory.core.tag(tag_id=self.factory.core.hex_id(1), slug="python")
        postgres = self.factory.core.tag(tag_id=self.factory.core.hex_id(2), slug="postgres")
        await self.storage_helper.create_tags(tags=[python, postgres])
        article = self.factory.core.article(
            slug="unchanged-tags",
            tags=[python, postgres],
        )
        await self.storage_helper.ensure_article_folder(folder=article.folder)
        created = await self.storage.create_article(article=article)

        updated = await self.storage.update_article(article=created)

        assert self.collections.slugs(updated.tags) == ["python", "postgres"]

    async def test_get_article_by_slug_not_found(self) -> None:
        with pytest.raises(ArticleNotFoundError):
            await self.storage.get_article_by_slug(
                slug="non-existent",
                lock=False,
            )

    async def test_locked_get_serializes_same_article_updates_and_reloads_state(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        slug = "concurrent-update"
        async with session_maker() as seed_session:
            seed_helper = StorageHelper(session=seed_session)
            await seed_helper.create_article(
                article=self.factory.core.article(slug=slug, title_ru="Initial"),
            )
            await seed_session.commit()

        async with session_maker() as first_session, session_maker() as second_session:
            first_storage = ArticlesDatabaseStorage(session=first_session)
            second_storage = ArticlesDatabaseStorage(session=second_session)
            first = await first_storage.get_article_by_slug(slug=slug, lock=True)
            assert first.title_ru == "Initial"

            second_get = asyncio.create_task(
                second_storage.get_article_by_slug(slug=slug, lock=True),
            )
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(second_get), timeout=0.1)

            await first_session.execute(
                update(ArticleModel)
                .where(ArticleModel.slug == slug)
                .values(title_ru="First update"),
            )
            await first_session.commit()

            second = await second_get
            assert second.title_ru == "First update"
            await second_session.rollback()

    async def test_locked_get_observes_concurrent_article_deletion(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> None:
        slug = "concurrent-delete"
        async with session_maker() as seed_session:
            seed_helper = StorageHelper(session=seed_session)
            await seed_helper.create_article(article=self.factory.core.article(slug=slug))
            await seed_session.commit()

        async with session_maker() as first_session, session_maker() as second_session:
            first_storage = ArticlesDatabaseStorage(session=first_session)
            second_storage = ArticlesDatabaseStorage(session=second_session)
            await first_storage.get_article_by_slug(slug=slug, lock=True)

            second_get = asyncio.create_task(
                second_storage.get_article_by_slug(slug=slug, lock=True),
            )
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(second_get), timeout=0.1)

            await first_storage.delete_article(slug=slug)
            await first_session.commit()

            with pytest.raises(ArticleNotFoundError):
                await second_get
            await second_session.rollback()

    async def test_list_articles_filters_by_tag_and_published_status(self) -> None:
        python = self.factory.core.tag(tag_id=self.factory.core.hex_id(1), slug="python")
        draft_tag = self.factory.core.tag(tag_id=self.factory.core.hex_id(2), slug="draft")
        await self.storage_helper.create_tags(tags=[python, draft_tag])
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="Published Python",
                    slug="published-python",
                    tags=[python],
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-01T00:00:00",
                    created_at="2024-02-01T00:00:00",
                    updated_at="2024-02-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Draft Python",
                    slug="draft-python",
                    tags=[python],
                    publish_status=PublishStatusEnum.DRAFT,
                    created_at="2024-03-01T00:00:00",
                    updated_at="2024-03-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Other",
                    slug="other",
                    tags=[draft_tag],
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-04-01T00:00:00",
                    created_at="2024-04-01T00:00:00",
                    updated_at="2024-04-01T00:00:00",
                ),
            ],
        )

        articles, total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                tag_slug="python",
                published_from=None,
                published_to=None,
                search_query=None,
            ),
        )

        assert self.collections.slugs(articles) == ["published-python"]
        assert total_count == 1

        draft_articles, draft_total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=False,
                publish_status=PublishStatusEnum.DRAFT,
                tag_slug="python",
                published_from=None,
                published_to=None,
                search_query=None,
            ),
        )

        assert self.collections.slugs(draft_articles) == ["draft-python"]
        assert draft_total_count == 1

    async def test_list_articles_filters_published_without_pagination_or_tags_for_seo(self) -> None:
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="Older published",
                    slug="older-published",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-01T00:00:00",
                    created_at="2024-02-01T00:00:00",
                    updated_at="2024-02-02T00:00:00",
                ),
                self.factory.core.article(
                    title="Draft",
                    slug="draft",
                    publish_status=PublishStatusEnum.DRAFT,
                    published_at=None,
                    created_at="2024-02-03T00:00:00",
                    updated_at="2024-02-03T00:00:00",
                ),
                self.factory.core.article(
                    title="Newer published",
                    slug="newer-published",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-03-01T00:00:00",
                    created_at="2024-03-01T00:00:00",
                    updated_at="2024-03-02T00:00:00",
                ),
            ],
        )

        articles, total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                only_published=True,
                include_tags=False,
                include_files=False,
                order_for_seo=True,
            ),
        )

        assert self.collections.slugs(articles) == ["newer-published", "older-published"]
        assert [list(article.tags) for article in articles] == [[], []]
        assert total_count == 2

    async def test_list_articles_sorts_published_before_drafts_for_admin(self) -> None:
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="Draft",
                    slug="draft",
                    publish_status=PublishStatusEnum.DRAFT,
                    created_at="2024-05-01T00:00:00",
                    updated_at="2024-05-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Older Published",
                    slug="older-published",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-01-01T00:00:00",
                    created_at="2024-01-01T00:00:00",
                    updated_at="2024-01-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Newer Published",
                    slug="newer-published",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-04-01T00:00:00",
                    created_at="2024-04-01T00:00:00",
                    updated_at="2024-04-01T00:00:00",
                ),
            ],
        )

        articles, _total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=False,
                tag_slug=None,
                published_from=None,
                published_to=None,
                search_query=None,
            ),
        )

        assert self.collections.slugs(articles) == [
            "newer-published",
            "older-published",
            "draft",
        ]

    async def test_list_articles_filters_by_inclusive_publish_date_range(self) -> None:
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="Before",
                    slug="before",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-01-31T23:59:59",
                    created_at="2024-01-31T23:59:59",
                    updated_at="2024-01-31T23:59:59",
                ),
                self.factory.core.article(
                    title="Range Start",
                    slug="range-start",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-01T00:00:00",
                    created_at="2024-02-01T00:00:00",
                    updated_at="2024-02-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Range End",
                    slug="range-end",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-29T23:59:59",
                    created_at="2024-02-29T23:59:59",
                    updated_at="2024-02-29T23:59:59",
                ),
                self.factory.core.article(
                    title="After",
                    slug="after",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-03-01T00:00:00",
                    created_at="2024-03-01T00:00:00",
                    updated_at="2024-03-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Draft",
                    slug="draft",
                    publish_status=PublishStatusEnum.DRAFT,
                    created_at="2024-02-15T00:00:00",
                    updated_at="2024-02-15T00:00:00",
                ),
            ],
        )

        articles, total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=False,
                tag_slug=None,
                published_from=date(2024, 2, 1),
                published_to=date(2024, 2, 29),
                search_query=None,
            ),
        )

        assert self.collections.slugs(articles) == ["range-end", "range-start"]
        assert total_count == 2

    async def test_list_articles_searches_by_title_and_content(self) -> None:
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="PostgreSQL full text search",
                    content="Indexing articles without a table scan.",
                    slug="title-match",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-05-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Dependency injection",
                    content="Dishka providers wire use cases to storage adapters.",
                    slug="content-match",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-04-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Unrelated",
                    content="No matching terms here.",
                    slug="unrelated",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-06-01T00:00:00",
                ),
            ],
        )

        title_articles, _title_total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                tag_slug=None,
                published_from=None,
                published_to=None,
                search_query="full text",
            ),
        )
        content_articles, _content_total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                tag_slug=None,
                published_from=None,
                published_to=None,
                search_query="dishka providers",
            ),
        )

        assert self.collections.slugs(title_articles) == ["title-match"]
        assert self.collections.slugs(content_articles) == ["content-match"]

    async def test_list_articles_searches_only_requested_language_vector(self) -> None:
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title_ru="Очереди задач",
                    title_en="Task queues",
                    content_ru="Фоновая обработка заданий.",
                    content_en="Background job processing.",
                    slug="task-queues",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-05-01T00:00:00",
                ),
                self.factory.core.article(
                    title_ru="Индексы PostgreSQL",
                    title_en="Database indexes",
                    content_ru="Поиск по документам.",
                    content_en="Query planning details.",
                    slug="database-indexes",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-04-01T00:00:00",
                ),
            ],
        )

        ru_articles, _ru_total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                tag_slug=None,
                published_from=None,
                published_to=None,
                search_query="документам",
            ),
        )
        en_articles, _en_total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.EN,
                only_published=True,
                tag_slug=None,
                published_from=None,
                published_to=None,
                search_query="background",
            ),
        )

        assert self.collections.slugs(ru_articles) == ["database-indexes"]
        assert self.collections.slugs(en_articles) == ["task-queues"]

    async def test_list_articles_composes_tag_date_and_search_filters(self) -> None:
        python = self.factory.core.tag(tag_id=self.factory.core.hex_id(1), slug="python")
        database = self.factory.core.tag(tag_id=self.factory.core.hex_id(2), slug="database")
        await self.storage_helper.create_tags(tags=[python, database])
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="Python database indexing",
                    content="PostgreSQL search vectors for articles.",
                    slug="match",
                    tags=[python],
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-10T00:00:00",
                ),
                self.factory.core.article(
                    title="Python old indexing",
                    content="PostgreSQL search vectors for articles.",
                    slug="old",
                    tags=[python],
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-01-10T00:00:00",
                ),
                self.factory.core.article(
                    title="Database indexing",
                    content="PostgreSQL search vectors for articles.",
                    slug="wrong-tag",
                    tags=[database],
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-10T00:00:00",
                ),
            ],
        )

        articles, _total_count = await self.storage.list_articles(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                tag_slug="python",
                published_from=date(2024, 2, 1),
                published_to=date(2024, 2, 29),
                search_query="search vectors",
            ),
        )

        assert self.collections.slugs(articles) == ["match"]

    async def test_list_tree_groups_folders_and_hides_drafts_for_public(self) -> None:
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="B Article",
                    slug="b-article",
                    folder="Backend",
                    folder_id=self.factory.core.hex_id(2),
                    folder_key="backend",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-01-01T00:00:00",
                ),
                self.factory.core.article(
                    title="A Article",
                    slug="a-article",
                    folder="Architecture",
                    folder_id=self.factory.core.hex_id(1),
                    folder_key="architecture",
                    publish_status=PublishStatusEnum.PUBLISHED,
                    published_at="2024-02-01T00:00:00",
                ),
                self.factory.core.article(
                    title="Draft",
                    slug="draft",
                    folder="Architecture",
                    folder_id=self.factory.core.hex_id(1),
                    folder_key="architecture",
                    publish_status=PublishStatusEnum.DRAFT,
                ),
            ],
        )

        public_items = await self.storage.list_tree_items(
            only_published=True,
            language=LanguageEnum.RU,
        )
        admin_items = await self.storage.list_tree_items(
            only_published=False,
            language=LanguageEnum.RU,
        )

        assert [(item.folder, item.slug) for item in public_items] == [
            ("Architecture", "a-article"),
            ("Backend", "b-article"),
        ]
        assert [(item.folder_id, item.folder_key) for item in public_items] == [
            (self.factory.core.hex_id(1), "architecture"),
            (self.factory.core.hex_id(2), "backend"),
        ]
        assert [(item.folder, item.slug) for item in admin_items] == [
            ("Architecture", "a-article"),
            ("Architecture", "draft"),
            ("Backend", "b-article"),
        ]

    async def test_list_tree_orders_folders_by_priority(self) -> None:
        await self.storage_helper.create_article_folder(
            folder=self.factory.core.article_folder(
                folder_id=self.factory.core.hex_id(1),
                key="first",
                name_ru="Первая",
                name_en="First",
                priority=2,
            ),
        )
        await self.storage_helper.create_article_folder(
            folder=self.factory.core.article_folder(
                folder_id=self.factory.core.hex_id(2),
                key="second",
                name_ru="Вторая",
                name_en="Second",
                priority=1,
            ),
        )
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    title="First article",
                    slug="first-article",
                    folder_id=self.factory.core.hex_id(1),
                    folder_key="first",
                    folder_priority=2,
                    folder_ru="Первая",
                    folder_en="First",
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
                self.factory.core.article(
                    title="Second article",
                    slug="second-article",
                    folder_id=self.factory.core.hex_id(2),
                    folder_key="second",
                    folder_priority=1,
                    folder_ru="Вторая",
                    folder_en="Second",
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
            ],
        )

        items = await self.storage.list_tree_items(
            only_published=True,
            language=LanguageEnum.EN,
        )

        assert [(item.folder_key, item.slug) for item in items] == [
            ("second", "second-article"),
            ("first", "first-article"),
        ]

    async def test_folder_create_list_get_and_reorder(self) -> None:
        first = await self.storage.create_folder(
            folder=self.factory.core.article_folder(
                folder_id=self.factory.core.hex_id(10),
                key="backend",
                name_ru="Бэкенд",
                name_en="Backend",
                priority=1,
            ),
        )
        second = await self.storage.create_folder(
            folder=self.factory.core.article_folder(
                folder_id=self.factory.core.hex_id(11),
                key="architecture",
                name_ru="Архитектура",
                name_en="Architecture",
                priority=2,
            ),
        )

        initial = await self.storage.list_folders(language=LanguageEnum.EN)
        loaded = await self.storage.get_folder_by_id(folder_id=first.id)
        await self.storage.update_folder_priorities(
            ordered_ids=(second.id, first.id),
        )
        reordered = await self.storage.list_folders(language=LanguageEnum.EN)
        initial_test_folders = [folder for folder in initial if folder.id in {first.id, second.id}]
        reordered_test_folders = [
            folder for folder in reordered if folder.id in {first.id, second.id}
        ]

        assert [folder.key for folder in initial_test_folders] == ["backend", "architecture"]
        assert [folder.priority for folder in initial_test_folders] == [1, 2]
        assert loaded == first
        assert [folder.key for folder in reordered_test_folders] == ["architecture", "backend"]
        assert [folder.priority for folder in reordered_test_folders] == [1, 2]

    async def test_folder_key_exists_matches_case_insensitively(self) -> None:
        await self.storage.create_folder(
            folder=self.factory.core.article_folder(
                folder_id=self.factory.core.hex_id(10),
                key="backend",
                name_ru="Бэкенд",
                name_en="Backend",
                priority=1,
            ),
        )

        assert await self.storage.folder_key_exists(key="BACKEND")
        assert not await self.storage.folder_key_exists(key="frontend")

    async def test_get_missing_folder_raises_not_found(self) -> None:
        with pytest.raises(ArticleFolderNotFoundError):
            await self.storage.get_folder_by_id(folder_id=self.factory.core.hex_id(404))

    async def test_update_article_publish_status_sets_first_published_at_only_once(self) -> None:
        await self.storage_helper.create_article(
            article=self.factory.core.article(slug="draft", publish_status=PublishStatusEnum.DRAFT),
        )

        await self.storage.update_article_publish_status(
            slug="draft",
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        first = await self.storage.get_article_by_slug(
            slug="draft",
            lock=False,
        )
        await self.storage.update_article_publish_status(
            slug="draft",
            publish_status=PublishStatusEnum.DRAFT,
        )
        await self.storage.update_article_publish_status(
            slug="draft",
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        second = await self.storage.get_article_by_slug(
            slug="draft",
            lock=False,
        )

        assert first.published_at is not None
        assert second.published_at == first.published_at

    async def test_list_tags_can_require_a_published_article(self) -> None:
        published_tag = self.factory.core.tag(
            tag_id=self.factory.core.hex_id(1),
            name="Published",
            slug="published",
        )
        draft_tag = self.factory.core.tag(
            tag_id=self.factory.core.hex_id(2),
            name="Draft",
            slug="draft",
        )
        unused_tag = self.factory.core.tag(
            tag_id=self.factory.core.hex_id(3),
            name="Unused",
            slug="unused",
        )
        await self.storage_helper.create_tags(tags=[published_tag, draft_tag, unused_tag])
        await self.storage_helper.create_articles(
            articles=[
                self.factory.core.article(
                    slug="first-published",
                    tags=[published_tag],
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
                self.factory.core.article(
                    slug="second-published",
                    tags=[published_tag],
                    publish_status=PublishStatusEnum.PUBLISHED,
                ),
                self.factory.core.article(
                    slug="draft",
                    tags=[draft_tag],
                    publish_status=PublishStatusEnum.DRAFT,
                ),
            ],
        )

        public_tags = await self.storage.list_tags(
            language=LanguageEnum.EN,
            only_with_published_articles=True,
        )
        all_tags = await self.storage.list_tags(
            language=LanguageEnum.EN,
            only_with_published_articles=False,
        )

        assert self.collections.slugs(public_tags) == ["published"]
        assert self.collections.slugs(all_tags) == ["draft", "published", "unused"]

    async def test_delete_tag_physically_removes_tag_and_article_association(self) -> None:
        tag = self.factory.core.tag(tag_id=self.factory.core.hex_id(1), slug="python")
        await self.storage.create_tag(tag=tag)
        await self.storage_helper.create_article(
            article=self.factory.core.article(slug="tagged-article", tags=[tag]),
        )

        await self.storage.delete_tag(tag_id=self.factory.core.hex_id(1))

        tags = await self.storage.list_tags(
            language=LanguageEnum.RU,
            only_with_published_articles=False,
        )
        article_tag_link = await self.db_session.scalar(
            select(ArticleToTagSecondaryModel).where(
                ArticleToTagSecondaryModel.tag_id == self.factory.core.hex_id(1),
            ),
        )

        assert tags.values == []
        assert article_tag_link is None
        with pytest.raises(TagNotFoundError):
            await self.storage.update_tag(tag=tag)

    async def test_search_tags_matches_typo(self) -> None:
        await self.storage_helper.create_tags(
            tags=[
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(1), name="Python", slug="python"
                ),
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(2), name="Django", slug="django"
                ),
            ],
        )

        tags = await self.storage.search_tags(
            search_name="pythno",
            limit=10,
            language=LanguageEnum.EN,
        )

        assert self.collections.names_en(tags) == ["Python"]

    async def test_search_tags_matches_secondary_language_name(self) -> None:
        await self.storage_helper.create_tags(
            tags=[
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(1),
                    name_ru="Базы данных",
                    name_en="Databases",
                    slug="databases",
                ),
            ],
        )

        tags = await self.storage.search_tags(
            search_name="базы",
            limit=10,
            language=LanguageEnum.EN,
        )

        assert self.collections.names_en(tags) == ["Databases"]

    async def test_search_tags_ranks_active_language_matches_before_slug_matches(self) -> None:
        await self.storage_helper.create_tags(
            tags=[
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(1),
                    name="Package tooling",
                    slug="python-packages",
                ),
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(2),
                    name="Python",
                    slug="language",
                ),
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(3),
                    name="Python internals",
                    slug="runtime",
                ),
            ],
        )

        tags = await self.storage.search_tags(
            search_name="python",
            limit=10,
            language=LanguageEnum.EN,
        )

        assert self.collections.names_en(tags)[:2] == ["Python", "Python internals"]

    async def test_search_tags_respects_limit(self) -> None:
        await self.storage_helper.create_tags(
            tags=[
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(1), name="Limit A", slug="limit-a"
                ),
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(2), name="Limit B", slug="limit-b"
                ),
                self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(3), name="Limit C", slug="limit-c"
                ),
            ],
        )

        tags = await self.storage.search_tags(
            search_name="limit",
            limit=2,
            language=LanguageEnum.EN,
        )

        assert len(tags) == 2

    async def test_update_unknown_tag_raises_not_found(self) -> None:
        with pytest.raises(TagNotFoundError):
            await self.storage.update_tag(
                tag=self.factory.core.tag(
                    tag_id=self.factory.core.hex_id(999), name="Missing", slug="missing"
                ),
            )
