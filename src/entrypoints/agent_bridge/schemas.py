from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel as camel_case

from core.agent_access.schemas import (
    AgentMatrixQuestionClaim,
    ExistingMatrixQuestionDraftResourceParams,
    MatrixAuthoringContext,
    MatrixQuestionDraftResourceParams,
    MatrixQuestionDraftSaveParams,
    MatrixQuestionDraftSaveResult,
)
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import (
    CompetencyMatrixStructure,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    ExternalResource,
    ExternalResources,
)
from infra.config.constants import constants


class AgentBridgeSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_case,
        extra="forbid",
        populate_by_name=True,
    )


MatrixClaimIdInput = Annotated[
    str,
    Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$"),
]
MatrixSubsectionIdInput = Annotated[
    str,
    Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$"),
]
MatrixSearchNameInput = Annotated[
    str,
    Field(min_length=1, max_length=constants.admin_validation.short_text_max_length),
]
MatrixSearchLimitInput = Annotated[int, Field(ge=1, le=50)]
MatrixSlugInput = Annotated[
    str,
    Field(
        min_length=1,
        max_length=constants.admin_validation.short_text_max_length,
        pattern=constants.admin_validation.slug_pattern,
    ),
]
MatrixLongTextInput = Annotated[
    str,
    Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
]


class ExistingMatrixDraftResourceInput(AgentBridgeSchema):
    resource_id: MatrixClaimIdInput
    context_ru: MatrixLongTextInput
    context_en: MatrixLongTextInput

    def to_domain_schema(self) -> ExistingMatrixQuestionDraftResourceParams:
        return ExistingMatrixQuestionDraftResourceParams(
            resource_id=self.resource_id,
            context_ru=self.context_ru,
            context_en=self.context_en,
        )


class NewMatrixDraftResourceInput(AgentBridgeSchema):
    name_ru: MatrixSearchNameInput
    name_en: MatrixSearchNameInput
    url: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.url_max_length),
    ]
    context_ru: MatrixLongTextInput
    context_en: MatrixLongTextInput

    def to_domain_schema(self) -> MatrixQuestionDraftResourceParams:
        return MatrixQuestionDraftResourceParams(
            name_ru=self.name_ru,
            name_en=self.name_en,
            url=self.url,
            context_ru=self.context_ru,
            context_en=self.context_en,
        )


MatrixDraftResourceInput = ExistingMatrixDraftResourceInput | NewMatrixDraftResourceInput
MatrixDraftResourcesInput = Annotated[
    list[MatrixDraftResourceInput],
    Field(
        min_length=constants.agent_access.minimum_resource_count,
        max_length=constants.agent_access.maximum_resource_count,
    ),
]


class MatrixQuestionDraftSaveInput(AgentBridgeSchema):
    slug: MatrixSlugInput
    subsection_id: MatrixSubsectionIdInput
    grade: GradeEnum
    interview_frequency: InterviewFrequencyEnum
    question_ru: MatrixLongTextInput
    question_en: MatrixLongTextInput
    answer_ru: MatrixLongTextInput
    answer_en: MatrixLongTextInput
    interview_answer_explanation_ru: MatrixLongTextInput
    interview_answer_explanation_en: MatrixLongTextInput
    resources: MatrixDraftResourcesInput

    def to_domain_schema(self, *, claim_id: str) -> MatrixQuestionDraftSaveParams:
        return MatrixQuestionDraftSaveParams(
            claim_id=claim_id,
            slug=self.slug,
            subsection_id=self.subsection_id,
            grade=self.grade,
            interview_frequency=self.interview_frequency,
            question_ru=self.question_ru,
            question_en=self.question_en,
            answer_ru=self.answer_ru,
            answer_en=self.answer_en,
            interview_answer_explanation_ru=self.interview_answer_explanation_ru,
            interview_answer_explanation_en=self.interview_answer_explanation_en,
            resources=tuple(resource.to_domain_schema() for resource in self.resources),
        )


class MatrixQuestionClaimOutput(AgentBridgeSchema):
    claim_id: str
    queue_item_id: str
    question: str
    grade: GradeEnum | None
    sheet: str | None
    section: str | None
    subsection: str | None
    suggested_by_username: str
    created_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentMatrixQuestionClaim,
    ) -> MatrixQuestionClaimOutput:
        return cls.model_construct(
            claim_id=schema.claim_id,
            queue_item_id=schema.queue_item_id,
            question=schema.question,
            grade=schema.grade,
            sheet=schema.sheet,
            section=schema.section,
            subsection=schema.subsection,
            suggested_by_username=schema.suggested_by_username,
            created_at=schema.created_at,
            expires_at=schema.expires_at,
        )


class MatrixStructureSubsectionOutput(AgentBridgeSchema):
    id: str
    name_ru: str
    name_en: str
    priority: int

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSubsection,
    ) -> MatrixStructureSubsectionOutput:
        return cls.model_construct(
            id=schema.id,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            priority=schema.priority,
        )


class MatrixStructureSectionOutput(AgentBridgeSchema):
    id: str
    name_ru: str
    name_en: str
    priority: int
    subsections: list[MatrixStructureSubsectionOutput]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSection,
    ) -> MatrixStructureSectionOutput:
        return cls.model_construct(
            id=schema.id,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            priority=schema.priority,
            subsections=[
                MatrixStructureSubsectionOutput.from_domain_schema(schema=subsection)
                for subsection in schema.subsections
            ],
        )


class MatrixStructureSheetOutput(AgentBridgeSchema):
    id: str
    key: str
    name_ru: str
    name_en: str
    priority: int
    sections: list[MatrixStructureSectionOutput]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSheet,
    ) -> MatrixStructureSheetOutput:
        return cls.model_construct(
            id=schema.id,
            key=schema.key,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            priority=schema.priority,
            sections=[
                MatrixStructureSectionOutput.from_domain_schema(schema=section)
                for section in schema.sections
            ],
        )


class MatrixStructureOutput(AgentBridgeSchema):
    sheets: list[MatrixStructureSheetOutput]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructure,
    ) -> MatrixStructureOutput:
        return cls.model_construct(
            sheets=[
                MatrixStructureSheetOutput.from_domain_schema(schema=sheet)
                for sheet in schema.sheets
            ],
        )


class MatrixAuthoringContextOutput(AgentBridgeSchema):
    structure: MatrixStructureOutput
    grades: list[GradeEnum]
    interview_frequencies: list[InterviewFrequencyEnum]
    minimum_resource_count: int
    maximum_resource_count: int

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: MatrixAuthoringContext,
    ) -> MatrixAuthoringContextOutput:
        return cls.model_construct(
            structure=MatrixStructureOutput.from_domain_schema(schema=schema.structure),
            grades=list(schema.grades),
            interview_frequencies=list(schema.interview_frequencies),
            minimum_resource_count=schema.minimum_resource_count,
            maximum_resource_count=schema.maximum_resource_count,
        )


class MatrixResourceOutput(AgentBridgeSchema):
    id: str
    name_ru: str
    name_en: str
    url: str

    @classmethod
    def from_domain_schema(cls, *, schema: ExternalResource) -> MatrixResourceOutput:
        return cls.model_construct(
            id=schema.id,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            url=schema.url,
        )


class MatrixResourcesOutput(AgentBridgeSchema):
    resources: list[MatrixResourceOutput]

    @classmethod
    def from_domain_schema(cls, *, schema: ExternalResources) -> MatrixResourcesOutput:
        return cls.model_construct(
            resources=[MatrixResourceOutput.from_domain_schema(schema=item) for item in schema],
        )


class MatrixDraftSaveOutput(AgentBridgeSchema):
    item_id: str
    publish_status: Literal["Draft"]
    replayed: bool

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: MatrixQuestionDraftSaveResult,
    ) -> MatrixDraftSaveOutput:
        return cls.model_construct(
            item_id=schema.item_id,
            publish_status="Draft",
            replayed=schema.replayed,
        )


class MatrixClaimReleaseOutput(AgentBridgeSchema):
    released: Literal[True]
