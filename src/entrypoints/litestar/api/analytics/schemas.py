import datetime
import re
from dataclasses import asdict
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from core.analytics.enums import AnalyticsEvent, AnalyticsKind, PublicPage
from core.analytics.schemas import AnalyticsDaily, AnalyticsVisit
from core.articles.enums import ArticleViewSourceCategory
from entrypoints.litestar.api.articles.schemas import ArticleReactionCountsResponseSchema
from entrypoints.litestar.api.schemas import CamelCaseSchema


class AnalyticsVisitRequest(CamelCaseSchema):
    kind: Literal[AnalyticsKind.SITE, AnalyticsKind.MATRIX] = Field(
        description="Analytics domain; public recording accepts Site or Matrix only.",
        examples=["Site"],
    )
    target_id: str = Field(
        min_length=1,
        max_length=511,
        description="Site page category, or matrix target as sheet-key/question-slug.",
        examples=["articles"],
    )
    event: AnalyticsEvent = Field(
        description="View starts a visit; Engaged records meaningful reading activity.",
        examples=["View"],
    )
    source: ArticleViewSourceCategory = Field(
        description="Coarse referrer category; raw URLs are not collected.", examples=["Direct"]
    )
    visitor_token: UUID = Field(
        description="Random daily visitor UUID; reuse only within the same day.",
        examples=["39ed503f-8c0f-47d0-bcf9-96b040798cd1"],
    )
    visit_token: UUID = Field(
        description="Random UUID shared by events within one visit.",
        examples=["492b06fd-ed8e-4d33-a6bb-e28a5adf461a"],
    )

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
    date: datetime.date = Field(description="UTC date of the aggregate.", examples=["2026-10-15"])
    target_id: str = Field(
        description="Site page category, or matrix target as sheet-key/question-slug.",
        examples=["articles"],
    )
    title: str = Field(
        description="Localized display title of the target.",
        examples=["Understanding asyncio.gather"],
    )
    group_id: str = Field(
        description="Stable folder or sheet identifier; empty when not applicable.",
        examples=["python"],
    )
    group_title: str = Field(
        description="Display name of the folder or sheet; empty when not applicable.",
        examples=["Python"],
    )
    section_id: str = Field(
        description="Stable matrix section identifier; empty when not applicable.",
        examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
    )
    section_title: str = Field(
        description="Display name of the matrix section; empty when not applicable.",
        examples=["Concurrency"],
    )
    source: ArticleViewSourceCategory = Field(
        description="Coarse referrer category; raw URLs are not collected.", examples=["Direct"]
    )
    views: int = Field(description="Recorded view count.", examples=[120])
    engaged: int = Field(description="Recorded engaged-view count.", examples=[78])
    reactions: int = Field(description="Recorded reaction event count.", examples=[32])
    suggestions: int = Field(description="Recorded question suggestion count.", examples=[4])
    visitors: int = Field(description="Distinct daily visitor count.", examples=[94])

    @classmethod
    def from_domain_schema(cls, *, schema: AnalyticsDaily) -> Self:
        return cls(**asdict(schema))


class AnalyticsReportResponse(CamelCaseSchema):
    date_from: datetime.date = Field(
        description="Inclusive first UTC date in the report.", examples=["2026-10-01"]
    )
    date_to: datetime.date = Field(
        description="Inclusive last UTC date in the report.", examples=["2026-10-15"]
    )
    kind: AnalyticsKind = Field(
        description="Domain whose daily aggregates were requested.",
        examples=["Site"],
    )
    daily: list[AnalyticsDailyResponse]
    current_reactions: dict[str, ArticleReactionCountsResponseSchema]
