from datetime import date
from unittest.mock import Mock

import pytest

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.exceptions import ArticleNotFoundError
from core.articles.schemas import (
    ArticleAnalyticsConfig,
    ArticleAnalyticsDailyStats,
    ArticlePublicStatsCollection,
    ArticleReactionCounts,
)
from core.articles.storages import ArticleAnalyticsStorage, ArticlesStorage
from core.articles.use_cases import ArticleAnalyticsUseCase
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from core.schemas import Secret
from tests.test_cases import TestCase


class TestArticleAnalyticsUseCase(TestCase):
    def setup_method(self) -> None:
        self.articles_storage = Mock(spec=ArticlesStorage)
        self.analytics_storage = Mock(spec=ArticleAnalyticsStorage)
        self.error_reporter = Mock()
        self.use_case = ArticleAnalyticsUseCase(
            articles_storage=self.articles_storage,
            analytics_storage=self.analytics_storage,
            error_reporter=self.error_reporter,
        )
        self.config = ArticleAnalyticsConfig(
            reaction_secret=Secret("reaction-secret"),
            app_domain="example.com",
        )

    async def test_track_view_delegates_published_article(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1),
            publish_status=PublishStatusEnum.PUBLISHED,
        )

        await self.use_case.track_view(
            article=article,
            source_category=ArticleViewSourceCategory.SEARCH,
        )

        self.analytics_storage.increment_view.assert_called_once_with(
            article_id=article.id,
            source_category=ArticleViewSourceCategory.SEARCH,
            viewed_on=None,
        )

    async def test_track_view_ignores_draft_article(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1),
            publish_status=PublishStatusEnum.DRAFT,
        )

        await self.use_case.track_view(
            article=article,
            source_category=ArticleViewSourceCategory.SEARCH,
        )

        self.analytics_storage.increment_view.assert_not_called()

    async def test_track_public_view_classifies_referrer(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1),
            publish_status=PublishStatusEnum.PUBLISHED,
        )

        await self.use_case.track_public_view(
            article=article,
            referrer="https://www.google.com/search?q=typed",
            config=self.config,
        )

        self.analytics_storage.increment_view.assert_called_once_with(
            article_id=article.id,
            source_category=ArticleViewSourceCategory.SEARCH,
            viewed_on=None,
        )

    async def test_track_public_view_reports_error_without_raising(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1),
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        error = RuntimeError("db is down")
        self.analytics_storage.increment_view.side_effect = error

        await self.use_case.track_public_view(
            article=article,
            referrer=None,
            config=self.config,
        )

        self.error_reporter.report_public_view_tracking_failure.assert_called_once_with(
            article=article,
            error=error,
        )

    async def test_track_engaged_view_rejects_draft_article(self) -> None:
        self.articles_storage.get_article_by_slug.return_value = self.factory.core.article(
            publish_status=PublishStatusEnum.DRAFT,
        )

        with pytest.raises(ArticleNotFoundError):
            await self.use_case.track_engaged_view(
                slug="draft-article",
                source_category=ArticleViewSourceCategory.UNKNOWN,
            )

        self.analytics_storage.increment_engaged_view.assert_not_called()

    async def test_same_token_is_article_scoped_for_reactions(self) -> None:
        first_article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1),
            slug="first",
        )
        second_article = self.factory.core.article(
            article_id=self.factory.core.hex_id(2),
            slug="second",
        )
        self.articles_storage.get_article_by_slug.side_effect = [first_article, second_article]

        await self.use_case.set_reaction(
            slug="first",
            client_token="same-client-token",  # noqa: S106
            reaction_kind=ArticleReactionKind.HEART,
            config=self.config,
        )
        await self.use_case.set_reaction(
            slug="second",
            client_token="same-client-token",  # noqa: S106
            reaction_kind=ArticleReactionKind.HEART,
            config=self.config,
        )

        first_call, second_call = self.analytics_storage.set_reaction.call_args_list
        assert first_call.kwargs["article_id"] == first_article.id
        assert second_call.kwargs["article_id"] == second_article.id
        assert (
            first_call.kwargs["article_scoped_voter_hash"]
            != second_call.kwargs["article_scoped_voter_hash"]
        )

    async def test_public_stats_are_filled_with_zero_counts(self) -> None:
        article_id = self.factory.core.hex_id(1)
        self.analytics_storage.get_public_stats.return_value = ArticlePublicStatsCollection(
            values=[],
        )

        result = await self.use_case.get_public_stats(article_ids=[article_id])

        assert result.values[0].article_id == article_id
        assert result.values[0].view_count == 0
        assert result.values[0].reaction_counts == ArticleReactionCounts(
            heart=0,
            fire=0,
            thinking=0,
            neutral=0,
            poop=0,
        )

    async def test_get_stats_builds_totals_and_article_rows_from_storage_data(self) -> None:
        article_id = self.factory.core.hex_id(1)
        self.analytics_storage.get_daily_stats.return_value = [
            ArticleAnalyticsDailyStats(
                article_id=article_id,
                title="Typed articles",
                slug="typed-articles",
                date=date(2026, 1, 2),
                source_category=ArticleViewSourceCategory.SEARCH,
                view_count=4,
                engaged_view_count=1,
            ),
            ArticleAnalyticsDailyStats(
                article_id=article_id,
                title="Typed articles",
                slug="typed-articles",
                date=date(2026, 1, 3),
                source_category=ArticleViewSourceCategory.DIRECT,
                view_count=3,
                engaged_view_count=2,
            ),
        ]
        self.analytics_storage.get_reaction_counts.return_value = {
            article_id: ArticleReactionCounts(
                heart=1,
                fire=0,
                thinking=1,
                neutral=0,
                poop=0,
            ),
        }

        result = await self.use_case.get_stats(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            language=LanguageEnum.RU,
        )

        assert result.totals.view_count == 7
        assert result.totals.engaged_view_count == 3
        assert result.totals.reaction_count == 2
        assert len(result.articles) == 1
        assert result.articles[0].article_id == article_id
        assert result.articles[0].view_count == 7
        assert result.articles[0].engaged_view_count == 3
        assert result.articles[0].reaction_counts.thinking == 1
        assert result.daily == self.analytics_storage.get_daily_stats.return_value
        self.analytics_storage.get_daily_stats.assert_called_once_with(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            language=LanguageEnum.RU,
        )
        self.analytics_storage.get_reaction_counts.assert_called_once_with(article_ids=[article_id])
