import pytest
import pytest_asyncio
from httpx import codes

from core.articles.exceptions import ArticleNotFoundError
from core.articles.schemas import (
    ArticleCreateParams,
    ArticleFolderCreateParams,
    ArticleFolderPriorityUpdateParams,
    ArticleMetadata,
    ArticleUpdateParams,
)
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.response_cache import ResponseCacheDomain
from tests.test_cases import ApiTestCase
from tests.unit.mocks.providers.auth import test_current_datetime


class TestAdminArticlesAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.article_id = (await self.container.get_hex_uuid_id_generator()).get_next()
        self.folder_id = (await self.container.get_hex_uuid_id_generator()).get_next()
        self.use_case = await self.container.get_articles_use_case()

    def test_create_article_saves_author(self) -> None:
        article = self.factory.core.article(
            article_id=self.article_id,
            title="New article",
            content="New content",
            slug="new-article",
            folder="Inbox",
            author_username="test",
            publish_status=PublishStatusEnum.DRAFT,
            created_at="2026-01-01T03:04:05",
            updated_at="2026-01-01T03:04:05",
        )
        self.use_case.create_article.return_value = article

        response = self.api.post_create_article(
            data=self.factory.api.article_request(
                title_ru="Новая статья",
                title_en="New article",
                content_ru="Новое содержимое",
                content_en="New content",
                slug="new-article",
                folder_id=self.folder_id,
                publish_status="Draft",
                tag_ids=[
                    "00000000000040008000000000000031",
                    "00000000000040008000000000000032",
                ],
            ),
        )

        assert response.status_code == codes.CREATED, response.content
        assert response.json()["authorUsername"] == "test"
        self.use_case.create_article.assert_called_once_with(
            params=ArticleCreateParams(
                id=self.article_id,
                slug="new-article",
                title_ru="Новая статья",
                title_en="New article",
                content_ru="Новое содержимое",
                content_en="New content",
                folder_id=self.folder_id,
                author_username="test",
                publish_status=PublishStatusEnum.DRAFT,
                metadata=ArticleMetadata(
                    seo_title_ru="SEO статья",
                    seo_title_en="SEO article",
                    seo_description_ru="Описание для выдачи",
                    seo_description_en="Search result description",
                    cover_image_file_id="0000000000000000000000000000001e",
                    cover_image_file=None,
                    cover_image_url=None,
                    cover_image_alt_ru="Обложка статьи",
                    cover_image_alt_en="Article cover",
                ),
                tag_ids=[
                    "00000000000040008000000000000031",
                    "00000000000040008000000000000032",
                ],
            ),
            current_datetime=test_current_datetime,
        )

    def test_update_article(self) -> None:
        article = self.factory.core.article(
            article_id="00000000000040008000000000000022",
            title="Updated article",
            content="Updated content",
            slug="updated-article",
            folder="Inbox",
            author_username="test",
            publish_status=PublishStatusEnum.PUBLISHED,
            published_at="2026-01-02T03:04:05",
            created_at="2026-01-01T03:04:05",
            updated_at="2026-01-03T03:04:05",
        )
        self.use_case.update_article.return_value = article

        response = self.api.put_update_article(
            slug="old-article",
            data=self.factory.api.article_request(
                title_ru="Обновлённая статья",
                title_en="Updated article",
                content_ru="Обновлённое содержимое",
                content_en="Updated content",
                slug="updated-article",
                folder_id=self.folder_id,
                publish_status="Published",
                metadata={
                    "seoTitleRu": "SEO обновлённая статья",
                    "seoTitleEn": "SEO updated article",
                    "seoDescriptionRu": "Обновлённое описание",
                    "seoDescriptionEn": "Updated description",
                    "coverImageFileId": "0000000000000000000000000000001e",
                    "coverImageAltRu": "Обложка обновлённой статьи",
                    "coverImageAltEn": "Updated article cover",
                },
                tag_ids=["00000000000040008000000000000031"],
            ),
        )

        assert response.status_code == codes.OK, response.content
        assert response.json()["slug"] == "updated-article"
        self.use_case.update_article.assert_called_once_with(
            slug="old-article",
            params=ArticleUpdateParams(
                slug="updated-article",
                title_ru="Обновлённая статья",
                title_en="Updated article",
                content_ru="Обновлённое содержимое",
                content_en="Updated content",
                folder_id=self.folder_id,
                publish_status=PublishStatusEnum.PUBLISHED,
                metadata=ArticleMetadata(
                    seo_title_ru="SEO обновлённая статья",
                    seo_title_en="SEO updated article",
                    seo_description_ru="Обновлённое описание",
                    seo_description_en="Updated description",
                    cover_image_file_id="0000000000000000000000000000001e",
                    cover_image_file=None,
                    cover_image_url=None,
                    cover_image_alt_ru="Обложка обновлённой статьи",
                    cover_image_alt_en="Updated article cover",
                ),
                tag_ids=["00000000000040008000000000000031"],
            ),
            current_datetime=test_current_datetime,
        )

    def test_create_article_requires_metadata_object(self) -> None:
        data = self.factory.api.article_request()
        del data["metadata"]

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_allows_null_metadata_fields(self) -> None:
        self.use_case.create_article.return_value = self.factory.core.article(
            article_id=self.article_id,
            slug="nullable-metadata",
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        data = self.factory.api.article_request(
            slug="nullable-metadata",
            publish_status="Published",
            metadata={
                "seoTitleRu": None,
                "seoTitleEn": None,
                "seoDescriptionRu": None,
                "seoDescriptionEn": None,
                "coverImageFileId": None,
                "coverImageAltRu": None,
                "coverImageAltEn": None,
            },
        )

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.CREATED, response.content
        params = self.use_case.create_article.call_args.kwargs["params"]
        assert params.publish_status == PublishStatusEnum.PUBLISHED
        assert params.metadata == ArticleMetadata(
            seo_title_ru=None,
            seo_title_en=None,
            seo_description_ru=None,
            seo_description_en=None,
            cover_image_file_id=None,
            cover_image_file=None,
            cover_image_url=None,
            cover_image_alt_ru=None,
            cover_image_alt_en=None,
        )

    @pytest.mark.parametrize("slug", ["", "   ", "Invalid Slug", "invalid_slug", "-invalid"])
    def test_create_article_rejects_blank_or_invalid_slug(self, slug: str) -> None:
        response = self.api.post_create_article(data=self.factory.api.article_request(slug=slug))

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_rejects_whitespace_required_translation_fields(self) -> None:
        response = self.api.post_create_article(
            data=self.factory.api.article_request(title_ru="   "),
        )

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_requires_folder_id(self) -> None:
        data = self.factory.api.article_request()
        del data["folderId"]

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_rejects_blank_folder_id(self) -> None:
        response = self.api.post_create_article(
            data=self.factory.api.article_request(folder_id="   "),
        )

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_rejects_legacy_cover_url_input(self) -> None:
        data = self.factory.api.article_request()
        data["metadata"]["coverImageUrl"] = "https://example.com/cover.jpg"

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_rejects_too_long_content(self) -> None:
        response = self.api.post_create_article(
            data=self.factory.api.article_request(content_en="x" * 100_001),
        )

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_requires_all_translation_fields(self) -> None:
        data = self.factory.api.article_request()
        del data["translations"]["en"]["content"]

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_create_article_rejects_folder_inside_translations(self) -> None:
        data = self.factory.api.article_request()
        data["translations"]["en"]["folder"] = "Legacy folder"

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.create_article.assert_not_called()

    def test_list_article_folders(self) -> None:
        self.use_case.list_folders.return_value = self.factory.core.article_folders(
            values=[
                self.factory.core.article_folder(
                    folder_id=self.factory.core.hex_id(2),
                    key="architecture",
                    name_ru="Архитектура",
                    name_en="Architecture",
                    priority=1,
                ),
            ],
        )

        response = self.api.get_admin_article_folders(language="en")

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "folders": [
                {
                    "id": self.factory.core.hex_id(2),
                    "key": "architecture",
                    "name": "Architecture",
                    "priority": 1,
                    "translations": {
                        "ru": {"name": "Архитектура"},
                        "en": {"name": "Architecture"},
                    },
                },
            ],
        }
        self.use_case.list_folders.assert_called_once_with(language=LanguageEnum.EN)

    def test_create_article_folder(self) -> None:
        self.use_case.create_folder.return_value = self.factory.core.article_folder(
            folder_id=self.folder_id,
            key="backend",
            name_ru="Бэкенд",
            name_en="Backend",
            priority=3,
        )

        response = self.api.post_create_article_folder(
            data=self.factory.api.article_folder_request(
                key="backend",
                name_ru="Бэкенд",
                name_en="Backend",
            ),
            language="ru",
        )

        assert response.status_code == codes.CREATED, response.content
        assert response.json()["id"] == self.folder_id
        assert response.json()["name"] == "Бэкенд"
        self.use_case.create_folder.assert_called_once_with(
            params=ArticleFolderCreateParams(
                id=self.folder_id,
                key="backend",
                name_ru="Бэкенд",
                name_en="Backend",
            ),
        )

    def test_update_article_folder_priorities(self) -> None:
        response = self.api.put_update_article_folder_priorities(ordered_ids=[2, 1])

        assert response.status_code == codes.NO_CONTENT
        self.use_case.update_folder_priorities.assert_called_once_with(
            params=ArticleFolderPriorityUpdateParams(
                ordered_ids=(self.factory.core.hex_id(2), self.factory.core.hex_id(1)),
            ),
        )

    def test_create_article_validation_error_does_not_schedule_cache_invalidation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        invalidated_domains: list[ResponseCacheDomain] = []

        async def fake_invalidate_response_cache_domain_for_mutation(
            *,
            request: object,
            domain: ResponseCacheDomain,
            post_commit_actions: object,
        ) -> None:
            _ = request, post_commit_actions
            invalidated_domains.append(domain)

        monkeypatch.setattr(
            "entrypoints.litestar.api.articles.endpoints.invalidate_response_cache_domain_for_mutation",
            fake_invalidate_response_cache_domain_for_mutation,
            raising=False,
        )
        data = self.factory.api.article_request()
        del data["translations"]["en"]["content"]

        response = self.api.post_create_article(data=data)

        assert response.status_code == codes.BAD_REQUEST
        assert invalidated_domains == []

    def test_delete_article_not_found(self) -> None:
        self.use_case.delete_article.side_effect = ArticleNotFoundError()

        response = self.api.delete_article(slug="missing")

        assert response.status_code == codes.NOT_FOUND
        assert response.json()["message"] == ArticleNotFoundError.message

    def test_delete_article(self) -> None:
        response = self.api.delete_article(slug="old-article")

        assert response.status_code == codes.NO_CONTENT
        self.use_case.delete_article.assert_called_once_with(
            slug="old-article",
            current_datetime=test_current_datetime,
        )

    def test_set_published_status_to_article(self) -> None:
        response = self.api.post_set_published_status_to_article(slug="draft-article")

        assert response.status_code == codes.NO_CONTENT
        self.use_case.switch_article_publish_status.assert_called_once_with(
            slug="draft-article",
            publish_status=PublishStatusEnum.PUBLISHED,
        )

    def test_set_draft_status_to_article(self) -> None:
        response = self.api.post_set_draft_status_to_article(slug="published-article")

        assert response.status_code == codes.NO_CONTENT
        self.use_case.switch_article_publish_status.assert_called_once_with(
            slug="published-article",
            publish_status=PublishStatusEnum.DRAFT,
        )

    def test_successful_article_mutations_schedule_articles_cache_invalidation(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        invalidated_domains: list[ResponseCacheDomain] = []

        async def fake_invalidate_response_cache_domain_for_mutation(
            *,
            request: object,
            domain: ResponseCacheDomain,
            post_commit_actions: object,
        ) -> None:
            _ = request, post_commit_actions
            invalidated_domains.append(domain)

        monkeypatch.setattr(
            "entrypoints.litestar.api.articles.endpoints.invalidate_response_cache_domain_for_mutation",
            fake_invalidate_response_cache_domain_for_mutation,
            raising=False,
        )
        created_article = self.factory.core.article(
            article_id=self.article_id,
            slug="new-article",
            publish_status=PublishStatusEnum.DRAFT,
        )
        updated_article = self.factory.core.article(
            article_id="00000000000040008000000000000022",
            slug="updated-article",
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        self.use_case.create_article.return_value = created_article
        self.use_case.update_article.return_value = updated_article

        responses = [
            self.api.post_create_article(data=self.factory.api.article_request(slug="new-article")),
            self.api.put_update_article(
                slug="old-article",
                data=self.factory.api.article_request(
                    slug="updated-article",
                    metadata={
                        "seoTitleRu": "SEO обновлённая статья",
                        "seoTitleEn": "SEO updated article",
                        "seoDescriptionRu": "Обновлённое описание",
                        "seoDescriptionEn": "Updated description",
                        "coverImageFileId": "0000000000000000000000000000001e",
                        "coverImageAltRu": "Обложка обновлённой статьи",
                        "coverImageAltEn": "Updated article cover",
                    },
                ),
            ),
            self.api.delete_article(slug="updated-article"),
            self.api.post_set_published_status_to_article(slug="draft-article"),
            self.api.post_set_draft_status_to_article(slug="published-article"),
        ]

        assert [response.status_code for response in responses] == [
            codes.CREATED,
            codes.OK,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
            codes.NO_CONTENT,
        ]
        assert invalidated_domains == [ResponseCacheDomain.ARTICLES] * 5
