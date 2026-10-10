from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import ColumnElement, String, cast, delete, func, literal, select, union_all, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.analytics.enums import AnalyticsEvent, AnalyticsKind
from core.analytics.schemas import AnalyticsConfig, AnalyticsDaily, AnalyticsFilters, AnalyticsVisit
from core.analytics.storages import AnalyticsStorage
from core.articles.enums import ArticleViewSourceCategory
from core.i18n.enums import LanguageEnum
from infra.postgresql.models.analytics import AnalyticsDailyModel, AnalyticsReceiptModel
from infra.postgresql.models.articles import (
    ArticleDailyAnalyticsModel,
    ArticleFolderModel,
    ArticleModel,
)
from infra.postgresql.models.competency_matrix import (
    CompetencyMatrixItemModel,
    CompetencyMatrixSectionModel,
    CompetencyMatrixSheetModel,
    CompetencyMatrixSubsectionModel,
)


@dataclass(slots=True, kw_only=True)
class AnalyticsDatabaseStorage(AnalyticsStorage):
    session: AsyncSession

    async def increment(  # noqa: PLR0913
        self,
        *,
        day: date,
        kind: AnalyticsKind,
        target_id: str,
        source: ArticleViewSourceCategory,
        views: int,
        engaged: int,
        reactions: int,
        suggestions: int,
        visitors: int,
    ) -> None:
        stmt = insert(AnalyticsDailyModel).values(
            date=day,
            kind=kind,
            target_id=target_id,
            source=source,
            views=views,
            engaged=engaged,
            reactions=reactions,
            suggestions=suggestions,
            visitors=visitors,
        )
        await self.session.execute(
            stmt.on_conflict_do_update(
                constraint="analytics_daily_uniq",
                set_={
                    name: getattr(AnalyticsDailyModel, name) + value
                    for name, value in {
                        "views": views,
                        "engaged": engaged,
                        "reactions": reactions,
                        "suggestions": suggestions,
                        "visitors": visitors,
                    }.items()
                },
            )
        )

    async def record_visit(
        self, *, visit: AnalyticsVisit, day: date, config: AnalyticsConfig
    ) -> None:
        scope = f"{visit.kind.value}:{visit.target_id}"
        digest = config.digest(day=day, scope=scope, token=visit.visit_token)
        await self.session.execute(
            delete(AnalyticsReceiptModel).where(
                AnalyticsReceiptModel.date < day - timedelta(days=config.receipt_retention_days)
            )
        )
        if visit.event == AnalyticsEvent.VIEW:
            receipt = await self.session.scalar(
                insert(AnalyticsReceiptModel)
                .values(
                    date=day,
                    scope=scope,
                    digest=digest,
                    source=visit.source,
                    engaged=False,
                )
                .on_conflict_do_nothing(constraint="analytics_receipt_uniq")
                .returning(AnalyticsReceiptModel.id)
            )
            if receipt is None:
                return
            await self.increment(
                day=day,
                kind=visit.kind,
                target_id=visit.target_id,
                source=visit.source,
                views=1,
                engaged=0,
                reactions=0,
                suggestions=0,
                visitors=0,
            )
            if visit.kind == AnalyticsKind.SITE:
                visitor_scope = "Site:audience"
                visitor = await self.session.scalar(
                    insert(AnalyticsReceiptModel)
                    .values(
                        date=day,
                        scope=visitor_scope,
                        digest=config.digest(
                            day=day, scope=visitor_scope, token=visit.visitor_token
                        ),
                        source=visit.source,
                        engaged=False,
                    )
                    .on_conflict_do_nothing(constraint="analytics_receipt_uniq")
                    .returning(AnalyticsReceiptModel.id)
                )
                if visitor is not None:
                    await self.increment(
                        day=day,
                        kind=AnalyticsKind.SITE,
                        target_id="_audience",
                        source=visit.source,
                        views=0,
                        engaged=0,
                        reactions=0,
                        suggestions=0,
                        visitors=1,
                    )
        else:
            source = await self.session.scalar(
                update(AnalyticsReceiptModel)
                .where(
                    AnalyticsReceiptModel.date == day,
                    AnalyticsReceiptModel.scope == scope,
                    AnalyticsReceiptModel.digest == digest,
                    AnalyticsReceiptModel.engaged.is_(False),
                )
                .values(engaged=True)
                .returning(AnalyticsReceiptModel.source)
            )
            if source is not None:
                await self.increment(
                    day=day,
                    kind=visit.kind,
                    target_id=visit.target_id,
                    source=source,
                    views=0,
                    engaged=1,
                    reactions=0,
                    suggestions=0,
                    visitors=0,
                )

    async def get_daily(self, *, filters: AnalyticsFilters) -> list[AnalyticsDaily]:
        data = AnalyticsDailyModel
        counters = select(
            data.date.label("date"),
            data.target_id.label("target_id"),
            data.source.label("source"),
            data.views.label("views"),
            data.engaged.label("engaged"),
            data.reactions.label("reactions"),
            data.suggestions.label("suggestions"),
            data.visitors.label("visitors"),
        ).where(
            data.kind == filters.kind, data.date >= filters.date_from, data.date <= filters.date_to
        )
        if filters.kind == AnalyticsKind.ARTICLES:
            old = ArticleDailyAnalyticsModel
            legacy_union = union_all(
                counters,
                select(
                    old.date,
                    old.article_id,
                    old.source_category,
                    old.view_count,
                    old.engaged_view_count,
                    literal(0),
                    literal(0),
                    literal(0),
                ).where(old.date >= filters.date_from, old.date <= filters.date_to),
            )
            rows = legacy_union.subquery()
        else:
            rows = counters.subquery()
        ru = filters.language == LanguageEnum.RU
        blank = literal("")
        title: ColumnElement[str] = rows.c.target_id
        group_id: ColumnElement[str] = blank
        group_title: ColumnElement[str] = blank
        section_id: ColumnElement[str] = blank
        section_title: ColumnElement[str] = blank
        stmt = select(rows)
        if filters.kind == AnalyticsKind.ARTICLES:
            article, folder = ArticleModel, ArticleFolderModel
            title = func.coalesce(article.title_ru if ru else article.title_en, rows.c.target_id)
            group_id = func.coalesce(folder.id, "")
            group_title = func.coalesce(folder.name_ru if ru else folder.name_en, "")
            stmt = stmt.outerjoin(article, article.id == rows.c.target_id).outerjoin(
                folder, folder.id == article.folder_id
            )
        elif filters.kind == AnalyticsKind.MATRIX:
            item, sub, section, sheet = (
                CompetencyMatrixItemModel,
                CompetencyMatrixSubsectionModel,
                CompetencyMatrixSectionModel,
                CompetencyMatrixSheetModel,
            )
            title = func.coalesce(item.question_ru if ru else item.question_en, rows.c.target_id)
            group_id = func.coalesce(sheet.id, "")
            group_title = func.coalesce(sheet.name_ru if ru else sheet.name_en, "")
            section_id = func.coalesce(section.id, "")
            section_title = func.coalesce(section.name_ru if ru else section.name_en, "")
            stmt = (
                stmt.outerjoin(item, item.id == rows.c.target_id)
                .outerjoin(sub, sub.id == item.subsection_id)
                .outerjoin(section, section.id == sub.section_id)
                .outerjoin(sheet, sheet.id == section.sheet_id)
            )
        elif filters.kind == AnalyticsKind.SUGGESTIONS:
            sheet = CompetencyMatrixSheetModel
            title = func.coalesce(sheet.name_ru if ru else sheet.name_en, rows.c.target_id)
            group_id = func.coalesce(sheet.id, "")
            group_title = title
            stmt = stmt.outerjoin(sheet, sheet.key == rows.c.target_id)
        if filters.source is not None:
            stmt = stmt.where(rows.c.source == filters.source)
        if filters.target_id is not None:
            stmt = stmt.where(rows.c.target_id == filters.target_id)
        if filters.group_id is not None:
            stmt = stmt.where(group_id == filters.group_id)
        if filters.section_id is not None:
            stmt = stmt.where(section_id == filters.section_id)
        if filters.search:
            stmt = stmt.where(func.strpos(func.lower(title), filters.search.lower()) > 0)
        stmt = (
            stmt.with_only_columns(
                rows.c.date,
                rows.c.target_id,
                title.label("title"),
                group_id.label("group_id"),
                group_title.label("group_title"),
                section_id.label("section_id"),
                section_title.label("section_title"),
                cast(rows.c.source, String()).label("source"),
                *(
                    func.sum(rows.c[name]).label(name)
                    for name in ("views", "engaged", "reactions", "suggestions", "visitors")
                ),
            )
            .group_by(
                rows.c.date,
                rows.c.target_id,
                title,
                group_id,
                group_title,
                section_id,
                section_title,
                rows.c.source,
            )
            .order_by(rows.c.date, rows.c.target_id, rows.c.source)
        )
        result = await self.session.execute(stmt)
        return [
            AnalyticsDaily(
                date=row.date,
                target_id=row.target_id,
                title=row.title,
                group_id=row.group_id,
                group_title=row.group_title,
                section_id=row.section_id,
                section_title=row.section_title,
                source=ArticleViewSourceCategory[row.source],
                views=row.views,
                engaged=row.engaged,
                reactions=row.reactions,
                suggestions=row.suggestions,
                visitors=row.visitors,
            )
            for row in result
        ]
