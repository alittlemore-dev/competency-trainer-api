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
    id: Annotated[str, Field(title="Identifier")]
    name: Annotated[str, Field(title="Name")]
    slug: Annotated[str, Field(title="Slug")]
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
    name: Annotated[RequiredShortText, Field(title="Name")]


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
    slug: Annotated[SlugString, Field(title="Slug")]
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
    heart: Annotated[int, Field(title="Reaction: liked")]
    fire: Annotated[int, Field(title="Reaction: want more")]
    thinking: Annotated[int, Field(title="Reaction: thought-provoking")]
    neutral: Annotated[int, Field(title="Reaction: neutral")]
    poop: Annotated[int, Field(title="Reaction: disliked")]

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
        Field(title="RU SEO title", max_length=constants.admin_validation.short_text_max_length),
    ]
    seo_title_en: Annotated[
        str | None,
        Field(title="EN SEO title", max_length=constants.admin_validation.short_text_max_length),
    ]
    seo_description_ru: Annotated[
        str | None,
        Field(
            title="RU SEO description",
            max_length=constants.admin_validation.seo_description_max_length,
        ),
    ]
    seo_description_en: Annotated[
        str | None,
        Field(
            title="EN SEO description",
            max_length=constants.admin_validation.seo_description_max_length,
        ),
    ]
    cover_image_file_id: Annotated[str | None, Field(title="Cover image file ID")]
    cover_image_alt_ru: Annotated[
        str | None,
        Field(
            title="RU cover image alt",
            max_length=constants.admin_validation.short_text_max_length,
        ),
    ]
    cover_image_alt_en: Annotated[
        str | None,
        Field(
            title="EN cover image alt",
            max_length=constants.admin_validation.short_text_max_length,
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
    cover_image_url: Annotated[OptionalHttpUrlString, Field(title="Cover image URL")]

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
    id: Annotated[str, Field(title="Identifier")]
    title: Annotated[str, Field(title="Title")]
    slug: Annotated[str, Field(title="Slug")]
    folder: Annotated[str, Field(title="Folder")]
    folder_id: Annotated[str, Field(title="Folder identifier")]
    folder_key: Annotated[str, Field(title="Folder key")]
    author_username: Annotated[str, Field(title="Author")]
    published_at: Annotated[str | None, Field(title="Publication date")]
    publish_status: Annotated[PublishStatusEnum, Field(title="Publication status")]
    updated_at: Annotated[str, Field(title="Update date")]
    excerpt: Annotated[str, Field(title="Short preview")]
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
    content: Annotated[str, Field(title="Content")]
    created_at: Annotated[str, Field(title="Creation date")]
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
    total_count: Annotated[int, Field(title="Article count")]
    total_pages: Annotated[int, Field(title="Page count")]
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
    article_id: Annotated[str, Field(title="Article identifier")]
    view_count: Annotated[int, Field(title="View count")]
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
    title: Annotated[RequiredShortText, Field(title="Title")]
    content: Annotated[ArticleContentText, Field(title="Content")]


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
    slug: Annotated[SlugString, Field(title="Slug")]
    folder_id: Annotated[RequiredShortText, Field(title="Folder identifier")]
    publish_status: Annotated[PublishStatusEnum, Field(title="Publication status")]
    tag_ids: Annotated[list[str], Field(title="Tag identifiers")]
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
    reaction_kind: Annotated[ArticleReactionKind | None, Field(title="Reaction")]
    client_token: Annotated[
        str,
        Field(title="Anonymous client token", min_length=1, max_length=255),
    ]


class ArticleTreeItemResponseSchema(CamelCaseSchema):
    title: Annotated[str, Field(title="Title")]
    slug: Annotated[str, Field(title="Slug")]
    publish_status: Annotated[PublishStatusEnum, Field(title="Publication status")]
    published_at: Annotated[str | None, Field(title="Publication date")]
    updated_at: Annotated[str, Field(title="Update date")]

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
    folder_id: Annotated[str, Field(title="Folder identifier")]
    folder_key: Annotated[str, Field(title="Folder key")]
    folder: Annotated[str, Field(title="Folder")]
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
    name: Annotated[RequiredShortText, Field(title="Name")]


class ArticleFolderTranslationsSchema(CamelCaseSchema):
    ru: Annotated[ArticleFolderNameSchema, Field(title="Russian translation")]
    en: Annotated[ArticleFolderNameSchema, Field(title="English translation")]


class ArticleFolderResponseSchema(CamelCaseSchema):
    id: Annotated[str, Field(title="Identifier")]
    key: Annotated[str, Field(title="Key")]
    name: Annotated[str, Field(title="Name")]
    priority: Annotated[int, Field(title="Priority")]
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
    key: Annotated[SlugString, Field(title="Key")]
    translations: Annotated[ArticleFolderTranslationsSchema, Field(title="Translations")]

    def to_create_schema(self, *, folder_id: str) -> ArticleFolderCreateParams:
        return ArticleFolderCreateParams(
            id=folder_id,
            key=self.key,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
        )


class ArticleFolderPriorityUpdateRequestSchema(CamelCaseSchema):
    ordered_ids: Annotated[list[str], Field(title="Ordered identifiers")]

    def to_schema(self) -> ArticleFolderPriorityUpdateParams:
        return ArticleFolderPriorityUpdateParams(ordered_ids=tuple(self.ordered_ids))


class ArticleAnalyticsTotalsResponseSchema(CamelCaseSchema):
    view_count: Annotated[int, Field(title="View count")]
    engaged_view_count: Annotated[int, Field(title="Engaged view count")]
    reaction_count: Annotated[int, Field(title="Reaction count")]

    @classmethod
    def from_domain_schema(cls, *, schema: ArticleAnalyticsTotals) -> Self:
        return cls(
            view_count=schema.view_count,
            engaged_view_count=schema.engaged_view_count,
            reaction_count=schema.reaction_count,
        )


class ArticleAnalyticsArticleStatsResponseSchema(CamelCaseSchema):
    article_id: Annotated[str, Field(title="Article identifier")]
    title: Annotated[str, Field(title="Title")]
    slug: Annotated[str, Field(title="Slug")]
    view_count: Annotated[int, Field(title="View count")]
    engaged_view_count: Annotated[int, Field(title="Engaged view count")]
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
    article_id: Annotated[str, Field(title="Article identifier")]
    title: Annotated[str, Field(title="Title")]
    slug: Annotated[str, Field(title="Slug")]
    date: Annotated[date, Field(title="Date")]
    source_category: Annotated[ArticleViewSourceCategory, Field(title="Source")]
    view_count: Annotated[int, Field(title="View count")]
    engaged_view_count: Annotated[int, Field(title="Engaged view count")]

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
    date_from: Annotated[date, Field(title="Start date")]
    date_to: Annotated[date, Field(title="End date")]
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
