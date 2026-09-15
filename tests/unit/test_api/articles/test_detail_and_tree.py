from datetime import UTC, datetime

import pytest_asyncio
from httpx import codes

from core.articles.exceptions import ArticleNotFoundError
from core.articles.schemas import (
    ArticlePublicStatsCollection,
    ArticleTree,
    ArticleTreeFolder,
    ArticleTreeItem,
)
from core.auth.enums import RoleEnum
from core.auth.exceptions import UnauthorizedError
from core.auth.schemas import JwtUser
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from tests.test_cases import ApiTestCase


class TestArticleDetailAndTreeAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.use_case = await self.container.get_articles_use_case()
        self.analytics_use_case = await self.container.get_article_analytics_use_case()
        self.analytics_use_case.get_public_stats.return_value = ArticlePublicStatsCollection(
            values=[],
        )

    def test_get_article(self) -> None:
        tag = self.factory.core.tag(
            tag_id=2,
            name="Old",
            slug="old",
        )
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1),
            title="Detail article",
            content="# Markdown detail",
            slug="detail-article",
            folder="General",
            author_username="admin",
            publish_status=PublishStatusEnum.PUBLISHED,
            published_at="2026-01-02T03:04:05",
            created_at="2026-01-01T03:04:05",
            updated_at="2026-01-03T03:04:05",
            tags=[tag],
        )
        self.use_case.get_article.return_value = article

        response = self.api.get_admin_article(slug="detail-article", only_published=False)

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "id": str(article.id),
            "title": "Detail article",
            "slug": "detail-article",
            "folder": "General",
            "folderId": article.folder.id,
            "folderKey": "general",
            "authorUsername": "admin",
            "publishedAt": "2026-01-02T03:04:05+00:00",
            "publishStatus": "Published",
            "updatedAt": "2026-01-03T03:04:05+00:00",
            "excerpt": "Markdown detail",
            "metadata": {
                "seoTitleRu": None,
                "seoTitleEn": None,
                "seoDescriptionRu": None,
                "seoDescriptionEn": None,
                "coverImageFileId": None,
                "coverImageUrl": None,
                "coverImageAltRu": None,
                "coverImageAltEn": None,
            },
            "tags": [
                {
                    "id": self.factory.core.hex_id(2),
                    "name": "Old",
                    "slug": "old",
                    "translations": {
                        "ru": {"name": "Old"},
                        "en": {"name": "Old"},
                    },
                },
            ],
            "content": "# Markdown detail",
            "createdAt": "2026-01-01T03:04:05+00:00",
            "translations": {
                "ru": {
                    "title": "Detail article",
                    "content": "# Markdown detail",
                },
                "en": {
                    "title": "Detail article",
                    "content": "# Markdown detail",
                },
            },
        }
        self.use_case.get_article.assert_called_once_with(
            slug="detail-article",
            only_published=False,
        )
        self.analytics_use_case.get_public_stats.assert_not_called()
        self.analytics_use_case.track_public_view.assert_not_called()

    def test_public_get_article_does_not_track_view(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(2),
            title="Public article",
            slug="public-article",
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        self.use_case.get_article.return_value = article

        response = self.no_auth_api.get_article(slug="public-article")

        assert response.status_code == codes.OK, response.content
        assert "viewCount" not in response.json()
        assert "reactionCounts" not in response.json()
        self.analytics_use_case.get_public_stats.assert_not_called()
        self.analytics_use_case.track_public_view.assert_not_called()

    def test_get_article_not_found(self) -> None:
        self.use_case.get_article.side_effect = ArticleNotFoundError()

        response = self.api.get_article(slug="missing")

        assert response.status_code == codes.NOT_FOUND
        assert response.json()["message"] == ArticleNotFoundError.message

    def test_get_article_requires_explicit_language(self) -> None:
        response = self.api.get_article(slug="detail-article", language=None)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.get_article.assert_not_called()

    def test_anonymous_cannot_request_admin_draft_article(self) -> None:
        response = self.no_auth_api.get_admin_article(slug="draft", only_published=False)

        assert response.status_code == codes.UNAUTHORIZED
        assert response.json()["message"] == UnauthorizedError.message
        self.use_case.get_article.assert_not_called()

    def test_moderator_can_request_draft_article(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.use_case.get_article.return_value = self.factory.core.article(
            article_id=self.factory.core.hex_id(3),
            title="Draft article",
            slug="draft",
            publish_status=PublishStatusEnum.DRAFT,
        )

        response = self.api.get_admin_article(slug="draft", only_published=False)

        assert response.status_code == codes.OK, response.content
        self.use_case.get_article.assert_called_once_with(slug="draft", only_published=False)

    def test_tree_uses_public_visibility_for_anonymous_users(self) -> None:
        self.use_case.list_tree.return_value = ArticleTree(
            folders=[
                ArticleTreeFolder(
                    folder_id=self.factory.core.hex_id(11),
                    folder_key="engineering",
                    folder="Engineering",
                    articles=[
                        ArticleTreeItem(
                            title="Public article",
                            slug="public-article",
                            publish_status=PublishStatusEnum.PUBLISHED,
                            published_at=datetime.fromisoformat("2026-01-02T03:04:05").replace(
                                tzinfo=UTC,
                            ),
                            updated_at=datetime.fromisoformat("2026-01-03T03:04:05").replace(
                                tzinfo=UTC,
                            ),
                        ),
                    ],
                ),
            ],
        )

        response = self.no_auth_api.get_articles_tree()

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "folders": [
                {
                    "folderId": self.factory.core.hex_id(11),
                    "folderKey": "engineering",
                    "folder": "Engineering",
                    "articles": [
                        {
                            "title": "Public article",
                            "slug": "public-article",
                            "publishStatus": "Published",
                            "publishedAt": "2026-01-02T03:04:05+00:00",
                            "updatedAt": "2026-01-03T03:04:05+00:00",
                        },
                    ],
                },
            ],
        }
        self.use_case.list_tree.assert_called_once_with(
            only_published=True,
            language=LanguageEnum.RU,
        )

    def test_tree_uses_all_visibility_for_moderator(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.use_case.list_tree.return_value = ArticleTree(folders=[])

        response = self.api.get_admin_articles_tree()

        assert response.status_code == codes.OK, response.content
        self.use_case.list_tree.assert_called_once_with(
            only_published=False,
            language=LanguageEnum.RU,
        )

    def test_tree_requires_explicit_language(self) -> None:
        response = self.api.get_articles_tree(language=None)

        assert response.status_code == codes.BAD_REQUEST
        self.use_case.list_tree.assert_not_called()
