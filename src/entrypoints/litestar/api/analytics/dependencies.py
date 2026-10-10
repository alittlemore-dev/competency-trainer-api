from datetime import UTC, datetime
from typing import Annotated

from litestar.exceptions import ValidationException
from litestar.params import QueryParameter

from core.analytics.enums import AnalyticsKind
from core.analytics.schemas import AnalyticsFilters
from core.articles.enums import ArticleViewSourceCategory
from entrypoints.litestar.api.parameters import (
    DateFromQuery,
    DateToQuery,
    LanguageQuery,
    build_examples,
)
from infra.config.constants import constants


def provide_analytics_filters(  # noqa: PLR0913
    kind: Annotated[
        AnalyticsKind,
        QueryParameter(description="Analytics report domain", examples=build_examples("Site")),
    ],
    date_from: DateFromQuery,
    date_to: DateToQuery,
    language: LanguageQuery,
    source: Annotated[
        ArticleViewSourceCategory | None,
        QueryParameter(
            description="Coarse view source category", examples=build_examples("Search")
        ),
    ] = None,
    target_id: Annotated[
        str | None,
        QueryParameter(
            name="targetId",
            max_length=255,
            description="One content identifier or page category",
            examples=build_examples("articles"),
        ),
    ] = None,
    group_id: Annotated[
        str | None,
        QueryParameter(
            name="groupId",
            max_length=255,
            description="Article folder or matrix sheet identifier",
            examples=build_examples("00000000000040008000000000000001"),
        ),
    ] = None,
    section_id: Annotated[
        str | None,
        QueryParameter(
            name="sectionId",
            max_length=255,
            description="Matrix section identifier",
            examples=build_examples("00000000000040008000000000000001"),
        ),
    ] = None,
    search: Annotated[
        str | None,
        QueryParameter(
            max_length=255,
            description="Literal title substring",
            examples=build_examples("asyncio"),
        ),
    ] = None,
) -> AnalyticsFilters:
    if date_to < date_from or (date_to - date_from).days > constants.analytics.maximum_range_days:
        raise ValidationException(detail="Choose an ordered date range of at most three years")
    if date_to > datetime.now(UTC).date():
        raise ValidationException(detail="The statistics range cannot end in the future")
    return AnalyticsFilters(
        kind=kind,
        date_from=date_from,
        date_to=date_to,
        language=language,
        source=source,
        target_id=target_id,
        group_id=group_id,
        section_id=section_id,
        search=search.strip() if search else None,
    )
