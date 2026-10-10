from datetime import date
from unittest.mock import Mock

import pytest

from core.analytics.enums import AnalyticsEvent, AnalyticsKind
from core.analytics.schemas import AnalyticsConfig, AnalyticsDaily, AnalyticsFilters, AnalyticsVisit
from core.analytics.storages import AnalyticsStorage
from core.analytics.use_cases import AnalyticsUseCase
from core.articles.enums import ArticleViewSourceCategory
from core.articles.schemas import ArticleReactionCounts
from core.articles.storages import ArticleAnalyticsStorage
from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from core.schemas import Secret
from tests.helpers.factories.core import CoreFactoryHelper


async def test_matrix_tracking_resolves_public_target_and_rejects_drafts() -> None:
    matrix = Mock(spec=CompetencyMatrixStorage)
    storage = Mock(spec=AnalyticsStorage)
    article_storage = Mock(spec=ArticleAnalyticsStorage)
    item = CoreFactoryHelper.competency_matrix_item(item_id=CoreFactoryHelper.hex_id(1))
    matrix.get_competency_matrix_item_by_slug.return_value = item
    use_case = AnalyticsUseCase(
        storage=storage, matrix_storage=matrix, article_storage=article_storage
    )
    visit = AnalyticsVisit(
        kind=AnalyticsKind.MATRIX,
        target_id="python/context-managers",
        event=AnalyticsEvent.VIEW,
        source=ArticleViewSourceCategory.SEARCH,
        visitor_token=CoreFactoryHelper.hex_id(2),
        visit_token=CoreFactoryHelper.hex_id(3),
    )
    config = AnalyticsConfig(secret=Secret("test-analytics-key"), receipt_retention_days=1)
    day = date(2026, 1, 1)
    await use_case.record_visit(visit=visit, day=day, config=config)
    matrix.get_competency_matrix_item_by_slug.assert_called_once_with(
        sheet_key="python", slug="context-managers"
    )
    assert storage.record_visit.call_args.kwargs["visit"].target_id == item.id
    storage.record_visit.reset_mock()
    item.publish_status = PublishStatusEnum.DRAFT
    with pytest.raises(CompetencyMatrixItemNotFoundError):
        await use_case.record_visit(visit=visit, day=day, config=config)
    storage.record_visit.assert_not_called()


async def test_article_period_activity_is_separate_from_current_reaction_distribution() -> None:
    storage = Mock(spec=AnalyticsStorage)
    article_storage = Mock(spec=ArticleAnalyticsStorage)
    matrix = Mock(spec=CompetencyMatrixStorage)
    row = AnalyticsDaily(
        date=date(2026, 1, 1),
        target_id="article",
        title="Article",
        group_id="",
        group_title="",
        section_id="",
        section_title="",
        source=ArticleViewSourceCategory.DIRECT,
        views=7,
        engaged=2,
        reactions=1,
        suggestions=0,
        visitors=0,
    )
    storage.get_daily.return_value = [row]
    counts = ArticleReactionCounts(heart=4, fire=2, thinking=0, neutral=0, poop=0)
    article_storage.get_reaction_counts.return_value = {"article": counts}
    use_case = AnalyticsUseCase(
        storage=storage, matrix_storage=matrix, article_storage=article_storage
    )
    report = await use_case.get_report(
        filters=AnalyticsFilters(
            kind=AnalyticsKind.ARTICLES,
            date_from=row.date,
            date_to=row.date,
            language=LanguageEnum.EN,
        )
    )
    assert report.daily == [row]
    assert report.current_reactions["article"].total == 6
    article_storage.get_reaction_counts.assert_called_once_with(article_ids=["article"])
