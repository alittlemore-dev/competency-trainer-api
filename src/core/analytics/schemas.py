from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from hmac import new as hmac_new

from core.analytics.enums import AnalyticsEvent, AnalyticsKind
from core.articles.enums import ArticleViewSourceCategory
from core.articles.schemas import ArticleReactionCounts
from core.i18n.enums import LanguageEnum
from core.schemas import Secret


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsConfig:
    secret: Secret[str]
    receipt_retention_days: int

    def digest(self, *, day: date, scope: str, token: str) -> str:
        return hmac_new(
            self.secret.get_secret_value().encode(),
            f"{day.isoformat()}:{scope}:{token}".encode(),
            sha256,
        ).hexdigest()


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsVisit:
    kind: AnalyticsKind
    target_id: str
    event: AnalyticsEvent
    source: ArticleViewSourceCategory
    visitor_token: str
    visit_token: str


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsFilters:
    kind: AnalyticsKind
    date_from: date
    date_to: date
    language: LanguageEnum
    source: ArticleViewSourceCategory | None = None
    target_id: str | None = None
    group_id: str | None = None
    section_id: str | None = None
    search: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsDaily:
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


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalyticsReport:
    daily: list[AnalyticsDaily]
    current_reactions: dict[str, ArticleReactionCounts]

    @property
    def article_ids(self) -> list[str]:
        return list(dict.fromkeys(row.target_id for row in self.daily))
