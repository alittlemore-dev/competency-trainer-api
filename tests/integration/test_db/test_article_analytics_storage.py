from datetime import date

import pytest_asyncio

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.i18n.enums import LanguageEnum
from infra.postgresql.storages.articles import ArticleAnalyticsDatabaseStorage
from tests.test_cases import StorageTestCase


class TestArticleAnalyticsDatabaseStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.storage = ArticleAnalyticsDatabaseStorage(session=self.db_session)

    async def test_public_stats_include_views_and_reactions(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1), slug="analytics-article"
        )
        await self.storage_helper.create_article(article=article)

        await self.storage.increment_view(
            article_id=article.id,
            source_category=ArticleViewSourceCategory.SEARCH,
            viewed_on=None,
        )
        await self.storage.increment_view(
            article_id=article.id,
            source_category=ArticleViewSourceCategory.SEARCH,
            viewed_on=None,
        )
        await self.storage.increment_engaged_view(
            article_id=article.id,
            source_category=ArticleViewSourceCategory.SEARCH,
            viewed_on=None,
        )
        await self.storage.set_reaction(
            article_id=article.id,
            article_scoped_voter_hash="voter-hash",
            reaction_kind=ArticleReactionKind.FIRE,
        )

        result = await self.storage.get_public_stats(article_ids=[article.id])

        assert result.by_article_id(article.id).view_count == 2
        assert result.by_article_id(article.id).reaction_counts.fire == 1

    async def test_same_voter_reaction_is_replaced_and_removed(self) -> None:
        article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1), slug="reaction-article"
        )
        await self.storage_helper.create_article(article=article)

        await self.storage.set_reaction(
            article_id=article.id,
            article_scoped_voter_hash="voter-hash",
            reaction_kind=ArticleReactionKind.HEART,
        )
        await self.storage.set_reaction(
            article_id=article.id,
            article_scoped_voter_hash="voter-hash",
            reaction_kind=ArticleReactionKind.POOP,
        )
        replaced = await self.storage.get_public_stats(article_ids=[article.id])
        await self.storage.set_reaction(
            article_id=article.id,
            article_scoped_voter_hash="voter-hash",
            reaction_kind=None,
        )
        removed = await self.storage.get_public_stats(article_ids=[article.id])

        assert replaced.by_article_id(article.id).reaction_counts.heart == 0
        assert replaced.by_article_id(article.id).reaction_counts.poop == 1
        assert removed.by_article_id(article.id).reaction_counts.poop == 0

    async def test_stats_are_filtered_by_date_range(self) -> None:
        first_article = self.factory.core.article(
            article_id=self.factory.core.hex_id(1), slug="first"
        )
        second_article = self.factory.core.article(
            article_id=self.factory.core.hex_id(2), slug="second"
        )
        await self.storage_helper.create_articles(articles=[first_article, second_article])
        await self.storage.increment_view(
            article_id=first_article.id,
            source_category=ArticleViewSourceCategory.EXTERNAL,
            viewed_on=date(2026, 1, 2),
        )
        await self.storage.increment_engaged_view(
            article_id=first_article.id,
            source_category=ArticleViewSourceCategory.EXTERNAL,
            viewed_on=date(2026, 1, 2),
        )
        await self.storage.increment_view(
            article_id=second_article.id,
            source_category=ArticleViewSourceCategory.DIRECT,
            viewed_on=date(2026, 2, 2),
        )
        await self.storage.set_reaction(
            article_id=first_article.id,
            article_scoped_voter_hash="voter-hash",
            reaction_kind=ArticleReactionKind.THINKING,
        )

        daily = await self.storage.get_daily_stats(
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 31),
            language=LanguageEnum.RU,
        )
        reaction_counts = await self.storage.get_reaction_counts(article_ids=[first_article.id])

        assert [item.slug for item in daily] == ["first"]
        assert daily[0].view_count == 1
        assert daily[0].engaged_view_count == 1
        assert daily[0].source_category == ArticleViewSourceCategory.EXTERNAL
        assert reaction_counts[first_article.id].thinking == 1
