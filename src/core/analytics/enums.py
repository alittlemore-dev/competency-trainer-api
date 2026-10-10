from core.enums import StrEnum


class AnalyticsKind(StrEnum):
    ARTICLES = "Articles"
    MATRIX = "Matrix"
    SITE = "Site"
    SUGGESTIONS = "Suggestions"


class PublicPage(StrEnum):
    ARTICLES = "articles"
    MATRIX = "matrix"
    ABOUT = "about"
    UPDATES = "updates"
    CONTACTS = "contacts"
    SITEMAP = "sitemap"


class AnalyticsEvent(StrEnum):
    VIEW = "View"
    ENGAGED = "Engaged"
