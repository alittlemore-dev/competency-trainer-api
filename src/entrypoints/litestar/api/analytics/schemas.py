import re
from dataclasses import asdict
from datetime import date
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from core.analytics.enums import AnalyticsEvent, AnalyticsKind, PublicPage
from core.analytics.schemas import AnalyticsDaily, AnalyticsVisit
from core.articles.enums import ArticleViewSourceCategory
from entrypoints.litestar.api.articles.schemas import ArticleReactionCountsResponseSchema
from entrypoints.litestar.api.schemas import CamelCaseSchema


class AnalyticsVisitRequest(CamelCaseSchema):
    kind: Literal[AnalyticsKind.SITE, AnalyticsKind.MATRIX]
    target_id: str = Field(min_length=1, max_length=511)
    event: AnalyticsEvent
    source: ArticleViewSourceCategory
    visitor_token: UUID
    visit_token: UUID

    @model_validator(mode="after")
    def validate_target(self) -> Self:  # noqa: N804
        if self.kind == AnalyticsKind.SITE:
            PublicPage.from_value(self.target_id)
        elif not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*", self.target_id):
            msg = "A matrix target must contain its sheet key and question slug"
            raise ValueError(msg)
        return self

    def to_domain_schema(self) -> AnalyticsVisit:
        return AnalyticsVisit(
            kind=self.kind,
            target_id=self.target_id,
            event=self.event,
            source=self.source,
            visitor_token=str(self.visitor_token),
            visit_token=str(self.visit_token),
        )


class AnalyticsDailyResponse(CamelCaseSchema):
    date: date
    target_id: str
    title: str
    group_id: str
    group_title: str
    section_id: str
    section_title: str
    source: ArticleViewSourceCategory
    views: int
    engaged: int
    reactions: int
    suggestions: int
    visitors: int

    @classmethod
    def from_domain_schema(cls, *, schema: AnalyticsDaily) -> Self:
        return cls(**asdict(schema))


class AnalyticsReportResponse(CamelCaseSchema):
    date_from: date
    date_to: date
    kind: AnalyticsKind
    daily: list[AnalyticsDailyResponse]
    current_reactions: dict[str, ArticleReactionCountsResponseSchema]
