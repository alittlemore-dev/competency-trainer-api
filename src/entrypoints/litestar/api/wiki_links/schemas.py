from typing import Annotated, Self

from pydantic import Field

from core.enums import PublishStatusEnum
from core.wiki_links.enums import WikiLinkTargetTypeEnum
from core.wiki_links.schemas import WikiLinkTarget, WikiLinkTargetGroup, WikiLinkTargets
from entrypoints.litestar.api.schemas import CamelCaseSchema


class WikiLinkTargetResponseSchema(CamelCaseSchema):
    slug: Annotated[str, Field(title="Target slug")]
    title: Annotated[str, Field(title="Localized target title")]
    publish_status: Annotated[PublishStatusEnum, Field(title="Publication status")]

    @classmethod
    def from_domain_schema(cls, *, schema: WikiLinkTarget) -> Self:
        return cls(
            slug=schema.slug,
            title=schema.title,
            publish_status=schema.publish_status,
        )


class WikiLinkTargetGroupResponseSchema(CamelCaseSchema):
    type: Annotated[WikiLinkTargetTypeEnum, Field(title="Target type")]
    items: Annotated[list[WikiLinkTargetResponseSchema], Field(title="Targets")]

    @classmethod
    def from_domain_schema(cls, *, schema: WikiLinkTargetGroup) -> Self:
        return cls(
            type=schema.type,
            items=[
                WikiLinkTargetResponseSchema.from_domain_schema(schema=item)
                for item in schema.items
            ],
        )


class WikiLinkTargetsResponseSchema(CamelCaseSchema):
    targets: Annotated[list[WikiLinkTargetGroupResponseSchema], Field(title="Targets")]

    @classmethod
    def from_domain_schema(cls, *, schema: WikiLinkTargets) -> Self:
        return cls(
            targets=[
                WikiLinkTargetGroupResponseSchema.from_domain_schema(schema=target)
                for target in schema
            ],
        )
