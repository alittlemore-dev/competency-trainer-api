from datetime import datetime
from typing import Annotated

from pydantic import Field

from core.agent_access.schemas import (
    AgentCertificateRotation,
    AgentCertificateRotationResult,
    ExistingMatrixQuestionDraftResourceParams,
    MatrixAuthoringContext,
    MatrixQuestionClaim,
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
    ExternalResources,
)
from entrypoints.litestar.api.schemas import CamelCaseSchema
from infra.config.constants import constants


class ExistingMatrixDraftResourceRequestSchema(CamelCaseSchema):
    resource_id: Annotated[str, Field(min_length=32, max_length=32)]
    context_ru: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    context_en: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]

    def to_domain_schema(self) -> ExistingMatrixQuestionDraftResourceParams:
        return ExistingMatrixQuestionDraftResourceParams(
            resource_id=self.resource_id,
            context_ru=self.context_ru,
            context_en=self.context_en,
        )


class NewMatrixDraftResourceRequestSchema(CamelCaseSchema):
    name_ru: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.short_text_max_length),
    ]
    name_en: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.short_text_max_length),
    ]
    url: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.url_max_length),
    ]
    context_ru: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    context_en: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]

    def to_domain_schema(self) -> MatrixQuestionDraftResourceParams:
        return MatrixQuestionDraftResourceParams(
            name_ru=self.name_ru,
            name_en=self.name_en,
            url=self.url,
            context_ru=self.context_ru,
            context_en=self.context_en,
        )


MatrixDraftResourceRequestSchema = (
    ExistingMatrixDraftResourceRequestSchema | NewMatrixDraftResourceRequestSchema
)


class MatrixQuestionDraftSaveRequestSchema(CamelCaseSchema):
    slug: Annotated[
        str,
        Field(
            min_length=1,
            max_length=constants.admin_validation.short_text_max_length,
            pattern=constants.admin_validation.slug_pattern,
        ),
    ]
    subsection_id: Annotated[str, Field(min_length=32, max_length=32)]
    grade: GradeEnum
    interview_frequency: InterviewFrequencyEnum
    question_ru: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    question_en: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    answer_ru: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    answer_en: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    interview_answer_explanation_ru: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    interview_answer_explanation_en: Annotated[
        str,
        Field(min_length=1, max_length=constants.admin_validation.matrix_long_text_max_length),
    ]
    resources: Annotated[
        list[MatrixDraftResourceRequestSchema],
        Field(
            min_length=constants.agent_access.minimum_resource_count,
            max_length=constants.agent_access.maximum_resource_count,
        ),
    ]

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


class AgentCertificateRotationRequestSchema(CamelCaseSchema):
    rotation_id: Annotated[
        str,
        Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$"),
    ]
    csr_pem: Annotated[
        str,
        Field(min_length=1, max_length=constants.agent_access.csr_pem_max_length),
    ]


class MatrixQuestionClaimResponseSchema(CamelCaseSchema):
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
        schema: MatrixQuestionClaim,
    ) -> MatrixQuestionClaimResponseSchema:
        return cls.model_construct(
            claim_id=schema.id,
            queue_item_id=schema.question.id,
            question=schema.question.question,
            grade=schema.question.grade,
            sheet=schema.question.sheet,
            section=schema.question.section,
            subsection=schema.question.subsection,
            suggested_by_username=schema.question.suggested_by_username,
            created_at=schema.question.created_at,
            expires_at=schema.expires_at,
        )


class MatrixStructureSubsectionResponseSchema(CamelCaseSchema):
    id: str
    name_ru: str
    name_en: str
    priority: int

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSubsection,
    ) -> MatrixStructureSubsectionResponseSchema:
        return cls.model_construct(
            id=schema.id,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            priority=schema.priority,
        )


class MatrixStructureSectionResponseSchema(CamelCaseSchema):
    id: str
    name_ru: str
    name_en: str
    priority: int
    subsections: list[MatrixStructureSubsectionResponseSchema]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSection,
    ) -> MatrixStructureSectionResponseSchema:
        return cls.model_construct(
            id=schema.id,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            priority=schema.priority,
            subsections=[
                MatrixStructureSubsectionResponseSchema.from_domain_schema(schema=subsection)
                for subsection in schema.subsections
            ],
        )


class MatrixStructureSheetResponseSchema(CamelCaseSchema):
    id: str
    key: str
    name_ru: str
    name_en: str
    priority: int
    sections: list[MatrixStructureSectionResponseSchema]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSheet,
    ) -> MatrixStructureSheetResponseSchema:
        return cls.model_construct(
            id=schema.id,
            key=schema.key,
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            priority=schema.priority,
            sections=[
                MatrixStructureSectionResponseSchema.from_domain_schema(schema=section)
                for section in schema.sections
            ],
        )


class MatrixStructureResponseSchema(CamelCaseSchema):
    sheets: list[MatrixStructureSheetResponseSchema]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructure,
    ) -> MatrixStructureResponseSchema:
        return cls.model_construct(
            sheets=[
                MatrixStructureSheetResponseSchema.from_domain_schema(schema=sheet)
                for sheet in schema.sheets
            ],
        )


class MatrixAuthoringContextResponseSchema(CamelCaseSchema):
    structure: MatrixStructureResponseSchema
    grades: list[GradeEnum]
    interview_frequencies: list[InterviewFrequencyEnum]
    minimum_resource_count: int
    maximum_resource_count: int

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: MatrixAuthoringContext,
    ) -> MatrixAuthoringContextResponseSchema:
        return cls.model_construct(
            structure=MatrixStructureResponseSchema.from_domain_schema(schema=schema.structure),
            grades=list(schema.grades),
            interview_frequencies=list(schema.interview_frequencies),
            minimum_resource_count=schema.minimum_resource_count,
            maximum_resource_count=schema.maximum_resource_count,
        )


class MatrixResourceResponseSchema(CamelCaseSchema):
    id: str
    name_ru: str
    name_en: str
    url: str


class MatrixResourcesResponseSchema(CamelCaseSchema):
    resources: list[MatrixResourceResponseSchema]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: ExternalResources,
    ) -> MatrixResourcesResponseSchema:
        return cls.model_construct(
            resources=[
                MatrixResourceResponseSchema.model_construct(
                    id=resource.id,
                    name_ru=resource.name_ru,
                    name_en=resource.name_en,
                    url=resource.url,
                )
                for resource in schema
            ],
        )


class MatrixQuestionDraftSaveResponseSchema(CamelCaseSchema):
    item_id: str
    publish_status: str
    replayed: bool

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: MatrixQuestionDraftSaveResult,
    ) -> MatrixQuestionDraftSaveResponseSchema:
        return cls.model_construct(
            item_id=schema.item_id,
            publish_status="Draft",
            replayed=schema.replayed,
        )


class MatrixQuestionClaimReleaseResponseSchema(CamelCaseSchema):
    released: bool


class AgentCertificateRotationResponseSchema(CamelCaseSchema):
    certificate_pem: str
    certificate_chain_pem: str
    fingerprint_sha256: str
    serial_number: str
    valid_from: datetime
    expires_at: datetime
    replayed: bool

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentCertificateRotationResult,
    ) -> AgentCertificateRotationResponseSchema:
        return cls.model_construct(
            certificate_pem=schema.certificate.certificate_pem,
            certificate_chain_pem=schema.certificate_chain_pem,
            fingerprint_sha256=schema.certificate.fingerprint_sha256,
            serial_number=schema.certificate.serial_number,
            valid_from=schema.certificate.valid_from,
            expires_at=schema.certificate.expires_at,
            replayed=schema.replayed,
        )


class AgentCertificateRotationConfirmResponseSchema(CamelCaseSchema):
    rotation_id: str
    confirmed_at: datetime
    confirmed: bool

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentCertificateRotation,
    ) -> AgentCertificateRotationConfirmResponseSchema:
        if schema.confirmed_at is None:
            msg = "confirmed rotation must have a confirmation timestamp"
            raise ValueError(msg)
        return cls.model_construct(
            rotation_id=schema.rotation_id,
            confirmed_at=schema.confirmed_at,
            confirmed=True,
        )
