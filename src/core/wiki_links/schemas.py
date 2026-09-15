from dataclasses import dataclass

from core.enums import PublishStatusEnum
from core.schemas import ValuedDataclass
from core.wiki_links.enums import WikiLinkTargetTypeEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class WikiLinkTarget:
    slug: str
    title: str
    publish_status: PublishStatusEnum


@dataclass(frozen=True, slots=True, kw_only=True)
class WikiLinkTargetGroup:
    type: WikiLinkTargetTypeEnum
    items: list[WikiLinkTarget]


@dataclass(frozen=True, slots=True, kw_only=True)
class WikiLinkTargets(ValuedDataclass[WikiLinkTargetGroup]): ...
