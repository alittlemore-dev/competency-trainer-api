from datetime import datetime
from typing import Self

from sqlalchemy import Enum, ForeignKey, Index, LargeBinary, String, UniqueConstraint, func, or_
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import (
    AttachedExternalResource,
    AttachedExternalResources,
    CompetencyMatrixItem,
    CompetencyMatrixItemStructure,
    CompetencyMatrixQuestionFingerprint,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    ExternalResource,
    MatrixQuestionClaimSummary,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateParams,
)
from core.enums import PublishStatusEnum
from infra.postgresql.models.base import BaseModel, TableArgs
from infra.postgresql.models.mixins.ids import HexUuidIDMixin
from infra.postgresql.models.mixins.priority import PriorityMixin
from infra.postgresql.models.mixins.publish import PublishMixin


class ExternalResourceModel(HexUuidIDMixin, BaseModel):
    name_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian resource name",
    )
    name_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English resource name",
    )
    url: Mapped[str] = mapped_column(
        String(length=2048),
        doc="Resource URL",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "cm_external_resource_name_ru_trgm_idx",
                func.lower(cls.name_ru).label("name_ru_lower"),
                postgresql_using="gin",
                postgresql_ops={"name_ru_lower": "gin_trgm_ops"},
            ),
            Index(
                "cm_external_resource_name_en_trgm_idx",
                func.lower(cls.name_en).label("name_en_lower"),
                postgresql_using="gin",
                postgresql_ops={"name_en_lower": "gin_trgm_ops"},
            ),
            Index(
                "cm_external_resource_url_trgm_idx",
                func.lower(cls.url).label("url_lower"),
                postgresql_using="gin",
                postgresql_ops={"url_lower": "gin_trgm_ops"},
            ),
        )

    def __str__(self) -> str:
        return f'External resource "{self.name_en}"'

    @classmethod
    def from_domain_schema(cls, schema: ExternalResource) -> Self:
        return cls(
            id=schema.id,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            url=schema.url,
        )

    def to_domain_schema(self) -> ExternalResource:
        return ExternalResource(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            url=self.url,
        )


class CompetencyMatrixSheetModel(PriorityMixin, HexUuidIDMixin, BaseModel):
    key: Mapped[str] = mapped_column(
        String(length=255),
        unique=True,
        doc="Stable language-neutral sheet key",
    )
    name_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian sheet name",
    )
    name_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English sheet name",
    )

    sections: Mapped[list[CompetencyMatrixSectionModel]] = relationship(
        back_populates="sheet",
        cascade="all, delete-orphan",
        order_by=lambda: (CompetencyMatrixSectionModel.priority, CompetencyMatrixSectionModel.id),
        doc="Sheet sections",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index("cm_sheet_key_lower_idx", func.lower(cls.key).label("sheet_key_lower")),
            Index("cm_sheet_priority_idx", cls.priority, cls.id),
        )

    def to_domain_schema(self) -> CompetencyMatrixStructureSheet:
        return CompetencyMatrixStructureSheet(
            id=self.id,
            key=self.key,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
            sections=[section.to_domain_schema() for section in self.sections],
        )


class CompetencyMatrixSectionModel(PriorityMixin, HexUuidIDMixin, BaseModel):
    sheet_id: Mapped[str] = mapped_column(
        ForeignKey(CompetencyMatrixSheetModel.id, ondelete="CASCADE"),
        doc="Sheet identifier",
    )
    name_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian section name",
    )
    name_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English section name",
    )

    sheet: Mapped[CompetencyMatrixSheetModel] = relationship(
        back_populates="sections",
        doc="Parent sheet",
    )
    subsections: Mapped[list[CompetencyMatrixSubsectionModel]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by=lambda: (
            CompetencyMatrixSubsectionModel.priority,
            CompetencyMatrixSubsectionModel.id,
        ),
        doc="Section subsections",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.sheet_id,
                cls.name_ru,
                name="cm_section_sheet_name_ru_uniq",
            ),
            UniqueConstraint(
                cls.sheet_id,
                cls.name_en,
                name="cm_section_sheet_name_en_uniq",
            ),
            Index("cm_section_sheet_en_idx", cls.sheet_id, cls.name_en, cls.id),
            Index("cm_section_sheet_ru_idx", cls.sheet_id, cls.name_ru, cls.id),
            Index(
                "cm_section_sheet_priority_idx",
                cls.sheet_id,
                cls.priority,
                cls.id,
            ),
        )

    def to_domain_schema(self) -> CompetencyMatrixStructureSection:
        return CompetencyMatrixStructureSection(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
            subsections=[subsection.to_domain_schema() for subsection in self.subsections],
        )


class CompetencyMatrixSubsectionModel(PriorityMixin, HexUuidIDMixin, BaseModel):
    section_id: Mapped[str] = mapped_column(
        ForeignKey(CompetencyMatrixSectionModel.id, ondelete="CASCADE"),
        doc="Section identifier",
    )
    name_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian subsection name",
    )
    name_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English subsection name",
    )

    section: Mapped[CompetencyMatrixSectionModel] = relationship(
        back_populates="subsections",
        doc="Parent section",
    )
    items: Mapped[list[CompetencyMatrixItemModel]] = relationship(
        back_populates="subsection",
        doc="Competency matrix questions in this subsection",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.section_id,
                cls.name_ru,
                name="cm_subsection_section_name_ru_uniq",
            ),
            UniqueConstraint(
                cls.section_id,
                cls.name_en,
                name="cm_subsection_section_name_en_uniq",
            ),
            Index("cm_subsection_section_en_idx", cls.section_id, cls.name_en, cls.id),
            Index("cm_subsection_section_ru_idx", cls.section_id, cls.name_ru, cls.id),
            Index(
                "cm_subsection_section_priority_idx",
                cls.section_id,
                cls.priority,
                cls.id,
            ),
        )

    def to_domain_schema(self) -> CompetencyMatrixStructureSubsection:
        return CompetencyMatrixStructureSubsection(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
        )

    def to_item_structure(self) -> CompetencyMatrixItemStructure:
        return CompetencyMatrixItemStructure(
            sheet_id=self.section.sheet.id,
            sheet_key=self.section.sheet.key,
            sheet_ru=self.section.sheet.name_ru,
            sheet_en=self.section.sheet.name_en,
            section_id=self.section.id,
            section_ru=self.section.name_ru,
            section_en=self.section.name_en,
            subsection_id=self.id,
            subsection_ru=self.name_ru,
            subsection_en=self.name_en,
        )


class CompetencyMatrixItemModel(PublishMixin, HexUuidIDMixin, BaseModel):
    slug: Mapped[str] = mapped_column(
        String(length=255),
        unique=True,
        index=True,
        doc="URL slug for the competency matrix question",
    )
    question_ru: Mapped[str] = mapped_column(
        String(length=255),
        doc="Russian question",
    )
    question_en: Mapped[str] = mapped_column(
        String(length=255),
        doc="English question",
    )
    question_ru_fingerprint: Mapped[bytes] = mapped_column(
        LargeBinary(length=32),
        doc="Normalized Russian question digest",
    )
    question_en_fingerprint: Mapped[bytes] = mapped_column(
        LargeBinary(length=32),
        doc="Normalized English question digest",
    )
    answer_ru: Mapped[str] = mapped_column(
        String(),
        doc="Russian answer",
    )
    answer_en: Mapped[str] = mapped_column(
        String(),
        doc="English answer",
    )
    interview_answer_explanation_ru: Mapped[str] = mapped_column(
        String(),
        doc="Russian interview answer explanation",
    )
    interview_answer_explanation_en: Mapped[str] = mapped_column(
        String(),
        doc="English interview answer explanation",
    )
    subsection_id: Mapped[str] = mapped_column(
        ForeignKey(CompetencyMatrixSubsectionModel.id, ondelete="RESTRICT"),
        doc="Question subsection identifier",
    )
    grade: Mapped[GradeEnum | None] = mapped_column(
        Enum(GradeEnum, native_enum=True, name="grade_enum"),
        doc="Competency grade",
    )
    interview_frequency: Mapped[InterviewFrequencyEnum | None] = mapped_column(
        Enum(
            InterviewFrequencyEnum,
            native_enum=True,
            name="interview_frequency_enum",
        ),
        doc="How often the question appears in interviews",
    )
    suggested_by_username: Mapped[str] = mapped_column(
        String(length=255),
        doc="Immutable username snapshot that suggested the question",
    )

    resource_links: Mapped[list[ResourceToItemSecondaryModel]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        doc="External resource links",
    )
    subsection: Mapped[CompetencyMatrixSubsectionModel] = relationship(
        back_populates="items",
        doc="Question subsection",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index(
                "cmi_subsection_status_grade_idx",
                cls.subsection_id,
                cls.publish_status,
                cls.grade,
                cls.id,
            ),
            Index(
                "cmi_workspace_status_published_at_idx",
                cls.publish_status,
                cls.published_at.desc().nulls_last(),
                cls.id,
            ),
            Index(
                "cmi_workspace_subsection_status_grade_idx",
                cls.subsection_id,
                cls.publish_status,
                cls.grade,
                cls.id,
            ),
            Index(
                "cmi_workspace_missing_fields_idx",
                or_(
                    func.length(func.trim(cls.slug)) == 0,
                    cls.grade.is_(None),
                    func.length(func.trim(cls.question_ru)) == 0,
                    func.length(func.trim(cls.question_en)) == 0,
                    func.length(func.trim(cls.answer_ru)) == 0,
                    func.length(func.trim(cls.answer_en)) == 0,
                    func.length(func.trim(cls.interview_answer_explanation_ru)) == 0,
                    func.length(func.trim(cls.interview_answer_explanation_en)) == 0,
                ),
            ),
            Index(
                "cmi_workspace_slug_trgm_idx",
                func.lower(cls.slug).label("workspace_slug_lower"),
                postgresql_using="gin",
                postgresql_ops={"workspace_slug_lower": "gin_trgm_ops"},
            ),
            Index(
                "cmi_workspace_question_ru_trgm_idx",
                func.lower(cls.question_ru).label("workspace_question_ru_lower"),
                postgresql_using="gin",
                postgresql_ops={"workspace_question_ru_lower": "gin_trgm_ops"},
            ),
            Index(
                "cmi_workspace_question_en_trgm_idx",
                func.lower(cls.question_en).label("workspace_question_en_lower"),
                postgresql_using="gin",
                postgresql_ops={"workspace_question_en_lower": "gin_trgm_ops"},
            ),
            Index(
                "cmi_question_ru_fingerprint_idx",
                cls.question_ru_fingerprint,
            ),
            Index(
                "cmi_question_en_fingerprint_idx",
                cls.question_en_fingerprint,
            ),
        )

    def __str__(self) -> str:
        return f"[{self.subsection.section.name_en} - {self.subsection.name_en}] {self.question_en}"

    @classmethod
    def from_domain_schema(
        cls,
        item: CompetencyMatrixItem,
        *,
        include_relationships: bool,
    ) -> Self:
        return cls(
            id=item.id,
            slug=item.slug,
            question_ru=item.question_ru,
            question_en=item.question_en,
            question_ru_fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
                question=item.question_ru,
            ).digest,
            question_en_fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
                question=item.question_en,
            ).digest,
            answer_ru=item.answer_ru,
            answer_en=item.answer_en,
            publish_status=item.publish_status,
            published_at=item.published_at,
            interview_answer_explanation_ru=item.interview_answer_explanation_ru,
            interview_answer_explanation_en=item.interview_answer_explanation_en,
            subsection_id=item.subsection_id,
            grade=item.grade,
            interview_frequency=item.interview_frequency,
            suggested_by_username=item.suggested_by_username,
            resource_links=[
                ResourceToItemSecondaryModel.from_domain_schema(schema=resource)
                for resource in item.resources
            ]
            if include_relationships
            else [],
        )

    def update_from_domain_schema(self, item: CompetencyMatrixItem) -> None:
        self.slug = item.slug
        self.question_ru = item.question_ru
        self.question_en = item.question_en
        self.question_ru_fingerprint = CompetencyMatrixQuestionFingerprint.from_question(
            question=item.question_ru,
        ).digest
        self.question_en_fingerprint = CompetencyMatrixQuestionFingerprint.from_question(
            question=item.question_en,
        ).digest
        self.answer_ru = item.answer_ru
        self.answer_en = item.answer_en
        self.publish_status = item.publish_status
        if item.published_at is not None:
            self.published_at = item.published_at
        self.interview_answer_explanation_ru = item.interview_answer_explanation_ru
        self.interview_answer_explanation_en = item.interview_answer_explanation_en
        self.subsection_id = item.subsection_id
        self.grade = item.grade
        self.interview_frequency = item.interview_frequency

    def to_domain_schema(self, *, include_relationships: bool) -> CompetencyMatrixItem:
        return CompetencyMatrixItem(
            id=self.id,
            slug=self.slug,
            question_ru=self.question_ru,
            question_en=self.question_en,
            answer_ru=self.answer_ru,
            answer_en=self.answer_en,
            publish_status=PublishStatusEnum.from_value(self.publish_status),
            published_at=self.published_at,
            interview_answer_explanation_ru=self.interview_answer_explanation_ru,
            interview_answer_explanation_en=self.interview_answer_explanation_en,
            structure=self.subsection.to_item_structure(),
            grade=self.grade,
            interview_frequency=self.interview_frequency,
            suggested_by_username=self.suggested_by_username,
            resources=AttachedExternalResources(
                values=(
                    [link.to_domain_schema() for link in self.resource_links]
                    if include_relationships
                    else []
                ),
            ),
        )


class QueuedQuestionModel(HexUuidIDMixin, BaseModel):
    question: Mapped[str] = mapped_column(
        String(length=255),
        doc="Suggested or imported raw competency matrix question",
    )
    question_fingerprint: Mapped[bytes] = mapped_column(
        LargeBinary(length=32),
        doc="Normalized queued question digest",
    )
    grade: Mapped[GradeEnum | None] = mapped_column(
        Enum(GradeEnum, native_enum=True, name="grade_enum"),
        doc="Optional competency grade",
    )
    sheet: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="Optional sheet name or key",
    )
    section: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="Optional section",
    )
    subsection: Mapped[str | None] = mapped_column(
        String(length=255),
        doc="Optional subsection",
    )
    suggested_by_username: Mapped[str] = mapped_column(
        String(length=255),
        doc="Immutable username snapshot that suggested the question",
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(timezone=True),
        doc="Queue insertion time",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            Index("cm_queued_question_fifo_idx", cls.created_at),
            Index("cm_queued_question_suggested_by_idx", cls.suggested_by_username),
            Index("cm_queued_question_fingerprint_idx", cls.question_fingerprint),
        )

    @classmethod
    def from_create_params(
        cls,
        *,
        params: QueuedCompetencyMatrixQuestionCreateParams,
        created_at: datetime,
        suggested_by_username: str,
    ) -> Self:
        return cls(
            question=params.question,
            question_fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
                question=params.question,
            ).digest,
            grade=params.grade,
            sheet=params.sheet,
            section=None,
            subsection=None,
            suggested_by_username=suggested_by_username,
            created_at=created_at,
        )

    @classmethod
    def from_domain_schema(cls, schema: QueuedCompetencyMatrixQuestion) -> Self:
        return cls(
            id=schema.id,
            question=schema.question,
            question_fingerprint=CompetencyMatrixQuestionFingerprint.from_question(
                question=schema.question,
            ).digest,
            grade=schema.grade,
            sheet=schema.sheet,
            section=schema.section,
            subsection=schema.subsection,
            suggested_by_username=schema.suggested_by_username,
            created_at=schema.created_at,
        )

    def to_domain_schema(
        self,
        *,
        claim: MatrixQuestionClaimSummary | None,
    ) -> QueuedCompetencyMatrixQuestion:
        return QueuedCompetencyMatrixQuestion(
            id=self.id,
            question=self.question,
            grade=self.grade,
            sheet=self.sheet,
            section=self.section,
            subsection=self.subsection,
            suggested_by_username=self.suggested_by_username,
            created_at=self.created_at,
            claim=claim,
        )


class ResourceToItemSecondaryModel(HexUuidIDMixin, BaseModel):
    item_id: Mapped[str] = mapped_column(
        ForeignKey(CompetencyMatrixItemModel.id, ondelete="CASCADE"),
        doc="Competency matrix item identifier",
    )
    resource_id: Mapped[str] = mapped_column(
        ForeignKey(ExternalResourceModel.id, ondelete="CASCADE"),
        doc="External resource identifier",
    )
    context_ru: Mapped[str] = mapped_column(
        String(),
        doc="Russian context for why the resource was attached",
    )
    context_en: Mapped[str] = mapped_column(
        String(),
        doc="English context for why the resource was attached",
    )

    item: Mapped[CompetencyMatrixItemModel] = relationship(
        back_populates="resource_links",
        doc="Competency matrix item",
    )
    resource: Mapped[ExternalResourceModel] = relationship(
        doc="External resource",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (UniqueConstraint(cls.item_id, cls.resource_id, name="cm_resource_item_uniq"),)

    @classmethod
    def from_domain_schema(cls, schema: AttachedExternalResource) -> Self:
        return cls(
            resource_id=schema.id,
            resource=ExternalResourceModel.from_domain_schema(
                schema=schema.to_external_resource(),
            ),
            context_ru=schema.context_ru,
            context_en=schema.context_en,
        )

    def to_domain_schema(self) -> AttachedExternalResource:
        return AttachedExternalResource(
            id=self.resource.id,
            name_ru=self.resource.name_ru,
            name_en=self.resource.name_en,
            url=self.resource.url,
            context_ru=self.context_ru,
            context_en=self.context_en,
        )
