from dataclasses import dataclass, replace
from datetime import date

from core.analytics.enums import AnalyticsKind, PublicPage
from core.analytics.schemas import (
    AnalyticsConfig,
    AnalyticsFilters,
    AnalyticsReport,
    AnalyticsVisit,
)
from core.analytics.storages import AnalyticsStorage
from core.articles.storages import ArticleAnalyticsStorage
from core.competency_matrix.exceptions import CompetencyMatrixItemNotFoundError
from core.competency_matrix.storages import CompetencyMatrixStorage


@dataclass(slots=True, kw_only=True)
class AnalyticsUseCase:
    storage: AnalyticsStorage
    matrix_storage: CompetencyMatrixStorage
    article_storage: ArticleAnalyticsStorage

    async def record_visit(
        self, *, visit: AnalyticsVisit, day: date, config: AnalyticsConfig
    ) -> None:
        if visit.kind == AnalyticsKind.MATRIX:
            sheet_key, slug = visit.target_id.split("/", 1)
            item = await self.matrix_storage.get_competency_matrix_item_by_slug(
                sheet_key=sheet_key, slug=slug
            )
            if not item.is_available():
                raise CompetencyMatrixItemNotFoundError
            visit = replace(visit, target_id=item.id)
        elif visit.kind == AnalyticsKind.SITE:
            PublicPage.from_value(visit.target_id)
        await self.storage.record_visit(visit=visit, day=day, config=config)

    async def get_report(self, *, filters: AnalyticsFilters) -> AnalyticsReport:
        daily = await self.storage.get_daily(filters=filters)
        report = AnalyticsReport(daily=daily, current_reactions={})
        if filters.kind == AnalyticsKind.ARTICLES:
            return replace(
                report,
                current_reactions=await self.article_storage.get_reaction_counts(
                    article_ids=report.article_ids,
                ),
            )
        return report
