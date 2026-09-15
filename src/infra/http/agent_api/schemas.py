from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from core.agent_access.schemas import (
    AgentCertificateRotationConfirmation,
    AgentCertificateRotationStartParams,
    AgentClientCertificateRotation,
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


class AgentApiWireSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        populate_by_name=True,
    )


type AgentApiHexId = Annotated[
    str,
    Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$"),
]


class ExistingMatrixDraftResourceRequest(AgentApiWireSchema):
    resource_id: AgentApiHexId
    context_ru: str
    context_en: str

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: ExistingMatrixQuestionDraftResourceParams,
    ) -> ExistingMatrixDraftResourceRequest:
        return cls(
            resource_id=schema.resource_id,
            context_ru=schema.context_ru,
            context_en=schema.context_en,
        )


class NewMatrixDraftResourceRequest(AgentApiWireSchema):
    name_ru: str
    name_en: str
    url: str
    context_ru: str
    context_en: str

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: MatrixQuestionDraftResourceParams,
    ) -> NewMatrixDraftResourceRequest:
        return cls(
            name_ru=schema.name_ru,
            name_en=schema.name_en,
            url=schema.url,
            context_ru=schema.context_ru,
            context_en=schema.context_en,
        )


type MatrixDraftResourceRequest = ExistingMatrixDraftResourceRequest | NewMatrixDraftResourceRequest


class MatrixQuestionDraftSaveRequest(AgentApiWireSchema):
    slug: str
    subsection_id: AgentApiHexId
    grade: GradeEnum
    interview_frequency: InterviewFrequencyEnum
    question_ru: str
    question_en: str
    answer_ru: str
    answer_en: str
    interview_answer_explanation_ru: str
    interview_answer_explanation_en: str
    resources: list[MatrixDraftResourceRequest]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: MatrixQuestionDraftSaveParams,
    ) -> MatrixQuestionDraftSaveRequest:
        resources: list[MatrixDraftResourceRequest] = []
        for resource in schema.resources:
            if isinstance(resource, ExistingMatrixQuestionDraftResourceParams):
                resources.append(
                    ExistingMatrixDraftResourceRequest.from_domain_schema(schema=resource),
                )
            else:
                resources.append(NewMatrixDraftResourceRequest.from_domain_schema(schema=resource))
        return cls(
            slug=schema.slug,
            subsection_id=schema.subsection_id,
            grade=schema.grade,
            interview_frequency=schema.interview_frequency,
            question_ru=schema.question_ru,
            question_en=schema.question_en,
            answer_ru=schema.answer_ru,
            answer_en=schema.answer_en,
            interview_answer_explanation_ru=schema.interview_answer_explanation_ru,
            interview_answer_explanation_en=schema.interview_answer_explanation_en,
            resources=resources,
        )


class AgentCertificateRotationRequest(AgentApiWireSchema):
    rotation_id: AgentApiHexId
    csr_pem: str

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AgentCertificateRotationStartParams,
    ) -> AgentCertificateRotationRequest:
        return cls(rotation_id=schema.rotation_id, csr_pem=schema.csr_pem)


class MatrixQuestionClaimResponse(AgentApiWireSchema):
    claim_id: AgentApiHexId
    queue_item_id: AgentApiHexId
    question: str
    grade: GradeEnum | None
    sheet: str | None
    section: str | None
    subsection: str | None
    suggested_by_username: str
    created_at: datetime
    expires_at: datetime

    def to_domain_schema(self) -> AgentMatrixQuestionClaim:
        return AgentMatrixQuestionClaim(
            claim_id=self.claim_id,
            queue_item_id=self.queue_item_id,
            question=self.question,
            grade=self.grade,
            sheet=self.sheet,
            section=self.section,
            subsection=self.subsection,
            suggested_by_username=self.suggested_by_username,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )


class MatrixStructureSubsectionResponse(AgentApiWireSchema):
    id: AgentApiHexId
    name_ru: str
    name_en: str
    priority: int

    def to_domain_schema(self) -> CompetencyMatrixStructureSubsection:
        return CompetencyMatrixStructureSubsection(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
        )


class MatrixStructureSectionResponse(AgentApiWireSchema):
    id: AgentApiHexId
    name_ru: str
    name_en: str
    priority: int
    subsections: list[MatrixStructureSubsectionResponse]

    def to_domain_schema(self) -> CompetencyMatrixStructureSection:
        return CompetencyMatrixStructureSection(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
            subsections=[subsection.to_domain_schema() for subsection in self.subsections],
        )


class MatrixStructureSheetResponse(AgentApiWireSchema):
    id: AgentApiHexId
    key: str
    name_ru: str
    name_en: str
    priority: int
    sections: list[MatrixStructureSectionResponse]

    def to_domain_schema(self) -> CompetencyMatrixStructureSheet:
        return CompetencyMatrixStructureSheet(
            id=self.id,
            key=self.key,
            name_ru=self.name_ru,
            name_en=self.name_en,
            priority=self.priority,
            sections=[section.to_domain_schema() for section in self.sections],
        )


class MatrixStructureResponse(AgentApiWireSchema):
    sheets: list[MatrixStructureSheetResponse]

    def to_domain_schema(self) -> CompetencyMatrixStructure:
        return CompetencyMatrixStructure(
            sheets=[sheet.to_domain_schema() for sheet in self.sheets],
        )


class MatrixAuthoringContextResponse(AgentApiWireSchema):
    structure: MatrixStructureResponse
    grades: list[GradeEnum]
    interview_frequencies: list[InterviewFrequencyEnum]
    minimum_resource_count: int
    maximum_resource_count: int

    def to_domain_schema(self) -> MatrixAuthoringContext:
        return MatrixAuthoringContext(
            structure=self.structure.to_domain_schema(),
            grades=tuple(self.grades),
            interview_frequencies=tuple(self.interview_frequencies),
            minimum_resource_count=self.minimum_resource_count,
            maximum_resource_count=self.maximum_resource_count,
        )


class MatrixResourceResponse(AgentApiWireSchema):
    id: AgentApiHexId
    name_ru: str
    name_en: str
    url: str

    def to_domain_schema(self) -> ExternalResource:
        return ExternalResource(
            id=self.id,
            name_ru=self.name_ru,
            name_en=self.name_en,
            url=self.url,
        )


class MatrixResourcesResponse(AgentApiWireSchema):
    resources: list[MatrixResourceResponse]

    def to_domain_schema(self) -> ExternalResources:
        return ExternalResources(
            values=[resource.to_domain_schema() for resource in self.resources],
        )


class MatrixQuestionDraftSaveResponse(AgentApiWireSchema):
    item_id: AgentApiHexId
    publish_status: Literal["Draft"]
    replayed: bool

    def to_domain_schema(self) -> MatrixQuestionDraftSaveResult:
        return MatrixQuestionDraftSaveResult(item_id=self.item_id, replayed=self.replayed)


class MatrixQuestionClaimReleaseResponse(AgentApiWireSchema):
    released: Literal[True]


class AgentCertificateRotationResponse(AgentApiWireSchema):
    certificate_pem: Annotated[str, Field(min_length=1)]
    certificate_chain_pem: Annotated[str, Field(min_length=1)]
    fingerprint_sha256: Annotated[
        str,
        Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"),
    ]
    serial_number: Annotated[str, Field(min_length=1, pattern=r"^[0-9a-f]+$")]
    valid_from: datetime
    expires_at: datetime
    replayed: bool

    def to_domain_schema(self) -> AgentClientCertificateRotation:
        return AgentClientCertificateRotation(
            certificate_pem=self.certificate_pem,
            certificate_chain_pem=self.certificate_chain_pem,
            fingerprint_sha256=self.fingerprint_sha256,
            serial_number=self.serial_number,
            valid_from=self.valid_from,
            expires_at=self.expires_at,
            replayed=self.replayed,
        )


class AgentCertificateRotationConfirmResponse(AgentApiWireSchema):
    rotation_id: AgentApiHexId
    confirmed_at: datetime
    confirmed: Literal[True]

    def to_domain_schema(self) -> AgentCertificateRotationConfirmation:
        return AgentCertificateRotationConfirmation(
            rotation_id=self.rotation_id,
            confirmed_at=self.confirmed_at,
        )


class MatrixResourceSearchQuery(AgentApiWireSchema):
    search_name: str
    limit: int
    language: str


class ClaimReference(AgentApiWireSchema):
    claim_id: AgentApiHexId


class RotationReference(AgentApiWireSchema):
    rotation_id: AgentApiHexId
