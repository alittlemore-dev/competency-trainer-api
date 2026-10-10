from datetime import date

from sqlalchemy import Boolean, Date, Enum, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from core.analytics.enums import AnalyticsKind
from core.articles.enums import ArticleViewSourceCategory
from infra.postgresql.models.base import BaseModel, TableArgs
from infra.postgresql.models.mixins.ids import HexUuidIDMixin


class AnalyticsDailyModel(HexUuidIDMixin, BaseModel):
    date: Mapped[date] = mapped_column(Date())
    kind: Mapped[AnalyticsKind] = mapped_column(Enum(AnalyticsKind, name="analytics_kind_enum"))
    target_id: Mapped[str] = mapped_column(String(255))
    source: Mapped[ArticleViewSourceCategory] = mapped_column(
        Enum(ArticleViewSourceCategory, name="article_view_source_category_enum")
    )
    views: Mapped[int] = mapped_column(Integer())
    engaged: Mapped[int] = mapped_column(Integer())
    reactions: Mapped[int] = mapped_column(Integer())
    suggestions: Mapped[int] = mapped_column(Integer())
    visitors: Mapped[int] = mapped_column(Integer())

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.date, cls.kind, cls.target_id, cls.source, name="analytics_daily_uniq"
            ),
            Index("analytics_daily_kind_date_idx", cls.kind, cls.date),
        )


class AnalyticsReceiptModel(HexUuidIDMixin, BaseModel):
    date: Mapped[date] = mapped_column(Date())
    scope: Mapped[str] = mapped_column(String(300))
    digest: Mapped[str] = mapped_column(String(64))
    source: Mapped[ArticleViewSourceCategory] = mapped_column(
        Enum(ArticleViewSourceCategory, name="article_view_source_category_enum")
    )
    engaged: Mapped[bool] = mapped_column(Boolean())

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (UniqueConstraint(cls.date, cls.scope, cls.digest, name="analytics_receipt_uniq"),)
