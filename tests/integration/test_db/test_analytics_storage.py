# ruff: noqa: S106
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest_asyncio
from sqlalchemy import func, select

from core.analytics.enums import AnalyticsEvent, AnalyticsKind
from core.analytics.schemas import AnalyticsConfig, AnalyticsFilters, AnalyticsVisit
from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.competency_matrix.schemas import QueuedCompetencyMatrixQuestionCreateParams
from core.i18n.enums import LanguageEnum
from core.schemas import Secret
from infra.postgresql.models.analytics import AnalyticsReceiptModel
from infra.postgresql.storages.analytics import AnalyticsDatabaseStorage
from infra.postgresql.storages.articles import ArticleAnalyticsDatabaseStorage
from infra.postgresql.storages.competency_matrix import CompetencyMatrixDatabaseStorage
from tests.test_cases import StorageTestCase

DAY = date(2026, 1, 10)


class TestAnalyticsDatabaseStorage(StorageTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.storage = AnalyticsDatabaseStorage(session=self.db_session)
        self.config = AnalyticsConfig(
            secret=Secret("test-analytics-secret"), receipt_retention_days=1
        )
        self.visit = AnalyticsVisit(
            kind=AnalyticsKind.SITE,
            target_id="articles",
            event=AnalyticsEvent.VIEW,
            source=ArticleViewSourceCategory.SEARCH,
            visitor_token="visitor-a",
            visit_token="visit-a",
        )

    async def test_deduplicates_views_engagement_and_daily_audience(self) -> None:
        await self.storage.record_visit(visit=self.visit, day=DAY, config=self.config)
        await self.storage.record_visit(visit=self.visit, day=DAY, config=self.config)
        engaged = replace(
            self.visit, event=AnalyticsEvent.ENGAGED, source=ArticleViewSourceCategory.UNKNOWN
        )
        await self.storage.record_visit(visit=engaged, day=DAY, config=self.config)
        await self.storage.record_visit(visit=engaged, day=DAY, config=self.config)
        await self.storage.record_visit(
            visit=replace(self.visit, target_id="matrix", visit_token="visit-b"),
            day=DAY,
            config=self.config,
        )
        rows = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.SITE, date_from=DAY, date_to=DAY, language=LanguageEnum.EN
            )
        )
        assert sum(row.views for row in rows) == 2
        assert sum(row.engaged for row in rows) == 1
        assert sum(row.visitors for row in rows) == 1
        assert all(row.source == ArticleViewSourceCategory.SEARCH for row in rows)

    async def test_engagement_requires_a_view_and_cannot_repeat_next_day(self) -> None:
        engaged = replace(self.visit, event=AnalyticsEvent.ENGAGED)
        await self.storage.record_visit(visit=engaged, day=DAY, config=self.config)
        await self.storage.record_visit(visit=self.visit, day=DAY, config=self.config)
        await self.storage.record_visit(
            visit=engaged, day=DAY + timedelta(days=1), config=self.config
        )
        rows = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.SITE,
                date_from=DAY,
                date_to=DAY + timedelta(days=1),
                language=LanguageEnum.EN,
            )
        )
        assert sum(row.engaged for row in rows) == 0

    async def test_rotates_daily_hashes_and_removes_old_receipts_without_losing_counts(
        self,
    ) -> None:
        await self.storage.record_visit(visit=self.visit, day=DAY, config=self.config)
        digests = set(await self.db_session.scalars(select(AnalyticsReceiptModel.digest)))
        await self.storage.record_visit(
            visit=self.visit, day=DAY + timedelta(days=2), config=self.config
        )
        new_digests = set(await self.db_session.scalars(select(AnalyticsReceiptModel.digest)))
        assert not digests.intersection(new_digests)
        assert (
            await self.db_session.scalar(
                select(func.count())
                .select_from(AnalyticsReceiptModel)
                .where(AnalyticsReceiptModel.date == DAY)
            )
            == 0
        )
        rows = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.SITE,
                date_from=DAY,
                date_to=DAY + timedelta(days=2),
                language=LanguageEnum.EN,
            )
        )
        assert sum(row.views for row in rows) == 2
        assert sum(row.visitors for row in rows) == 2

    async def test_article_report_preserves_history_and_counts_only_actual_reaction_changes(
        self,
    ) -> None:
        article = self.factory.core.article(slug="statistics-article")
        await self.storage_helper.create_article(article=article)
        article_storage = ArticleAnalyticsDatabaseStorage(session=self.db_session)
        await article_storage.increment_view(
            article_id=article.id, source_category=ArticleViewSourceCategory.SEARCH, viewed_on=DAY
        )
        for reaction in [
            ArticleReactionKind.HEART,
            ArticleReactionKind.HEART,
            ArticleReactionKind.FIRE,
            None,
            None,
        ]:
            await article_storage.set_reaction(
                article_id=article.id, article_scoped_voter_hash="voter", reaction_kind=reaction
            )
        historic = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.ARTICLES,
                date_from=DAY,
                date_to=DAY,
                language=LanguageEnum.EN,
                target_id=article.id,
            )
        )
        assert sum(row.views for row in historic) == 1
        assert sum(row.reactions for row in historic) == 0
        today = datetime.now(UTC).date()
        current = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.ARTICLES,
                date_from=today,
                date_to=today,
                language=LanguageEnum.EN,
                target_id=article.id,
            )
        )
        assert sum(row.reactions for row in current) == 3
        filtered = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.ARTICLES,
                date_from=DAY,
                date_to=DAY,
                language=LanguageEnum.EN,
                source=ArticleViewSourceCategory.DIRECT,
            )
        )
        assert filtered == []

    async def test_matrix_report_localizes_and_filters_structure(self) -> None:
        item = self.factory.core.competency_matrix_item(item_id=self.factory.core.hex_id(1))
        await self.storage_helper.create_competency_matrix_item(item=item)
        await self.storage.record_visit(
            visit=replace(self.visit, kind=AnalyticsKind.MATRIX, target_id=item.id),
            day=DAY,
            config=self.config,
        )
        filters = AnalyticsFilters(
            kind=AnalyticsKind.MATRIX,
            date_from=DAY,
            date_to=DAY,
            language=LanguageEnum.EN,
            group_id=item.structure.sheet_id,
            section_id=item.structure.section_id,
        )
        rows = await self.storage.get_daily(filters=filters)
        assert len(rows) == 1
        assert rows[0].title == item.question_en
        assert rows[0].section_title == item.structure.section_en
        assert (
            await self.storage.get_daily(filters=replace(filters, section_id="other-section")) == []
        )
        assert await self.storage.get_daily(filters=replace(filters, search="not found")) == []

    async def test_suggestion_statistics_survive_queue_deletion_without_author_data(self) -> None:
        queue = CompetencyMatrixDatabaseStorage(session=self.db_session)
        suggestion = await queue.create_queued_question(
            params=QueuedCompetencyMatrixQuestionCreateParams(
                question="A new question", sheet="python", grade=None
            ),
            suggested_by_username="private-author",
        )
        await queue.delete_queued_question(question_id=suggestion.id)
        today = datetime.now(UTC).date()
        rows = await self.storage.get_daily(
            filters=AnalyticsFilters(
                kind=AnalyticsKind.SUGGESTIONS,
                date_from=today,
                date_to=today,
                language=LanguageEnum.EN,
            )
        )
        assert sum(row.suggestions for row in rows) == 1
        assert rows[0].target_id == "python"
        assert "private-author" not in repr(rows)
