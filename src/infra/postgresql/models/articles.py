from datetime import date
from typing import Self

from sqlalchemy import (
    Computed,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    inspect,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy_dev_utils.mixins.audit import AuditMixin

from core.articles.enums import ArticleReactionKind, ArticleViewSourceCategory
from core.articles.schemas import Article, ArticleFolder, ArticleMetadata, Tag, Tags
from core.enums import PublishStatusEnum
from core.files.enums import FilePurpose
from infra.postgresql.models.base import BaseModel, TableArgs
from infra.postgresql.models.files import FileModel
from infra.postgresql.models.mixins.ids import HexUuidIDMixin
from infra.postgresql.models.mixins.priority import PriorityMixin
from infra.postgresql.models.mixins.publish import PublishMixin


class ArticleFolderModel(PriorityMixin, HexUuidIDMixin, BaseModel):
    key: Mapped[str] = mapped_column(
        String(length=255),
        doc="Stable language-neutral folder key",
    )
    name_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian human-readable folder name",
    )
    name_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English human-readable folder name",
    )
    articles: Mapped[list[ArticleModel]] = relationship(
        back_populates="folder",
        doc="Articles assigned to this folder",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "articles_folder_key_lower_uniq",
                func.lower(cls.key).label("folder_key_lower"),
                unique=True,
            ),
            Index("articles_folder_priority_id_idx", cls.priority, cls.id),
            Index(
                "articles_folder_name_ru_idx",
                func.lower(cls.name_ru).label("folder_name_ru_lower"),
                cls.id,
            ),
            Index(
                "articles_folder_name_en_idx",
                func.lower(cls.name_en).label("folder_name_en_lower"),
                cls.id,
            ),
        )

    def __str__(self) -> str:
        return f'Article folder "{self.key}"'

    @classmethod
    def from_domain_schema(cls, folder: ArticleFolder) -> Self:
        return cls(
            id=folder.id,
            key=folder.key,
            name_ru=folder.name_ru,
            name_en=folder.name_en,
            priority=folder.priority,
        )

    def to_domain_schema(self) -> ArticleFolder:
        return ArticleFolder(
            id=self.id,
            key=self.key,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
        )


class ArticleModel(PublishMixin, HexUuidIDMixin, AuditMixin, BaseModel):
    title_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian title of the article",
    )
    title_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English title of the article",
    )
    content_ru: Mapped[str] = mapped_column(
        String(),
        doc="Russian content of the article",
    )
    content_en: Mapped[str] = mapped_column(
        String(),
        doc="English content of the article",
    )
    slug: Mapped[str] = mapped_column(
        String(length=255),
        unique=True,
        index=True,
        doc="URL slug for the article",
    )
    folder_id: Mapped[str] = mapped_column(
        ForeignKey(ArticleFolderModel.id, ondelete="RESTRICT"),
        doc="Article folder identifier",
    )
    author_username: Mapped[str] = mapped_column(
        String(length=255),
        doc="Username of the article author",
    )
    seo_title_ru: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="Russian SEO title override for the article",
    )
    seo_title_en: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="English SEO title override for the article",
    )
    seo_description_ru: Mapped[str | None] = mapped_column(
        String(length=320),
        doc="Russian SEO description for the article",
    )
    seo_description_en: Mapped[str | None] = mapped_column(
        String(length=320),
        doc="English SEO description for the article",
    )
    cover_image_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("files__file_model.id", ondelete="RESTRICT"),
        doc="Managed article cover image file identifier",
    )
    cover_image_alt_ru: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="Russian cover image alt text",
    )
    cover_image_alt_en: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="English cover image alt text",
    )
    search_vector_ru: Mapped[str] = mapped_column(
        TSVECTOR(),
        Computed(
            "setweight(to_tsvector('simple', coalesce(title_ru, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(content_ru, '')), 'B')",
            persisted=True,
        ),
        doc="Generated full-text search vector for Russian title and content",
    )
    search_vector_en: Mapped[str] = mapped_column(
        TSVECTOR(),
        Computed(
            "setweight(to_tsvector('simple', coalesce(title_en, '')), 'A') || "
            "setweight(to_tsvector('simple', coalesce(content_en, '')), 'B')",
            persisted=True,
        ),
        doc="Generated full-text search vector for English title and content",
    )

    tag_links: Mapped[list[ArticleToTagSecondaryModel]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        doc="Links between articles and tags",
    )
    folder: Mapped[ArticleFolderModel] = relationship(
        back_populates="articles",
        doc="One-level article tree folder",
    )
    cover_image_file: Mapped[FileModel | None] = relationship(
        doc="Managed article cover image file",
    )
    file_usage_links: Mapped[list[ArticleFileUsageModel]] = relationship(
        back_populates="article",
        cascade="all, delete-orphan",
        doc="Managed files used by article content",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "articles_article_search_vector_gin_idx",
                cls.search_vector_ru,
                postgresql_using="gin",
            ),
            Index(
                "articles_article_search_vector_en_gin_idx",
                cls.search_vector_en,
                postgresql_using="gin",
            ),
            Index(
                "articles_article_publish_status_published_at_idx",
                cls.publish_status,
                cls.published_at,
            ),
            Index(
                "articles_article_publish_status_published_updated_idx",
                cls.publish_status,
                cls.published_at.desc().nulls_last(),
                cls.updated_at.desc(),
            ),
            Index("articles_article_cover_image_file_idx", cls.cover_image_file_id),
            Index(
                "articles_article_tree_folder_ru_published_idx",
                cls.folder_id,
                cls.published_at.desc().nulls_last(),
                cls.updated_at.desc(),
                cls.title_ru,
                postgresql_include=(cls.slug, cls.publish_status),
                postgresql_where=cls.publish_status == PublishStatusEnum.PUBLISHED,
            ),
            Index(
                "articles_article_tree_folder_en_published_idx",
                cls.folder_id,
                cls.published_at.desc().nulls_last(),
                cls.updated_at.desc(),
                cls.title_en,
                postgresql_include=(cls.slug, cls.publish_status),
                postgresql_where=cls.publish_status == PublishStatusEnum.PUBLISHED,
            ),
        )

    def __str__(self) -> str:
        return f'Article "{self.title_en}"'

    @classmethod
    def from_domain_schema(cls, article: Article) -> Self:
        return cls(
            id=article.id,
            title_ru=article.title_ru,
            title_en=article.title_en,
            content_ru=article.content_ru,
            content_en=article.content_en,
            slug=article.slug,
            folder_id=article.folder.id,
            author_username=article.author_username,
            seo_title_ru=article.metadata.seo_title_ru,
            seo_title_en=article.metadata.seo_title_en,
            seo_description_ru=article.metadata.seo_description_ru,
            seo_description_en=article.metadata.seo_description_en,
            cover_image_file_id=article.metadata.cover_image_file_id,
            cover_image_alt_ru=article.metadata.cover_image_alt_ru,
            cover_image_alt_en=article.metadata.cover_image_alt_en,
            published_at=article.published_at,
            publish_status=article.publish_status,
            created_at=article.created_at,
            updated_at=article.updated_at,
            file_usage_links=ArticleFileUsageModel.from_domain_schema(
                article=article,
            ),
        )

    def update_from_domain_schema(self, article: Article) -> None:
        self.title_ru = article.title_ru
        self.title_en = article.title_en
        self.content_ru = article.content_ru
        self.content_en = article.content_en
        self.slug = article.slug
        self.folder_id = article.folder.id
        self.seo_title_ru = article.metadata.seo_title_ru
        self.seo_title_en = article.metadata.seo_title_en
        self.seo_description_ru = article.metadata.seo_description_ru
        self.seo_description_en = article.metadata.seo_description_en
        self.cover_image_file_id = article.metadata.cover_image_file_id
        self.cover_image_alt_ru = article.metadata.cover_image_alt_ru
        self.cover_image_alt_en = article.metadata.cover_image_alt_en
        self.publish_status = article.publish_status
        self.published_at = article.published_at
        self.updated_at = article.updated_at

    def to_domain_schema(
        self,
        *,
        include_tags: bool,
        include_files: bool,
    ) -> Article:
        return Article(
            id=self.id,
            slug=self.slug,
            title_ru=self.title_ru,
            title_en=self.title_en,
            content_ru=self.content_ru,
            content_en=self.content_en,
            folder=self.folder.to_domain_schema(),
            author_username=self.author_username,
            metadata=self.to_metadata_domain_schema(include_files=include_files),
            published_at=self.published_at,
            publish_status=PublishStatusEnum.from_storage_value(self.publish_status),
            content_file_ids=(
                frozenset(link.file_id for link in self.file_usage_links)
                if include_files
                else frozenset()
            ),
            created_at=self.created_at,
            updated_at=self.updated_at,
            tags=Tags(
                values=[link.tag.to_domain_schema() for link in self.tag_links]
                if include_tags
                else [],
            ),
        )

    def to_metadata_domain_schema(self, *, include_files: bool) -> ArticleMetadata:
        cover_image_file = (
            self.cover_image_file.to_domain_schema()
            if include_files
            and "cover_image_file" not in inspect(self).unloaded
            and self.cover_image_file is not None
            else None
        )
        return ArticleMetadata(
            seo_title_ru=self.seo_title_ru,
            seo_title_en=self.seo_title_en,
            seo_description_ru=self.seo_description_ru,
            seo_description_en=self.seo_description_en,
            cover_image_file_id=self.cover_image_file_id,
            cover_image_file=cover_image_file,
            cover_image_url=None,
            cover_image_alt_ru=self.cover_image_alt_ru,
            cover_image_alt_en=self.cover_image_alt_en,
        )


class TagModel(HexUuidIDMixin, AuditMixin, BaseModel):
    name_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian human-readable tag name",
    )
    name_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English human-readable tag name",
    )
    slug: Mapped[str] = mapped_column(
        String(length=255),
        unique=True,
        index=True,
        doc="Stable tag slug used in filters",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "articles_tag_name_ru_trgm_idx",
                func.lower(cls.name_ru).label("name_ru_lower"),
                postgresql_using="gin",
                postgresql_ops={"name_ru_lower": "gin_trgm_ops"},
            ),
            Index(
                "articles_tag_name_en_trgm_idx",
                func.lower(cls.name_en).label("name_en_lower"),
                postgresql_using="gin",
                postgresql_ops={"name_en_lower": "gin_trgm_ops"},
            ),
            Index(
                "articles_tag_slug_trgm_idx",
                func.lower(cls.slug).label("slug_lower"),
                postgresql_using="gin",
                postgresql_ops={"slug_lower": "gin_trgm_ops"},
            ),
        )

    def __str__(self) -> str:
        return f'Tag "{self.name_en}"'

    @classmethod
    def from_domain_schema(cls, tag: Tag) -> Self:
        return cls(
            id=tag.id,
            name_ru=tag.name_ru,
            name_en=tag.name_en,
            slug=tag.slug,
        )

    def update_from_domain_schema(self, tag: Tag) -> None:
        self.name_ru = tag.name_ru
        self.name_en = tag.name_en
        self.slug = tag.slug

    def to_domain_schema(self) -> Tag:
        return Tag(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            slug=self.slug,
        )


class ArticleToTagSecondaryModel(HexUuidIDMixin, BaseModel):
    article_id: Mapped[str] = mapped_column(
        ForeignKey(ArticleModel.id, ondelete="CASCADE"),
        doc="Article identifier",
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey(TagModel.id, ondelete="CASCADE"),
        doc="Tag identifier",
    )

    article: Mapped[ArticleModel] = relationship(
        back_populates="tag_links",
        doc="Linked article",
    )
    tag: Mapped[TagModel] = relationship(
        doc="Linked tag",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (UniqueConstraint(cls.article_id, cls.tag_id, name="articles_article_tag_uniq"),)

    @classmethod
    def from_domain_schema(cls, tag: Tag) -> Self:
        return cls(
            tag_id=tag.id,
        )


class ArticleFileUsageModel(HexUuidIDMixin, BaseModel):
    article_id: Mapped[str] = mapped_column(
        ForeignKey(ArticleModel.id, ondelete="CASCADE"),
        doc="Article identifier",
    )
    file_id: Mapped[str] = mapped_column(
        ForeignKey("files__file_model.id", ondelete="RESTRICT"),
        doc="Managed file identifier",
    )
    usage: Mapped[FilePurpose] = mapped_column(
        Enum(
            FilePurpose,
            native_enum=True,
            name="file_purpose_enum",
        ),
        doc="How the article uses the managed file",
    )

    article: Mapped[ArticleModel] = relationship(
        back_populates="file_usage_links",
        doc="Linked article",
    )
    file: Mapped[FileModel] = relationship(
        doc="Linked managed file",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.article_id,
                cls.file_id,
                cls.usage,
                name="articles_file_usage_article_file_usage_uniq",
            ),
            Index("articles_file_usage_file_idx", cls.file_id),
        )

    @classmethod
    def from_domain_schema(cls, article: Article) -> list[Self]:
        return [
            cls(
                article_id=article.id,
                file_id=file_id,
                usage=FilePurpose.ARTICLE_CONTENT_IMAGE,
            )
            for file_id in sorted(article.content_file_ids)
        ]


class ArticleDailyAnalyticsModel(HexUuidIDMixin, BaseModel):
    article_id: Mapped[str] = mapped_column(
        ForeignKey(ArticleModel.id, ondelete="CASCADE"),
        doc="Article identifier",
    )
    date: Mapped[date] = mapped_column(
        Date(),
        doc="UTC day when the article interaction was recorded",
    )
    source_category: Mapped[ArticleViewSourceCategory] = mapped_column(
        Enum(
            ArticleViewSourceCategory,
            native_enum=True,
            name="article_view_source_category_enum",
        ),
        doc="Coarse referrer source category",
    )
    view_count: Mapped[int] = mapped_column(
        Integer(),
        doc="Number of public article detail views",
    )
    engaged_view_count: Mapped[int] = mapped_column(
        Integer(),
        doc="Number of public article detail views with engagement signal",
    )

    article: Mapped[ArticleModel] = relationship(doc="Tracked article")

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.article_id,
                cls.date,
                cls.source_category,
                name="articles_daily_analytics_article_date_source_uniq",
            ),
        )


class ArticleReactionModel(HexUuidIDMixin, AuditMixin, BaseModel):
    article_id: Mapped[str] = mapped_column(
        ForeignKey(ArticleModel.id, ondelete="CASCADE"),
        doc="Article identifier",
    )
    article_scoped_voter_hash: Mapped[str] = mapped_column(
        String(length=64),
        doc="HMAC hash scoped to one article and one anonymous client token",
    )
    reaction_kind: Mapped[ArticleReactionKind] = mapped_column(
        Enum(
            ArticleReactionKind,
            native_enum=True,
            name="article_reaction_kind_enum",
        ),
        doc="Anonymous reaction kind",
    )

    article: Mapped[ArticleModel] = relationship(doc="Reacted article")

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.article_id,
                cls.article_scoped_voter_hash,
                name="articles_reaction_article_voter_uniq",
            ),
        )
