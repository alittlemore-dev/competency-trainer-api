import re
from datetime import date
from typing import Annotated, Self

from pydantic import Field

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.schemas import (
    Article,
    ArticleAnalyticsArticleStats,
    ArticleAnalyticsDailyStats,
    ArticleAnalyticsStats,
    ArticleAnalyticsTotals,
    ArticleCreateParams,
    ArticleFolder,
    ArticleFolderCreateParams,
    ArticleFolderPriorityUpdateParams,
    ArticleFolders,
    ArticleMetadata,
    ArticlePublicStats,
    ArticlePublicStatsCollection,
    ArticleReactionCounts,
    Articles,
    ArticleTree,
    ArticleTreeFolder,
    ArticleTreeItem,
    ArticleUpdateParams,
    Tag,
    TagCreateParams,
    Tags,
    TagUpdateParams,
)
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.schemas import CamelCaseSchema
from entrypoints.litestar.api.validation import (
    ArticleContentText,
    OptionalHttpUrlString,
    RequiredShortText,
    SlugString,
)
from infra.config.constants import constants

ARTICLE_EXCERPT_CHARACTER_LIMIT = 180


class TagResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    name: Annotated[
        str,
        Field(
            title="Name",
            examples=["Python"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    translations: Annotated[TagTranslationsResponseSchema, Field(title="Translations")]

    @classmethod
    def from_domain_schema(cls, *, schema: Tag, language: LanguageEnum) -> Self:
        return cls(
            id=schema.id,
            name=schema.localized_name(language=language),
            slug=schema.slug,
            translations=TagTranslationsResponseSchema.from_domain_schema(schema=schema),
        )


class TagTranslationSchema(CamelCaseSchema):
    name: Annotated[
        RequiredShortText,
        Field(
            title="Name",
            examples=["Python"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]


class TagTranslationsSchema(CamelCaseSchema):
    ru: Annotated[TagTranslationSchema, Field(title="Russian translation")]
    en: Annotated[TagTranslationSchema, Field(title="English translation")]


class TagTranslationsResponseSchema(CamelCaseSchema):
    ru: Annotated[TagTranslationSchema, Field(title="Russian translation")]
    en: Annotated[TagTranslationSchema, Field(title="English translation")]

    @classmethod
    def from_domain_schema(cls, *, schema: Tag) -> Self:
        return cls(
            ru=TagTranslationSchema(name=schema.name_ru),
            en=TagTranslationSchema(name=schema.name_en),
        )


class TagsResponseSchema(CamelCaseSchema):
    tags: Annotated[list[TagResponseSchema], Field(title="Tags")]

    @classmethod
    def from_domain_schema(cls, *, schema: Tags, language: LanguageEnum) -> Self:
        return cls(
            tags=[
                TagResponseSchema.from_domain_schema(schema=tag, language=language)
                for tag in schema
            ],
        )


class TagRequestSchema(CamelCaseSchema):
    slug: Annotated[
        SlugString,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    translations: Annotated[TagTranslationsSchema, Field(title="Translations")]

    def to_create_schema(self, *, tag_id: str) -> TagCreateParams:
        return TagCreateParams(
            id=tag_id,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
            slug=self.slug,
        )

    def to_update_schema(self) -> TagUpdateParams:
        return TagUpdateParams(
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
            slug=self.slug,
        )


class ArticleReactionCountsResponseSchema(CamelCaseSchema):
    heart: Annotated[int, Field(title="Reaction: liked", examples=[17])]
    fire: Annotated[int, Field(title="Reaction: want more", examples=[8])]
    thinking: Annotated[int, Field(title="Reaction: thought-provoking", examples=[5])]
    neutral: Annotated[int, Field(title="Reaction: neutral", examples=[2])]
    poop: Annotated[int, Field(title="Reaction: disliked", examples=[0])]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleReactionCounts) -> Self:
        return cls(
            heart=schema.heart,
            fire=schema.fire,
            thinking=schema.thinking,
            neutral=schema.neutral,
            poop=schema.poop,
        )


class ArticleMetadataRequestSchema(CamelCaseSchema):
    seo_title_ru: Annotated[
        str | None,
        Field(
            title="RU SEO title",
            max_length=constants.admin_validation.short_text_max_length,
            examples=["Как работает asyncio.gather"],
        ),
    ]
    seo_title_en: Annotated[
        str | None,
        Field(
            title="EN SEO title",
            max_length=constants.admin_validation.short_text_max_length,
            examples=["Understanding asyncio.gather"],
        ),
    ]
    seo_description_ru: Annotated[
        str | None,
        Field(
            title="RU SEO description",
            max_length=constants.admin_validation.seo_description_max_length,
            examples=[
                "Как asyncio.gather запускает конкурентные задачи и обрабатывает результаты."
            ],
        ),
    ]
    seo_description_en: Annotated[
        str | None,
        Field(
            title="EN SEO description",
            max_length=constants.admin_validation.seo_description_max_length,
            examples=["How asyncio.gather schedules concurrent tasks and handles their results."],
        ),
    ]
    cover_image_file_id: Annotated[
        str | None,
        Field(
            title="Cover image file ID",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description=(
                "Existing managed cover-image file identifier, or null when no cover is selected."
            ),
        ),
    ]
    cover_image_alt_ru: Annotated[
        str | None,
        Field(
            title="RU cover image alt",
            max_length=constants.admin_validation.short_text_max_length,
            examples=["Параллельные задачи в цикле событий"],
        ),
    ]
    cover_image_alt_en: Annotated[
        str | None,
        Field(
            title="EN cover image alt",
            max_length=constants.admin_validation.short_text_max_length,
            examples=["Concurrent tasks on an event loop"],
        ),
    ]

    def to_domain_schema(self) -> ArticleMetadata:
        return ArticleMetadata(
            seo_title_ru=self.seo_title_ru,
            seo_title_en=self.seo_title_en,
            seo_description_ru=self.seo_description_ru,
            seo_description_en=self.seo_description_en,
            cover_image_file_id=self.cover_image_file_id,
            cover_image_file=None,
            cover_image_url=None,
            cover_image_alt_ru=self.cover_image_alt_ru,
            cover_image_alt_en=self.cover_image_alt_en,
        )


class ArticleMetadataResponseSchema(ArticleMetadataRequestSchema):
    cover_image_url: Annotated[
        OptionalHttpUrlString,
        Field(
            title="Cover image URL",
            examples=[
                "https://media.alittlemore.dev/article-cover-images/2026/10/asyncio-cover.webp"
            ],
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleMetadata) -> Self:
        return cls(
            seo_title_ru=schema.seo_title_ru,
            seo_title_en=schema.seo_title_en,
            seo_description_ru=schema.seo_description_ru,
            seo_description_en=schema.seo_description_en,
            cover_image_file_id=schema.cover_image_file_id,
            cover_image_url=schema.cover_image_url,
            cover_image_alt_ru=schema.cover_image_alt_ru,
            cover_image_alt_en=schema.cover_image_alt_en,
        )


class ArticleSummaryResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    title: Annotated[str, Field(title="Title", examples=["Understanding asyncio.gather"])]
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    folder: Annotated[str, Field(title="Folder", examples=["Python"])]
    folder_id: Annotated[
        str,
        Field(
            title="Folder identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Identifier of the existing article folder.",
        ),
    ]
    folder_key: Annotated[str, Field(title="Folder key", examples=["python"])]
    author_username: Annotated[str, Field(title="Author", examples=["dmitriy"])]
    published_at: Annotated[
        str | None,
        Field(
            title="Publication date",
            examples=["2026-10-13T10:00:00+00:00"],
            description="Publication timestamp in ISO 8601 format, or null when unpublished.",
        ),
    ]
    publish_status: Annotated[
        PublishStatusEnum,
        Field(
            title="Publication status",
            examples=["Draft"],
            description="Publication state. Published content must satisfy publication validation.",
        ),
    ]
    updated_at: Annotated[
        str,
        Field(
            title="Update date",
            examples=["2026-10-15T14:20:00+00:00"],
            description="Last update timestamp in ISO 8601 format.",
        ),
    ]
    excerpt: Annotated[
        str,
        Field(
            title="Short preview",
            examples=["Run independent asynchronous operations concurrently with asyncio.gather."],
        ),
    ]
    metadata: Annotated[ArticleMetadataResponseSchema, Field(title="SEO metadata")]
    tags: Annotated[list[TagResponseSchema], Field(title="Tags")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: Article,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            id=str(schema.id),
            title=schema.localized_title(language=language),
            slug=schema.slug,
            folder=schema.localized_folder(language=language),
            folder_id=schema.folder.id,
            folder_key=schema.folder.key,
            author_username=schema.author_username,
            published_at=schema.published_at.isoformat()
            if schema.published_at is not None
            else None,
            publish_status=schema.publish_status,
            updated_at=schema.updated_at.isoformat(),
            excerpt=cls.build_excerpt(content=schema.localized_content(language=language)),
            metadata=ArticleMetadataResponseSchema.from_domain_schema(schema=schema.metadata),
            tags=[
                TagResponseSchema.from_domain_schema(schema=tag, language=language)
                for tag in schema.tags
            ],
        )

    @classmethod
    def build_excerpt(cls, *, content: str) -> str:
        text = re.sub(r"[`*_#>\-[\]()!]", " ", content)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= ARTICLE_EXCERPT_CHARACTER_LIMIT:
            return text

        word_end = text.find(" ", ARTICLE_EXCERPT_CHARACTER_LIMIT)
        if word_end == -1:
            return text
        return f"{text[:word_end]}…"


class ArticleDetailResponseSchema(ArticleSummaryResponseSchema):
    content: Annotated[
        str,
        Field(
            title="Content",
            examples=[
                (
                    "## Concurrent tasks\n\nUse `asyncio.gather()` to await independent "
                    "operations together."
                )
            ],
            description="Article body in Markdown for this translation.",
        ),
    ]
    created_at: Annotated[
        str,
        Field(
            title="Creation date",
            examples=["2026-10-12T09:30:00+00:00"],
            description="Creation timestamp in ISO 8601 format.",
        ),
    ]
    translations: Annotated[ArticleTranslationsResponseSchema, Field(title="Translations")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: Article,
        language: LanguageEnum,
    ) -> Self:
        summary = ArticleSummaryResponseSchema.from_domain_schema(
            schema=schema,
            language=language,
        )
        return cls(
            **summary.model_dump(),
            content=schema.localized_content(language=language),
            created_at=schema.created_at.isoformat(),
            translations=ArticleTranslationsResponseSchema.from_domain_schema(schema=schema),
        )


class ArticleListResponseSchema(CamelCaseSchema):
    total_count: Annotated[
        int,
        Field(
            title="Article count",
            examples=[42],
            description="Total matching records before pagination.",
        ),
    ]
    total_pages: Annotated[
        int,
        Field(
            title="Page count",
            examples=[3],
            description="Number of pages for the requested pageSize; zero when no records match.",
        ),
    ]
    articles: Annotated[list[ArticleSummaryResponseSchema], Field(title="Articles")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: Articles,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            total_count=schema.total_count,
            total_pages=schema.total_pages,
            articles=[
                ArticleSummaryResponseSchema.from_domain_schema(
                    schema=article,
                    language=language,
                )
                for article in schema.values
            ],
        )


class ArticlePublicStatsResponseSchema(CamelCaseSchema):
    article_id: Annotated[
        str,
        Field(
            title="Article identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable article identifier.",
        ),
    ]
    view_count: Annotated[int, Field(title="View count", examples=[120])]
    reaction_counts: Annotated[ArticleReactionCountsResponseSchema, Field(title="Reactions")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticlePublicStats) -> Self:
        return cls(
            article_id=str(schema.article_id),
            view_count=schema.view_count,
            reaction_counts=ArticleReactionCountsResponseSchema.from_domain_schema(
                schema=schema.reaction_counts,
            ),
        )


class ArticlePublicStatsCollectionResponseSchema(CamelCaseSchema):
    stats: Annotated[list[ArticlePublicStatsResponseSchema], Field(title="Public statistics")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticlePublicStatsCollection) -> Self:
        return cls(
            stats=[
                ArticlePublicStatsResponseSchema.from_domain_schema(schema=item)
                for item in schema.values
            ],
        )


class ArticleTranslationSchema(CamelCaseSchema):
    title: Annotated[
        RequiredShortText, Field(title="Title", examples=["Understanding asyncio.gather"])
    ]
    content: Annotated[
        ArticleContentText,
        Field(
            title="Content",
            examples=[
                (
                    "## Concurrent tasks\n\nUse `asyncio.gather()` to await independent "
                    "operations together."
                )
            ],
            description="Article body in Markdown for this translation.",
        ),
    ]


class ArticleTranslationsSchema(CamelCaseSchema):
    ru: Annotated[ArticleTranslationSchema, Field(title="Russian translation")]
    en: Annotated[ArticleTranslationSchema, Field(title="English translation")]


class ArticleTranslationsResponseSchema(CamelCaseSchema):
    ru: Annotated[ArticleTranslationSchema, Field(title="Russian translation")]
    en: Annotated[ArticleTranslationSchema, Field(title="English translation")]

    @classmethod
    def from_domain_schema(cls, *, schema: Article) -> Self:
        return cls(
            ru=ArticleTranslationSchema(
                title=schema.title_ru,
                content=schema.content_ru,
            ),
            en=ArticleTranslationSchema(
                title=schema.title_en,
                content=schema.content_en,
            ),
        )


class ArticleRequestSchema(CamelCaseSchema):
    slug: Annotated[
        SlugString,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    folder_id: Annotated[
        RequiredShortText,
        Field(
            title="Folder identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Identifier of the existing article folder.",
        ),
    ]
    publish_status: Annotated[
        PublishStatusEnum,
        Field(
            title="Publication status",
            examples=["Draft"],
            description="Publication state. Published content must satisfy publication validation.",
        ),
    ]
    tag_ids: Annotated[
        list[str], Field(title="Tag identifiers", examples=[["1b734fe27bc04ace9f2c18fa26ad5081"]])
    ]
    translations: Annotated[ArticleTranslationsSchema, Field(title="Translations")]
    metadata: Annotated[ArticleMetadataRequestSchema, Field(title="SEO metadata")]

    def to_create_schema(
        self,
        *,
        article_id: str,
        author_username: str,
    ) -> ArticleCreateParams:
        return ArticleCreateParams(
            id=article_id,
            slug=self.slug,
            title_ru=self.translations.ru.title,
            title_en=self.translations.en.title,
            content_ru=self.translations.ru.content,
            content_en=self.translations.en.content,
            folder_id=self.folder_id,
            author_username=author_username,
            publish_status=self.publish_status,
            metadata=self.metadata.to_domain_schema(),
            tag_ids=list(self.tag_ids),
        )

    def to_update_schema(self) -> ArticleUpdateParams:
        return ArticleUpdateParams(
            slug=self.slug,
            title_ru=self.translations.ru.title,
            title_en=self.translations.en.title,
            content_ru=self.translations.ru.content,
            content_en=self.translations.en.content,
            folder_id=self.folder_id,
            publish_status=self.publish_status,
            metadata=self.metadata.to_domain_schema(),
            tag_ids=list(self.tag_ids),
        )


class ArticleReactionRequestSchema(CamelCaseSchema):
    reaction_kind: Annotated[
        ArticleReactionKind | None,
        Field(
            title="Reaction",
            examples=["heart"],
            description="Selected reaction, or null to remove this client’s existing reaction.",
        ),
    ]
    client_token: Annotated[
        str,
        Field(
            title="Anonymous client token",
            min_length=1,
            max_length=255,
            examples=["f09b1464-bd20-41d2-9c9a-ccf0e0d0b614"],
            description=(
                "Non-empty browser-scoped anonymous reaction identifier; reuse it "
                "to replace or clear a reaction."
            ),
        ),
    ]


class ArticleTreeItemResponseSchema(CamelCaseSchema):
    title: Annotated[str, Field(title="Title", examples=["Understanding asyncio.gather"])]
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    publish_status: Annotated[
        PublishStatusEnum,
        Field(
            title="Publication status",
            examples=["Draft"],
            description="Publication state. Published content must satisfy publication validation.",
        ),
    ]
    published_at: Annotated[
        str | None,
        Field(
            title="Publication date",
            examples=["2026-10-13T10:00:00+00:00"],
            description="Publication timestamp in ISO 8601 format, or null when unpublished.",
        ),
    ]
    updated_at: Annotated[
        str,
        Field(
            title="Update date",
            examples=["2026-10-15T14:20:00+00:00"],
            description="Last update timestamp in ISO 8601 format.",
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleTreeItem) -> Self:
        return cls(
            title=schema.title,
            slug=schema.slug,
            publish_status=schema.publish_status,
            published_at=schema.published_at.isoformat()
            if schema.published_at is not None
            else None,
            updated_at=schema.updated_at.isoformat(),
        )


class ArticleTreeFolderResponseSchema(CamelCaseSchema):
    folder_id: Annotated[
        str,
        Field(
            title="Folder identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Identifier of the existing article folder.",
        ),
    ]
    folder_key: Annotated[str, Field(title="Folder key", examples=["python"])]
    folder: Annotated[str, Field(title="Folder", examples=["Python"])]
    articles: Annotated[list[ArticleTreeItemResponseSchema], Field(title="Articles")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleTreeFolder) -> Self:
        return cls(
            folder_id=schema.folder_id,
            folder_key=schema.folder_key,
            folder=schema.folder,
            articles=[
                ArticleTreeItemResponseSchema.from_domain_schema(schema=article)
                for article in schema.articles
            ],
        )


class ArticleTreeResponseSchema(CamelCaseSchema):
    folders: Annotated[list[ArticleTreeFolderResponseSchema], Field(title="Folders")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleTree) -> Self:
        return cls(
            folders=[
                ArticleTreeFolderResponseSchema.from_domain_schema(schema=folder)
                for folder in schema.folders
            ],
        )


class ArticleFolderNameSchema(CamelCaseSchema):
    name: Annotated[
        RequiredShortText,
        Field(
            title="Name",
            examples=["Async IO"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]


class ArticleFolderTranslationsSchema(CamelCaseSchema):
    ru: Annotated[ArticleFolderNameSchema, Field(title="Russian translation")]
    en: Annotated[ArticleFolderNameSchema, Field(title="English translation")]


class ArticleFolderResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    key: Annotated[
        str,
        Field(
            title="Key",
            examples=["python"],
            description="Stable language-neutral key used to reference this structure node.",
        ),
    ]
    name: Annotated[
        str,
        Field(
            title="Name",
            examples=["Async IO"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]
    priority: Annotated[
        int,
        Field(
            title="Priority",
            examples=[2],
            description="Position used to order items within their parent.",
        ),
    ]
    translations: Annotated[ArticleFolderTranslationsSchema, Field(title="Translations")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleFolder, language: LanguageEnum) -> Self:
        return cls(
            id=schema.id,
            key=schema.key,
            name=schema.localized_name(language=language),
            priority=schema.priority,
            translations=ArticleFolderTranslationsSchema(
                ru=ArticleFolderNameSchema(name=schema.name_ru),
                en=ArticleFolderNameSchema(name=schema.name_en),
            ),
        )


class ArticleFoldersResponseSchema(CamelCaseSchema):
    folders: Annotated[list[ArticleFolderResponseSchema], Field(title="Folders")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleFolders, language: LanguageEnum) -> Self:
        return cls(
            folders=[
                ArticleFolderResponseSchema.from_domain_schema(
                    schema=folder,
                    language=language,
                )
                for folder in schema
            ],
        )


class ArticleFolderRequestSchema(CamelCaseSchema):
    key: Annotated[
        SlugString,
        Field(
            title="Key",
            examples=["python"],
            description="Stable language-neutral key used to reference this structure node.",
        ),
    ]
    translations: Annotated[ArticleFolderTranslationsSchema, Field(title="Translations")]

    def to_create_schema(self, *, folder_id: str) -> ArticleFolderCreateParams:
        return ArticleFolderCreateParams(
            id=folder_id,
            key=self.key,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
        )


class ArticleFolderPriorityUpdateRequestSchema(CamelCaseSchema):
    ordered_ids: Annotated[
        list[str],
        Field(
            title="Ordered identifiers",
            examples=[["1b734fe27bc04ace9f2c18fa26ad5081", "26226d65583d45ec8aee065d773d595f"]],
            description=(
                "Complete ordered identifiers of all siblings; omitted, duplicate,"
                " or foreign identifiers are rejected."
            ),
        ),
    ]

    def to_schema(self) -> ArticleFolderPriorityUpdateParams:
        return ArticleFolderPriorityUpdateParams(ordered_ids=tuple(self.ordered_ids))


class ArticleAnalyticsTotalsResponseSchema(CamelCaseSchema):
    view_count: Annotated[int, Field(title="View count", examples=[120])]
    engaged_view_count: Annotated[int, Field(title="Engaged view count", examples=[78])]
    reaction_count: Annotated[int, Field(title="Reaction count", examples=[32])]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleAnalyticsTotals) -> Self:
        return cls(
            view_count=schema.view_count,
            engaged_view_count=schema.engaged_view_count,
            reaction_count=schema.reaction_count,
        )


class ArticleAnalyticsArticleStatsResponseSchema(CamelCaseSchema):
    article_id: Annotated[
        str,
        Field(
            title="Article identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable article identifier.",
        ),
    ]
    title: Annotated[str, Field(title="Title", examples=["Understanding asyncio.gather"])]
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    view_count: Annotated[int, Field(title="View count", examples=[120])]
    engaged_view_count: Annotated[int, Field(title="Engaged view count", examples=[78])]
    reaction_counts: Annotated[ArticleReactionCountsResponseSchema, Field(title="Reactions")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleAnalyticsArticleStats) -> Self:
        return cls(
            article_id=str(schema.article_id),
            title=schema.title,
            slug=schema.slug,
            view_count=schema.view_count,
            engaged_view_count=schema.engaged_view_count,
            reaction_counts=ArticleReactionCountsResponseSchema.from_domain_schema(
                schema=schema.reaction_counts,
            ),
        )


class ArticleAnalyticsDailyStatsResponseSchema(CamelCaseSchema):
    article_id: Annotated[
        str,
        Field(
            title="Article identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable article identifier.",
        ),
    ]
    title: Annotated[str, Field(title="Title", examples=["Understanding asyncio.gather"])]
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["understanding-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    date: Annotated[date, Field(title="Date", examples=["2026-10-15"])]
    source_category: Annotated[
        ArticleViewSourceCategory, Field(title="Source", examples=["Search"])
    ]
    view_count: Annotated[int, Field(title="View count", examples=[120])]
    engaged_view_count: Annotated[int, Field(title="Engaged view count", examples=[78])]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleAnalyticsDailyStats) -> Self:
        return cls(
            article_id=str(schema.article_id),
            title=schema.title,
            slug=schema.slug,
            date=schema.date,
            source_category=schema.source_category,
            view_count=schema.view_count,
            engaged_view_count=schema.engaged_view_count,
        )


class ArticleAnalyticsStatsResponseSchema(CamelCaseSchema):
    date_from: Annotated[date, Field(title="Start date", examples=["2026-10-01"])]
    date_to: Annotated[date, Field(title="End date", examples=["2026-10-15"])]
    totals: Annotated[ArticleAnalyticsTotalsResponseSchema, Field(title="Totals")]
    articles: Annotated[list[ArticleAnalyticsArticleStatsResponseSchema], Field(title="Articles")]
    daily: Annotated[list[ArticleAnalyticsDailyStatsResponseSchema], Field(title="Days")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleAnalyticsStats) -> Self:
        return cls(
            date_from=schema.date_from,
            date_to=schema.date_to,
            totals=ArticleAnalyticsTotalsResponseSchema.from_domain_schema(schema=schema.totals),
            articles=[
                ArticleAnalyticsArticleStatsResponseSchema.from_domain_schema(schema=article)
                for article in schema.articles
            ],
            daily=[
                ArticleAnalyticsDailyStatsResponseSchema.from_domain_schema(schema=item)
                for item in schema.daily
            ],
        )
