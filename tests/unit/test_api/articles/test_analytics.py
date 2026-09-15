from datetime import date

import pytest_asyncio
from httpx import codes

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.schemas import (
    ArticleAnalyticsArticleStats,
    ArticleAnalyticsDailyStats,
    ArticleAnalyticsStats,
    ArticleAnalyticsTotals,
    ArticlePublicStats,
    ArticlePublicStatsCollection,
    ArticleReactionCounts,
)
from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.i18n.enums import LanguageEnum
from tests.test_cases import ApiTestCase


class TestArticleAnalyticsAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.articles_use_case = await self.container.get_articles_use_case()
        self.analytics_use_case = await self.container.get_article_analytics_use_case()
        self.config = await self.container.get_article_analytics_config()

    def test_track_public_view(self) -> None:
        article = self.factory.core.article(
            article_id="00000000000040008000000000000041",
            title="Public article",
            slug="public-article",
        )
        self.articles_use_case.get_article.return_value = article

        response = self.no_auth_api.post_article_view(slug="public-article")

        assert response.status_code == codes.NO_CONTENT, response.content
        self.articles_use_case.get_article.assert_called_once_with(
            slug="public-article",
            only_published=True,
        )
        self.analytics_use_case.track_public_view.assert_called_once_with(
            article=article,
            referrer=None,
            config=self.config,
        )

    def test_moderator_public_view_is_not_tracked(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )

        response = self.api.post_article_view(slug="public-article")

        assert response.status_code == codes.NO_CONTENT, response.content
        self.articles_use_case.get_article.assert_not_called()
        self.analytics_use_case.track_public_view.assert_not_called()

    def test_track_engaged_view(self) -> None:
        response = self.no_auth_api.post_article_engaged_view(slug="public-article")

        assert response.status_code == codes.NO_CONTENT, response.content
        self.analytics_use_case.track_engaged_view.assert_called_once_with(
            slug="public-article",
            source_category=ArticleViewSourceCategory.UNKNOWN,
        )

    def test_moderator_engaged_view_is_not_tracked(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )

        response = self.api.post_article_engaged_view(slug="public-article")

        assert response.status_code == codes.NO_CONTENT, response.content
        self.analytics_use_case.track_engaged_view.assert_not_called()

    def test_set_reaction(self) -> None:
        response = self.no_auth_api.post_article_reaction(
            slug="public-article",
            data={"reactionKind": "heart", "clientToken": "client-token"},
        )

        assert response.status_code == codes.NO_CONTENT, response.content
        self.analytics_use_case.set_reaction.assert_called_once_with(
            slug="public-article",
            client_token="client-token",  # noqa: S106
            reaction_kind=ArticleReactionKind.HEART,
            config=self.config,
        )

    def test_clear_reaction(self) -> None:
        response = self.no_auth_api.post_article_reaction(
            slug="public-article",
            data={"reactionKind": None, "clientToken": "client-token"},
        )

        assert response.status_code == codes.NO_CONTENT, response.content
        self.analytics_use_case.set_reaction.assert_called_once_with(
            slug="public-article",
            client_token="client-token",  # noqa: S106
            reaction_kind=None,
            config=self.config,
        )

    def test_get_public_stats(self) -> None:
        article_id = "00000000000040008000000000000041"
        self.analytics_use_case.get_public_stats.return_value = ArticlePublicStatsCollection(
            values=[
                ArticlePublicStats(
                    article_id=article_id,
                    view_count=7,
                    reaction_counts=ArticleReactionCounts(
                        heart=1,
                        fire=2,
                        thinking=3,
                        neutral=4,
                        poop=5,
                    ),
                ),
            ],
        )

        response = self.no_auth_api.get_article_public_stats(article_ids=[article_id])

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "stats": [
                {
                    "articleId": article_id,
                    "viewCount": 7,
                    "reactionCounts": {
                        "heart": 1,
                        "fire": 2,
                        "thinking": 3,
                        "neutral": 4,
                        "poop": 5,
                    },
                },
            ],
        }
        self.analytics_use_case.get_public_stats.assert_called_once_with(article_ids=[article_id])

    def test_get_public_stats_requires_article_ids(self) -> None:
        response = self.no_auth_api.get_article_public_stats(article_ids=None)

        assert response.status_code == codes.BAD_REQUEST
        self.analytics_use_case.get_public_stats.assert_not_called()

    def test_get_stats_requires_content_access(self) -> None:
        response = self.no_auth_api.get_article_stats(date_from="2026-01-01", date_to="2026-01-31")

        assert response.status_code == codes.UNAUTHORIZED
        self.analytics_use_case.get_stats.assert_not_called()

    def test_get_stats_allows_moderator(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.analytics_use_case.get_stats.return_value = ArticleAnalyticsStats(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            totals=ArticleAnalyticsTotals(
                view_count=0,
                engaged_view_count=0,
                reaction_count=0,
            ),
            articles=[],
            daily=[],
        )

        response = self.api.get_article_stats(date_from="2026-01-01", date_to="2026-01-31")

        assert response.status_code == codes.OK, response.content
        self.analytics_use_case.get_stats.assert_called_once_with(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            language=LanguageEnum.RU,
        )

    def test_get_stats(self) -> None:
        article_id = "00000000000040008000000000000041"
        self.analytics_use_case.get_stats.return_value = ArticleAnalyticsStats(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            totals=ArticleAnalyticsTotals(
                view_count=7,
                engaged_view_count=3,
                reaction_count=2,
            ),
            articles=[
                ArticleAnalyticsArticleStats(
                    article_id=article_id,
                    title="Typed articles",
                    slug="typed-articles",
                    view_count=7,
                    engaged_view_count=3,
                    reaction_counts=ArticleReactionCounts(
                        heart=1,
                        fire=0,
                        thinking=1,
                        neutral=0,
                        poop=0,
                    ),
                ),
            ],
            daily=[
                ArticleAnalyticsDailyStats(
                    article_id=article_id,
                    title="Typed articles",
                    slug="typed-articles",
                    date=date(2026, 1, 2),
                    source_category=ArticleViewSourceCategory.SEARCH,
                    view_count=7,
                    engaged_view_count=3,
                ),
            ],
        )

        response = self.api.get_article_stats(date_from="2026-01-01", date_to="2026-01-31")

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "dateFrom": "2026-01-01",
            "dateTo": "2026-01-31",
            "totals": {
                "viewCount": 7,
                "engagedViewCount": 3,
                "reactionCount": 2,
            },
            "articles": [
                {
                    "articleId": article_id,
                    "title": "Typed articles",
                    "slug": "typed-articles",
                    "viewCount": 7,
                    "engagedViewCount": 3,
                    "reactionCounts": {
                        "heart": 1,
                        "fire": 0,
                        "thinking": 1,
                        "neutral": 0,
                        "poop": 0,
                    },
                },
            ],
            "daily": [
                {
                    "articleId": article_id,
                    "title": "Typed articles",
                    "slug": "typed-articles",
                    "date": "2026-01-02",
                    "sourceCategory": "Search",
                    "viewCount": 7,
                    "engagedViewCount": 3,
                },
            ],
        }
        self.analytics_use_case.get_stats.assert_called_once_with(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            language=LanguageEnum.RU,
        )
