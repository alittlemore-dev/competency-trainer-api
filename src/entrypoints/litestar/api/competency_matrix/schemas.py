from collections.abc import Iterable
from itertools import groupby
from typing import Annotated, Self

from litestar.datastructures.upload_file import UploadFile
from pydantic import ConfigDict, Field, field_validator, model_validator

from core.competency_matrix.enums import (
    GradeEnum,
    InterviewFrequencyEnum,
    QuestionQueueImportIssueCodeEnum,
    QuestionQueueImportIssueSeverityEnum,
)
from core.competency_matrix.schemas import (
    AttachedExternalResource,
    CompetencyMatrixFilterOption,
    CompetencyMatrixFilterOptions,
    CompetencyMatrixFilterSectionOption,
    CompetencyMatrixFilterSheetOption,
    CompetencyMatrixFilterSubsectionOption,
    CompetencyMatrixItem,
    CompetencyMatrixItemCreateParams,
    CompetencyMatrixItems,
    CompetencyMatrixItemUpdateParams,
    CompetencyMatrixMissingFieldEnum,
    CompetencyMatrixSectionCreateParams,
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetCreateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixStructure,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    CompetencyMatrixSubsectionCreateParams,
    CompetencyMatrixSubsectionPriorityUpdateParams,
    CompetencyMatrixWorkspace,
    CompetencyMatrixWorkspaceItem,
    CompetencyMatrixWorkspaceSummary,
    ExistingExternalResourceAttachment,
    ExternalResource,
    ExternalResources,
    NewExternalResourceAttachment,
    QuestionQueueImportPreview,
    QuestionQueueImportPreviewIssue,
    QuestionQueueImportPreviewRow,
    QuestionSuggestionCreateParams,
    QuestionSuggestionLimitParams,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateItemParams,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestions,
    Sheet,
    Sheets,
)
from core.enums import PublishStatusEnum
from core.generators import HexUuidIdGenerator
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.parameters import MultipartFileMediaTypes
from entrypoints.litestar.api.schemas import CamelCaseSchema
from entrypoints.litestar.api.validation import (
    MatrixLongText,
    RequiredHttpUrlString,
    RequiredShortText,
    SlugString,
)


class ResourceTranslationSchema(CamelCaseSchema):
    name: Annotated[
        RequiredShortText,
        Field(
            title="Name",
            examples=["Python asyncio documentation"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]


class ResourceTranslationsSchema(CamelCaseSchema):
    ru: Annotated[ResourceTranslationSchema, Field(title="Russian translation")]
    en: Annotated[ResourceTranslationSchema, Field(title="English translation")]


class StructureNameTranslationSchema(CamelCaseSchema):
    name: Annotated[
        RequiredShortText,
        Field(
            title="Name",
            examples=["Async IO"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]


class StructureNameTranslationsSchema(CamelCaseSchema):
    ru: Annotated[StructureNameTranslationSchema, Field(title="Russian translation")]
    en: Annotated[StructureNameTranslationSchema, Field(title="English translation")]


class MatrixStructureSubsectionResponseSchema(CamelCaseSchema):
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
    translations: Annotated[StructureNameTranslationsSchema, Field(title="Translations")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSubsection,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            id=schema.id,
            name=schema.localized_name(language=language),
            priority=schema.priority,
            translations=StructureNameTranslationsSchema(
                ru=StructureNameTranslationSchema(name=schema.name_ru),
                en=StructureNameTranslationSchema(name=schema.name_en),
            ),
        )


class MatrixStructureSectionResponseSchema(CamelCaseSchema):
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
    translations: Annotated[StructureNameTranslationsSchema, Field(title="Translations")]
    subsections: Annotated[
        list[MatrixStructureSubsectionResponseSchema],
        Field(title="Subsections"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSection,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            id=schema.id,
            name=schema.localized_name(language=language),
            priority=schema.priority,
            translations=StructureNameTranslationsSchema(
                ru=StructureNameTranslationSchema(name=schema.name_ru),
                en=StructureNameTranslationSchema(name=schema.name_en),
            ),
            subsections=[
                MatrixStructureSubsectionResponseSchema.from_domain_schema(
                    schema=subsection,
                    language=language,
                )
                for subsection in schema.subsections
            ],
        )


class MatrixStructureSheetResponseSchema(CamelCaseSchema):
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
    translations: Annotated[StructureNameTranslationsSchema, Field(title="Translations")]
    sections: Annotated[
        list[MatrixStructureSectionResponseSchema],
        Field(title="Sections"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructureSheet,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            id=schema.id,
            key=schema.key,
            name=schema.localized_name(language=language),
            priority=schema.priority,
            translations=StructureNameTranslationsSchema(
                ru=StructureNameTranslationSchema(name=schema.name_ru),
                en=StructureNameTranslationSchema(name=schema.name_en),
            ),
            sections=[
                MatrixStructureSectionResponseSchema.from_domain_schema(
                    schema=section,
                    language=language,
                )
                for section in schema.sections
            ],
        )


class MatrixStructureResponseSchema(CamelCaseSchema):
    sheets: Annotated[list[MatrixStructureSheetResponseSchema], Field(title="Sheets")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixStructure,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            sheets=[
                MatrixStructureSheetResponseSchema.from_domain_schema(
                    schema=sheet,
                    language=language,
                )
                for sheet in schema.sheets
            ],
        )


class MatrixSheetCreateRequestSchema(CamelCaseSchema):
    key: Annotated[
        SlugString,
        Field(
            title="Key",
            examples=["python"],
            description="Stable language-neutral key used to reference this structure node.",
        ),
    ]
    translations: Annotated[StructureNameTranslationsSchema, Field(title="Translations")]

    def to_schema(self) -> CompetencyMatrixSheetCreateParams:
        return CompetencyMatrixSheetCreateParams(
            key=self.key,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
        )


class MatrixSectionCreateRequestSchema(CamelCaseSchema):
    translations: Annotated[StructureNameTranslationsSchema, Field(title="Translations")]

    def to_schema(self, *, sheet_id: str) -> CompetencyMatrixSectionCreateParams:
        return CompetencyMatrixSectionCreateParams(
            sheet_id=sheet_id,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
        )


class MatrixSubsectionCreateRequestSchema(CamelCaseSchema):
    translations: Annotated[StructureNameTranslationsSchema, Field(title="Translations")]

    def to_schema(self, *, section_id: str) -> CompetencyMatrixSubsectionCreateParams:
        return CompetencyMatrixSubsectionCreateParams(
            section_id=section_id,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
        )


class MatrixStructurePriorityUpdateRequestSchema(CamelCaseSchema):
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

    def to_sheet_schema(self) -> CompetencyMatrixSheetPriorityUpdateParams:
        return CompetencyMatrixSheetPriorityUpdateParams(
            ordered_ids=tuple(self.ordered_ids),
        )

    def to_section_schema(self, *, sheet_id: str) -> CompetencyMatrixSectionPriorityUpdateParams:
        return CompetencyMatrixSectionPriorityUpdateParams(
            sheet_id=sheet_id,
            ordered_ids=tuple(self.ordered_ids),
        )

    def to_subsection_schema(
        self,
        *,
        section_id: str,
    ) -> CompetencyMatrixSubsectionPriorityUpdateParams:
        return CompetencyMatrixSubsectionPriorityUpdateParams(
            section_id=section_id,
            ordered_ids=tuple(self.ordered_ids),
        )


class QuestionSuggestionRequestSchema(CamelCaseSchema):
    model_config = ConfigDict(json_schema_extra={"required": ["question"]})

    question: Annotated[
        RequiredShortText,
        Field(
            title="Question",
            examples=["How does asyncio.gather handle concurrent awaitables?"],
            description="Question text in the selected language, or in this explicit translation.",
        ),
    ]
    sheet: Annotated[
        RequiredShortText | None,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Optional queue sheet label; omitted or blank means no sheet.",
        ),
    ]

    @model_validator(mode="before")
    @classmethod
    def allow_omitted_sheet(cls, data: object) -> object:
        if isinstance(data, dict) and "sheet" not in data:
            return {**data, "sheet": None}
        return data

    @field_validator("question", mode="after")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            msg = "question must not be blank"
            raise ValueError(msg)
        return question

    @field_validator("sheet", mode="after")
    @classmethod
    def normalize_sheet(cls, value: str | None) -> str | None:
        if value is None:
            return None
        sheet = value.strip()
        if not sheet:
            return None
        return sheet

    def to_schema(
        self,
        *,
        limit: QuestionSuggestionLimitParams | None,
        suggested_by_username: str,
        reject_duplicates: bool,
        validate_public_sheet: bool,
    ) -> QuestionSuggestionCreateParams:
        return QuestionSuggestionCreateParams(
            question=QueuedCompetencyMatrixQuestionCreateParams(
                question=self.question,
                sheet=self.sheet,
                grade=None,
            ),
            limit=limit,
            suggested_by_username=suggested_by_username,
            reject_duplicates=reject_duplicates,
            validate_public_sheet=validate_public_sheet,
        )


class PublicQuestionSuggestionRequestSchema(QuestionSuggestionRequestSchema):
    model_config = ConfigDict(json_schema_extra={"required": ["question", "sheet"]})

    sheet: Annotated[
        RequiredShortText,
        Field(
            title="Sheet",
            examples=["python"],
            description="Existing language-neutral sheet key. Unknown keys return HTTP 400.",
        ),
    ]


class QueuedQuestionResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    question: Annotated[
        str,
        Field(
            title="Question",
            examples=["How does asyncio.gather handle concurrent awaitables?"],
            description="Question text in the selected language, or in this explicit translation.",
        ),
    ]
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    sheet: Annotated[
        str | None,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    section: Annotated[str | None, Field(title="Section", examples=["Concurrency"])]
    subsection: Annotated[str | None, Field(title="Subsection", examples=["Async IO"])]
    suggested_by_username: Annotated[str, Field(title="Suggested by", examples=["reader42"])]
    created_at: Annotated[
        str,
        Field(
            title="Creation date",
            examples=["2026-10-12T09:30:00+00:00"],
            description="Creation timestamp in ISO 8601 format.",
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: QueuedCompetencyMatrixQuestion) -> Self:
        return cls(
            id=schema.id,
            question=schema.question,
            grade=schema.grade,
            sheet=schema.sheet,
            section=schema.section,
            subsection=schema.subsection,
            suggested_by_username=schema.suggested_by_username,
            created_at=schema.created_at.isoformat(),
        )


class QueuedQuestionsResponseSchema(CamelCaseSchema):
    questions: Annotated[list[QueuedQuestionResponseSchema], Field(title="List")]

    @classmethod
    def from_domain_schema(cls, *, schema: QueuedCompetencyMatrixQuestions) -> Self:
        return cls(
            questions=[
                QueuedQuestionResponseSchema.from_domain_schema(schema=question)
                for question in schema
            ],
        )


class QueuedQuestionsImportPreviewRequestSchema(CamelCaseSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file: Annotated[
        UploadFile,
        MultipartFileMediaTypes(
            content_types=(
                "text/plain",
                "text/csv",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            ),
        ),
        Field(
            title="Import file",
            description=(
                "Binary .txt, .csv, .xlsx, or .xlsm upload with a filename. Legacy"
                " .xls is rejected. "
                "Format selection uses the filename extension. Supply the actual MIME type for "
                "the uploaded format; this is a file part, not a local filesystem path."
            ),
        ),
    ]


class QueuedQuestionsImportConfirmationRequestSchema(CamelCaseSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    file: Annotated[
        UploadFile,
        MultipartFileMediaTypes(
            content_types=(
                "text/plain",
                "text/csv",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel.sheet.macroEnabled.12",
            ),
        ),
        Field(
            title="Import file",
            description=(
                "Binary .txt, .csv, .xlsx, or .xlsm upload with a filename. Legacy"
                " .xls is rejected. "
                "Format selection uses the filename extension. Supply the actual MIME type for "
                "the uploaded format; this is a file part, not a local filesystem path."
            ),
        ),
    ]
    selected_row_numbers: Annotated[
        list[int],
        Field(
            title="Selected row numbers",
            min_length=1,
            examples=[[2, 3]],
            description="Non-empty list of one-based source row numbers selected after preview.",
        ),
    ]

    @field_validator("selected_row_numbers", mode="before")
    @classmethod
    def normalize_single_selected_row(cls, value: object) -> object:
        if isinstance(value, list):
            return value
        return [value]


class QueuedQuestionsImportPreviewIssueResponseSchema(CamelCaseSchema):
    code: Annotated[
        QuestionQueueImportIssueCodeEnum, Field(title="Issue code", examples=["duplicateInQueue"])
    ]
    severity: Annotated[
        QuestionQueueImportIssueSeverityEnum,
        Field(title="Issue severity", examples=["warning"]),
    ]
    related_row_numbers: Annotated[
        list[int],
        Field(
            title="Related row numbers",
            examples=[[4]],
            description="Other source rows involved in this duplicate warning.",
        ),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: QuestionQueueImportPreviewIssue,
    ) -> Self:
        return cls(
            code=schema.code,
            severity=schema.severity,
            related_row_numbers=list(schema.related_row_numbers),
        )


class QueuedQuestionsImportPreviewRowResponseSchema(CamelCaseSchema):
    row_number: Annotated[
        int,
        Field(
            title="Source row number",
            examples=[2],
            description=(
                "One-based row number in the source file, including the header row where present."
            ),
        ),
    ]
    question: Annotated[
        str,
        Field(
            title="Question",
            examples=["How does asyncio.gather handle concurrent awaitables?"],
            description="Question text in the selected language, or in this explicit translation.",
        ),
    ]
    sheet: Annotated[
        str,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    grade: Annotated[
        str,
        Field(
            title="Grade",
            examples=["Middle"],
            description=(
                "Raw grade text from the source row; empty when the file does not supply a grade."
            ),
        ),
    ]
    can_import: Annotated[
        bool,
        Field(
            title="Whether the row can be imported",
            examples=[True],
            description="Whether this row passes validation and can be included in confirmation.",
        ),
    ]
    selected_by_default: Annotated[
        bool,
        Field(
            title="Whether the row is selected by default",
            examples=[True],
            description=(
                "Initial selection suggested by the preview; duplicate warnings can clear it."
            ),
        ),
    ]
    issues: Annotated[
        list[QueuedQuestionsImportPreviewIssueResponseSchema],
        Field(title="Validation errors and duplicate warnings"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: QuestionQueueImportPreviewRow,
    ) -> Self:
        return cls(
            row_number=schema.row_number,
            question=schema.question,
            sheet=schema.sheet,
            grade=schema.grade,
            can_import=schema.can_import,
            selected_by_default=schema.selected_by_default,
            issues=[
                QueuedQuestionsImportPreviewIssueResponseSchema.from_domain_schema(schema=issue)
                for issue in schema.issues
            ],
        )


class QueuedQuestionsImportPreviewResponseSchema(CamelCaseSchema):
    rows: Annotated[
        list[QueuedQuestionsImportPreviewRowResponseSchema],
        Field(title="Import preview rows"),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: QuestionQueueImportPreview) -> Self:
        return cls(
            rows=[
                QueuedQuestionsImportPreviewRowResponseSchema.from_domain_schema(schema=row)
                for row in schema.rows
            ],
        )


class ResourceResponseSchema(CamelCaseSchema):
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
            examples=["Python asyncio documentation"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]
    url: Annotated[
        str,
        Field(
            title="URL",
            examples=["https://docs.python.org/3/library/asyncio-task.html#asyncio.gather"],
        ),
    ]
    translations: Annotated[ResourceTranslationsSchema, Field(title="Translations")]

    @classmethod
    def from_domain_schema(cls, *, schema: ExternalResource, language: LanguageEnum) -> Self:
        return cls(
            id=schema.id,
            name=schema.localized_name(language=language),
            url=schema.url,
            translations=ResourceTranslationsSchema(
                ru=ResourceTranslationSchema(name=schema.name_ru),
                en=ResourceTranslationSchema(name=schema.name_en),
            ),
        )


class ResourceRequestSchema(CamelCaseSchema):
    url: Annotated[
        RequiredHttpUrlString,
        Field(
            title="URL",
            examples=["https://docs.python.org/3/library/asyncio-task.html#asyncio.gather"],
        ),
    ]
    translations: Annotated[ResourceTranslationsSchema, Field(title="Translations")]

    def to_schema(self, resource_id: str) -> ExternalResource:
        return ExternalResource(
            id=resource_id,
            name_ru=self.translations.ru.name,
            name_en=self.translations.en.name,
            url=self.url,
        )


class AttachmentContextTranslationSchema(CamelCaseSchema):
    context: Annotated[
        MatrixLongText,
        Field(
            title="Context",
            examples=["Read the section about concurrent task execution."],
            description="Why this external resource is relevant to the question.",
        ),
    ]


class AttachmentContextTranslationsSchema(CamelCaseSchema):
    ru: Annotated[AttachmentContextTranslationSchema, Field(title="Russian translation")]
    en: Annotated[AttachmentContextTranslationSchema, Field(title="English translation")]


class AttachedResourceTranslationSchema(CamelCaseSchema):
    name: Annotated[
        str,
        Field(
            title="Name",
            examples=["Python asyncio documentation"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]
    context: Annotated[
        str,
        Field(
            title="Context",
            examples=["Read the section about concurrent task execution."],
            description="Why this external resource is relevant to the question.",
        ),
    ]


class AttachedResourceTranslationsSchema(CamelCaseSchema):
    ru: Annotated[AttachedResourceTranslationSchema, Field(title="Russian translation")]
    en: Annotated[AttachedResourceTranslationSchema, Field(title="English translation")]


class AttachedResourceResponseSchema(CamelCaseSchema):
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
            examples=["Python asyncio documentation"],
            description="Display name in the selected language, or in this explicit translation.",
        ),
    ]
    url: Annotated[
        str,
        Field(
            title="URL",
            examples=["https://docs.python.org/3/library/asyncio-task.html#asyncio.gather"],
        ),
    ]
    context: Annotated[
        str,
        Field(
            title="Context",
            examples=["Read the section about concurrent task execution."],
            description="Why this external resource is relevant to the question.",
        ),
    ]
    translations: Annotated[AttachedResourceTranslationsSchema, Field(title="Translations")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: AttachedExternalResource,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            id=schema.id,
            name=schema.localized_name(language=language),
            url=schema.url,
            context=schema.localized_context(language=language),
            translations=AttachedResourceTranslationsSchema(
                ru=AttachedResourceTranslationSchema(
                    name=schema.name_ru,
                    context=schema.context_ru,
                ),
                en=AttachedResourceTranslationSchema(
                    name=schema.name_en,
                    context=schema.context_en,
                ),
            ),
        )


class ExistingResourceAttachmentRequestSchema(CamelCaseSchema):
    resource_id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Identifier of an existing external resource to attach.",
        ),
    ]
    translations: Annotated[AttachmentContextTranslationsSchema, Field(title="Translations")]

    def to_schema(self) -> ExistingExternalResourceAttachment:
        return ExistingExternalResourceAttachment(
            resource_id=self.resource_id,
            context_ru=self.translations.ru.context,
            context_en=self.translations.en.context,
        )


class NewResourceAttachmentRequestSchema(CamelCaseSchema):
    resource: Annotated[
        ResourceRequestSchema,
        Field(title="Resource"),
    ]
    translations: Annotated[AttachmentContextTranslationsSchema, Field(title="Translations")]

    def to_schema(self, resource_id: str) -> NewExternalResourceAttachment:
        return NewExternalResourceAttachment(
            resource=self.resource.to_schema(resource_id=resource_id),
            context_ru=self.translations.ru.context,
            context_en=self.translations.en.context,
        )


class CompetencyMatrixItemTranslationSchema(CamelCaseSchema):
    question: Annotated[
        RequiredShortText,
        Field(
            title="Question",
            examples=["How does asyncio.gather handle concurrent awaitables?"],
            description="Question text in the selected language, or in this explicit translation.",
        ),
    ]
    answer: Annotated[
        MatrixLongText,
        Field(
            title="Answer",
            examples=[
                (
                    "`asyncio.gather()` schedules awaitables concurrently and returns "
                    "results in input order."
                )
            ],
            description=(
                "Markdown answer in the selected language, or in this explicit translation."
            ),
        ),
    ]
    interview_answer_explanation: Annotated[
        MatrixLongText,
        Field(
            title="Interview answer explanation",
            examples=["Explain result ordering and how return_exceptions changes error handling."],
            description="Guidance on what an interview answer should explain.",
        ),
    ]


class CompetencyMatrixItemTranslationsSchema(CamelCaseSchema):
    ru: Annotated[CompetencyMatrixItemTranslationSchema, Field(title="Russian translation")]
    en: Annotated[CompetencyMatrixItemTranslationSchema, Field(title="English translation")]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixItem) -> Self:
        return cls(
            ru=CompetencyMatrixItemTranslationSchema(
                question=schema.question_ru,
                answer=schema.answer_ru,
                interview_answer_explanation=schema.interview_answer_explanation_ru,
            ),
            en=CompetencyMatrixItemTranslationSchema(
                question=schema.question_en,
                answer=schema.answer_en,
                interview_answer_explanation=schema.interview_answer_explanation_en,
            ),
        )


class PublicCompetencyMatrixItemResponseSchema(CamelCaseSchema):
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["python-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    question: Annotated[
        str,
        Field(
            title="Question",
            examples=["How does asyncio.gather handle concurrent awaitables?"],
            description="Question text in the selected language, or in this explicit translation.",
        ),
    ]
    interview_frequency: Annotated[
        InterviewFrequencyEnum | None,
        Field(
            title="Interview frequency",
            examples=["often"],
            description="How frequently this question appears in interviews.",
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixItem, language: LanguageEnum) -> Self:
        return cls(
            slug=schema.slug,
            question=schema.localized_question(language=language),
            interview_frequency=schema.interview_frequency,
        )


class CompetencyMatrixItemResponseSchema(PublicCompetencyMatrixItemResponseSchema):
    id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixItem, language: LanguageEnum) -> Self:
        summary = PublicCompetencyMatrixItemResponseSchema.from_domain_schema(
            schema=schema,
            language=language,
        )
        return cls(
            **summary.model_dump(),
            id=str(schema.id),
        )


class PublicCompetencyMatrixItemDetailResponseSchema(PublicCompetencyMatrixItemResponseSchema):
    answer: Annotated[
        str,
        Field(
            title="Answer",
            examples=[
                (
                    "`asyncio.gather()` schedules awaitables concurrently and returns "
                    "results in input order."
                )
            ],
            description=(
                "Markdown answer in the selected language, or in this explicit translation."
            ),
        ),
    ]
    interview_answer_explanation: Annotated[
        str,
        Field(
            title="Interview answer explanation",
            examples=["Explain result ordering and how return_exceptions changes error handling."],
            description="Guidance on what an interview answer should explain.",
        ),
    ]
    sheet_key: Annotated[
        str,
        Field(
            title="Sheet key",
            examples=["python"],
            description="Stable language-neutral sheet key, independent of the selected language.",
        ),
    ]
    sheet: Annotated[
        str,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    section: Annotated[str, Field(title="Section", examples=["Concurrency"])]
    subsection: Annotated[str, Field(title="Subsection", examples=["Async IO"])]
    publish_status: Annotated[
        PublishStatusEnum,
        Field(
            title="Publication status",
            examples=["Draft"],
            description="Publication state. Published content must satisfy publication validation.",
        ),
    ]
    resources: Annotated[list[AttachedResourceResponseSchema], Field(title="Resources")]
    translations: Annotated[CompetencyMatrixItemTranslationsSchema, Field(title="Translations")]
    suggested_by_username: Annotated[str, Field(title="Suggested by", examples=["reader42"])]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixItem,
        language: LanguageEnum,
    ) -> Self:
        summary = PublicCompetencyMatrixItemResponseSchema.from_domain_schema(
            schema=schema,
            language=language,
        )
        return cls(
            **summary.model_dump(),
            answer=schema.localized_answer(language=language),
            interview_answer_explanation=schema.localized_interview_answer_explanation(
                language=language,
            ),
            sheet_key=schema.sheet_key,
            sheet=schema.localized_sheet(language=language),
            grade=schema.grade,
            section=schema.localized_section(language=language),
            subsection=schema.localized_subsection(language=language),
            publish_status=schema.publish_status,
            suggested_by_username=schema.suggested_by_username,
            resources=[
                AttachedResourceResponseSchema.from_domain_schema(
                    schema=resource,
                    language=language,
                )
                for resource in schema.resources
            ],
            translations=CompetencyMatrixItemTranslationsSchema.from_domain_schema(schema=schema),
        )


class CompetencyMatrixItemDetailResponseSchema(CompetencyMatrixItemResponseSchema):
    answer: Annotated[
        str,
        Field(
            title="Answer",
            examples=[
                (
                    "`asyncio.gather()` schedules awaitables concurrently and returns "
                    "results in input order."
                )
            ],
            description=(
                "Markdown answer in the selected language, or in this explicit translation."
            ),
        ),
    ]
    interview_answer_explanation: Annotated[
        str,
        Field(
            title="Interview answer explanation",
            examples=["Explain result ordering and how return_exceptions changes error handling."],
            description="Guidance on what an interview answer should explain.",
        ),
    ]
    subsection_id: Annotated[
        str,
        Field(
            title="Subsection identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description=(
                "Identifier of the existing matrix subsection to which the question belongs."
            ),
        ),
    ]
    sheet_key: Annotated[
        str,
        Field(
            title="Sheet key",
            examples=["python"],
            description="Stable language-neutral sheet key, independent of the selected language.",
        ),
    ]
    sheet: Annotated[
        str,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    section: Annotated[str, Field(title="Section", examples=["Concurrency"])]
    subsection: Annotated[str, Field(title="Subsection", examples=["Async IO"])]
    publish_status: Annotated[
        PublishStatusEnum,
        Field(
            title="Publication status",
            examples=["Draft"],
            description="Publication state. Published content must satisfy publication validation.",
        ),
    ]
    resources: Annotated[list[AttachedResourceResponseSchema], Field(title="Resources")]
    translations: Annotated[CompetencyMatrixItemTranslationsSchema, Field(title="Translations")]
    suggested_by_username: Annotated[str, Field(title="Suggested by", examples=["reader42"])]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: CompetencyMatrixItem,
        language: LanguageEnum,
    ) -> Self:
        summary = CompetencyMatrixItemResponseSchema.from_domain_schema(
            schema=schema,
            language=language,
        )
        return cls(
            **summary.model_dump(),
            answer=schema.localized_answer(language=language),
            interview_answer_explanation=schema.localized_interview_answer_explanation(
                language=language,
            ),
            subsection_id=schema.subsection_id,
            sheet_key=schema.sheet_key,
            sheet=schema.localized_sheet(language=language),
            grade=schema.grade,
            section=schema.localized_section(language=language),
            subsection=schema.localized_subsection(language=language),
            publish_status=schema.publish_status,
            suggested_by_username=schema.suggested_by_username,
            resources=[
                AttachedResourceResponseSchema.from_domain_schema(
                    schema=resource,
                    language=language,
                )
                for resource in schema.resources
            ],
            translations=CompetencyMatrixItemTranslationsSchema.from_domain_schema(schema=schema),
        )


class CompetencyMatrixItemRequestSchema(CamelCaseSchema):
    slug: Annotated[
        SlugString,
        Field(
            title="Slug",
            examples=["python-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    subsection_id: Annotated[
        str,
        Field(
            title="Subsection identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description=(
                "Identifier of the existing matrix subsection to which the question belongs."
            ),
        ),
    ]
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    interview_frequency: Annotated[
        InterviewFrequencyEnum | None,
        Field(
            title="Interview frequency",
            examples=["often"],
            description="How frequently this question appears in interviews.",
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
    translations: Annotated[CompetencyMatrixItemTranslationsSchema, Field(title="Translations")]
    resources: Annotated[
        list[ExistingResourceAttachmentRequestSchema | NewResourceAttachmentRequestSchema],
        Field(title="Resources"),
    ]

    def to_create_schema(
        self,
        item_id_generator: HexUuidIdGenerator,
        resource_id_generator: HexUuidIdGenerator,
    ) -> CompetencyMatrixItemCreateParams:
        return CompetencyMatrixItemCreateParams(
            id=item_id_generator.get_next(),
            slug=self.slug,
            question_ru=self.translations.ru.question,
            question_en=self.translations.en.question,
            answer_ru=self.translations.ru.answer,
            answer_en=self.translations.en.answer,
            interview_answer_explanation_ru=self.translations.ru.interview_answer_explanation,
            interview_answer_explanation_en=self.translations.en.interview_answer_explanation,
            subsection_id=self.subsection_id,
            grade=self.grade,
            interview_frequency=self.interview_frequency,
            publish_status=self.publish_status,
            resources=self._to_resource_attachments(resource_id_generator=resource_id_generator),
        )

    def to_create_from_queue_schema(
        self,
        queued_question_id: str,
        item_id_generator: HexUuidIdGenerator,
        resource_id_generator: HexUuidIdGenerator,
    ) -> QueuedCompetencyMatrixQuestionCreateItemParams:
        return QueuedCompetencyMatrixQuestionCreateItemParams(
            queued_question_id=queued_question_id,
            item=self.to_create_schema(
                item_id_generator=item_id_generator,
                resource_id_generator=resource_id_generator,
            ),
        )

    def to_update_schema(
        self,
        item_id: str,
        resource_id_generator: HexUuidIdGenerator,
    ) -> CompetencyMatrixItemUpdateParams:
        return CompetencyMatrixItemUpdateParams(
            id=item_id,
            slug=self.slug,
            question_ru=self.translations.ru.question,
            question_en=self.translations.en.question,
            answer_ru=self.translations.ru.answer,
            answer_en=self.translations.en.answer,
            interview_answer_explanation_ru=self.translations.ru.interview_answer_explanation,
            interview_answer_explanation_en=self.translations.en.interview_answer_explanation,
            subsection_id=self.subsection_id,
            grade=self.grade,
            interview_frequency=self.interview_frequency,
            publish_status=self.publish_status,
            resources=self._to_resource_attachments(resource_id_generator=resource_id_generator),
        )

    def _to_resource_attachments(
        self,
        resource_id_generator: HexUuidIdGenerator,
    ) -> list[ExistingExternalResourceAttachment | NewExternalResourceAttachment]:
        return [
            resource.to_schema()
            if isinstance(resource, ExistingResourceAttachmentRequestSchema)
            else resource.to_schema(resource_id=resource_id_generator.get_next())
            for resource in self.resources
        ]


class CompetencyMatrixGroupedGradesResponseSchema(CamelCaseSchema):
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    items: Annotated[list[CompetencyMatrixItemResponseSchema], Field(title="List")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        grade: GradeEnum | None,
        items: Iterable[CompetencyMatrixItem],
        language: LanguageEnum,
    ) -> Self:
        return cls(
            grade=grade,
            items=[
                CompetencyMatrixItemResponseSchema.from_domain_schema(
                    schema=item,
                    language=language,
                )
                for item in items
            ],
        )


class CompetencyMatrixGroupedSubsectionsResponseSchema(CamelCaseSchema):
    subsection: Annotated[str, Field(title="Subsection", examples=["Async IO"])]
    grades: Annotated[
        list[CompetencyMatrixGroupedGradesResponseSchema],
        Field(title="List"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        subsection: str,
        items: Iterable[CompetencyMatrixItem],
        language: LanguageEnum,
    ) -> Self:
        return cls(
            subsection=subsection,
            grades=[
                CompetencyMatrixGroupedGradesResponseSchema.from_domain_schema(
                    grade=grade,
                    items=list(grade_items),
                    language=language,
                )
                for grade, grade_items in groupby(items, key=lambda item: item.grade)
            ],
        )


class CompetencyMatrixGroupedSectionsResponseSchema(CamelCaseSchema):
    section: Annotated[str, Field(title="Section", examples=["Concurrency"])]
    subsections: Annotated[
        list[CompetencyMatrixGroupedSubsectionsResponseSchema],
        Field(title="List"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        section: str,
        items: Iterable[CompetencyMatrixItem],
        language: LanguageEnum,
    ) -> Self:
        return cls(
            section=section,
            subsections=[
                CompetencyMatrixGroupedSubsectionsResponseSchema.from_domain_schema(
                    subsection=subsection,
                    items=list(subsection_items),
                    language=language,
                )
                for subsection, subsection_items in groupby(
                    items,
                    key=lambda item: item.localized_subsection(language=language),
                )
            ],
        )


class CompetencyMatrixItemsListResponseSchema(CamelCaseSchema):
    sheet_key: Annotated[
        str,
        Field(
            title="Sheet key",
            examples=["python"],
            description="Stable language-neutral sheet key, independent of the selected language.",
        ),
    ]
    sheet: Annotated[
        str,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    sections: Annotated[
        list[CompetencyMatrixGroupedSectionsResponseSchema],
        Field(title="List"),
    ]

    @classmethod
    def empty(cls, *, sheet_key: str) -> Self:
        return cls(sheet_key=sheet_key, sheet="", sections=[])

    @classmethod
    def from_domain_schema(
        cls,
        *,
        sheet_key: str,
        schema: CompetencyMatrixItems,
        language: LanguageEnum,
    ) -> Self:
        items = [item for item in schema.values if item.sheet_key == sheet_key]
        if not items:
            return cls.empty(sheet_key=sheet_key)
        sections = [
            CompetencyMatrixGroupedSectionsResponseSchema.from_domain_schema(
                section=section,
                items=list(section_items),
                language=language,
            )
            for section, section_items in groupby(
                items,
                key=lambda item: item.localized_section(language=language),
            )
        ]
        return cls(
            sheet_key=sheet_key,
            sheet=items[0].localized_sheet(language=language),
            sections=sections,
        )


class PublicCompetencyMatrixGroupedGradesResponseSchema(CamelCaseSchema):
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    items: Annotated[list[PublicCompetencyMatrixItemResponseSchema], Field(title="List")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        grade: GradeEnum | None,
        items: Iterable[CompetencyMatrixItem],
        language: LanguageEnum,
    ) -> Self:
        return cls(
            grade=grade,
            items=[
                PublicCompetencyMatrixItemResponseSchema.from_domain_schema(
                    schema=item,
                    language=language,
                )
                for item in items
            ],
        )


class PublicCompetencyMatrixGroupedSubsectionsResponseSchema(CamelCaseSchema):
    subsection: Annotated[str, Field(title="Subsection", examples=["Async IO"])]
    grades: Annotated[
        list[PublicCompetencyMatrixGroupedGradesResponseSchema],
        Field(title="List"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        subsection: str,
        items: Iterable[CompetencyMatrixItem],
        language: LanguageEnum,
    ) -> Self:
        return cls(
            subsection=subsection,
            grades=[
                PublicCompetencyMatrixGroupedGradesResponseSchema.from_domain_schema(
                    grade=grade,
                    items=list(grade_items),
                    language=language,
                )
                for grade, grade_items in groupby(items, key=lambda item: item.grade)
            ],
        )


class PublicCompetencyMatrixGroupedSectionsResponseSchema(CamelCaseSchema):
    section: Annotated[str, Field(title="Section", examples=["Concurrency"])]
    subsections: Annotated[
        list[PublicCompetencyMatrixGroupedSubsectionsResponseSchema],
        Field(title="List"),
    ]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        section: str,
        items: Iterable[CompetencyMatrixItem],
        language: LanguageEnum,
    ) -> Self:
        return cls(
            section=section,
            subsections=[
                PublicCompetencyMatrixGroupedSubsectionsResponseSchema.from_domain_schema(
                    subsection=subsection,
                    items=list(subsection_items),
                    language=language,
                )
                for subsection, subsection_items in groupby(
                    items,
                    key=lambda item: item.localized_subsection(language=language),
                )
            ],
        )


class PublicCompetencyMatrixItemsListResponseSchema(CamelCaseSchema):
    sheet_key: Annotated[
        str,
        Field(
            title="Sheet key",
            examples=["python"],
            description="Stable language-neutral sheet key, independent of the selected language.",
        ),
    ]
    sheet: Annotated[
        str,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    sections: Annotated[
        list[PublicCompetencyMatrixGroupedSectionsResponseSchema],
        Field(title="List"),
    ]

    @classmethod
    def empty(cls, *, sheet_key: str) -> Self:
        return cls(sheet_key=sheet_key, sheet="", sections=[])

    @classmethod
    def from_domain_schema(
        cls,
        *,
        sheet_key: str,
        schema: CompetencyMatrixItems,
        language: LanguageEnum,
    ) -> Self:
        items = [item for item in schema.values if item.sheet_key == sheet_key]
        if not items:
            return cls.empty(sheet_key=sheet_key)
        sections = [
            PublicCompetencyMatrixGroupedSectionsResponseSchema.from_domain_schema(
                section=section,
                items=list(section_items),
                language=language,
            )
            for section, section_items in groupby(
                items,
                key=lambda item: item.localized_section(language=language),
            )
        ]
        return cls(
            sheet_key=sheet_key,
            sheet=items[0].localized_sheet(language=language),
            sections=sections,
        )


class SheetResponseSchema(CamelCaseSchema):
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

    @classmethod
    def from_domain_schema(cls, *, schema: Sheet, language: LanguageEnum) -> Self:
        return cls(key=schema.key, name=schema.localized_name(language=language))


class CompetencyMatrixSheetsListResponseSchema(CamelCaseSchema):
    sheets: Annotated[list[SheetResponseSchema], Field(title="List")]

    @classmethod
    def from_domain_schema(cls, *, schema: Sheets, language: LanguageEnum) -> Self:
        return cls(
            sheets=[
                SheetResponseSchema.from_domain_schema(schema=sheet, language=language)
                for sheet in schema
            ],
        )


class CompetencyMatrixResourcesResponseSchema(CamelCaseSchema):
    resources: Annotated[list[ResourceResponseSchema], Field(title="Resources")]

    @classmethod
    def from_domain_schema(
        cls,
        *,
        schema: ExternalResources,
        language: LanguageEnum,
    ) -> Self:
        return cls(
            resources=[
                ResourceResponseSchema.from_domain_schema(schema=resource, language=language)
                for resource in schema
            ],
        )


class CompetencyMatrixWorkspaceSummaryResponseSchema(CamelCaseSchema):
    total: Annotated[int, Field(title="Total", examples=[42])]
    draft: Annotated[int, Field(title="Draft", examples=[12])]
    missing_draft: Annotated[int, Field(title="Draft items with missing fields", examples=[4])]
    dangerous_published: Annotated[
        int, Field(title="Published items with missing fields", examples=[1])
    ]
    ready_published: Annotated[int, Field(title="Ready published items", examples=[29])]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixWorkspaceSummary) -> Self:
        return cls(
            total=schema.total,
            draft=schema.draft,
            missing_draft=schema.missing_draft,
            dangerous_published=schema.dangerous_published,
            ready_published=schema.ready_published,
        )


class CompetencyMatrixWorkspaceItemResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Identifier",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    slug: Annotated[
        str,
        Field(
            title="Slug",
            examples=["python-asyncio-gather"],
            description="Stable URL slug; lowercase words separated by hyphens.",
        ),
    ]
    question: Annotated[
        str,
        Field(
            title="Question",
            examples=["How does asyncio.gather handle concurrent awaitables?"],
            description="Question text in the selected language, or in this explicit translation.",
        ),
    ]
    sheet_key: Annotated[
        str,
        Field(
            title="Sheet key",
            examples=["python"],
            description="Stable language-neutral sheet key, independent of the selected language.",
        ),
    ]
    sheet: Annotated[
        str,
        Field(
            title="Sheet",
            examples=["Python"],
            description="Sheet display name, or the sheet value read from an imported row.",
        ),
    ]
    grade: Annotated[
        GradeEnum | None,
        Field(
            title="Grade",
            examples=["Middle"],
            description="Competency grade; null means the grade has not been assigned.",
        ),
    ]
    interview_frequency: Annotated[
        InterviewFrequencyEnum | None,
        Field(
            title="Interview frequency",
            examples=["often"],
            description="How frequently this question appears in interviews.",
        ),
    ]
    section: Annotated[str, Field(title="Section", examples=["Concurrency"])]
    subsection: Annotated[str, Field(title="Subsection", examples=["Async IO"])]
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
    missing_fields: Annotated[
        list[CompetencyMatrixMissingFieldEnum],
        Field(
            title="Missing fields",
            examples=[["answerEn"]],
            description="Publication requirements that are currently incomplete.",
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixWorkspaceItem) -> Self:
        return cls(
            id=str(schema.id),
            slug=schema.slug,
            question=schema.question,
            sheet_key=schema.sheet_key,
            sheet=schema.sheet,
            grade=schema.grade,
            interview_frequency=schema.interview_frequency,
            section=schema.section,
            subsection=schema.subsection,
            publish_status=schema.publish_status,
            published_at=schema.published_at.isoformat()
            if schema.published_at is not None
            else None,
            missing_fields=list(schema.missing_fields),
        )


class CompetencyMatrixWorkspaceResponseSchema(CamelCaseSchema):
    total_count: Annotated[
        int,
        Field(
            title="Question count",
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
    summary: Annotated[CompetencyMatrixWorkspaceSummaryResponseSchema, Field(title="Summary")]
    items: Annotated[list[CompetencyMatrixWorkspaceItemResponseSchema], Field(title="Questions")]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixWorkspace) -> Self:
        return cls(
            total_count=schema.total_count,
            total_pages=schema.total_pages,
            summary=CompetencyMatrixWorkspaceSummaryResponseSchema.from_domain_schema(
                schema=schema.summary,
            ),
            items=[
                CompetencyMatrixWorkspaceItemResponseSchema.from_domain_schema(schema=item)
                for item in schema
            ],
        )


class CompetencyMatrixFilterOptionResponseSchema(CamelCaseSchema):
    key: Annotated[
        str,
        Field(
            title="Key",
            examples=["python"],
            description="Stable language-neutral key used to reference this structure node.",
        ),
    ]
    label: Annotated[str, Field(title="Label", examples=["Python"])]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixFilterOption) -> Self:
        return cls(key=schema.key, label=schema.label)


class CompetencyMatrixFilterSubsectionOptionResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Subsection ID",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    label: Annotated[str, Field(title="Subsection", examples=["Python"])]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixFilterSubsectionOption) -> Self:
        return cls(id=schema.id, label=schema.label)


class CompetencyMatrixFilterSectionOptionResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="Section ID",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    label: Annotated[str, Field(title="Section", examples=["Python"])]
    subsections: Annotated[
        list[CompetencyMatrixFilterSubsectionOptionResponseSchema],
        Field(title="Subsections"),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixFilterSectionOption) -> Self:
        return cls(
            id=schema.id,
            label=schema.label,
            subsections=[
                CompetencyMatrixFilterSubsectionOptionResponseSchema.from_domain_schema(
                    schema=subsection,
                )
                for subsection in schema.subsections
            ],
        )


class CompetencyMatrixFilterSheetOptionResponseSchema(CamelCaseSchema):
    key: Annotated[
        str,
        Field(
            title="Key",
            examples=["python"],
            description="Stable language-neutral key used to reference this structure node.",
        ),
    ]
    label: Annotated[str, Field(title="Label", examples=["Python"])]
    sections: Annotated[
        list[CompetencyMatrixFilterSectionOptionResponseSchema],
        Field(title="Sections"),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixFilterSheetOption) -> Self:
        return cls(
            key=schema.key,
            label=schema.label,
            sections=[
                CompetencyMatrixFilterSectionOptionResponseSchema.from_domain_schema(
                    schema=section,
                )
                for section in schema.sections
            ],
        )


class CompetencyMatrixFilterOptionsResponseSchema(CamelCaseSchema):
    sheets: Annotated[list[CompetencyMatrixFilterSheetOptionResponseSchema], Field(title="Sheets")]
    grades: Annotated[list[GradeEnum], Field(title="Grades", examples=[["Middle", "Senior"]])]
    interview_frequencies: Annotated[
        list[InterviewFrequencyEnum],
        Field(title="Interview frequencies", examples=[["often"]]),
    ]
    sections: Annotated[list[str], Field(title="Sections", examples=[["Concurrency"]])]
    subsections: Annotated[list[str], Field(title="Subsections", examples=[["Async IO"]])]
    publish_statuses: Annotated[
        list[PublishStatusEnum],
        Field(title="Publication statuses", examples=[["Draft", "Published"]]),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: CompetencyMatrixFilterOptions) -> Self:
        return cls(
            sheets=[
                CompetencyMatrixFilterSheetOptionResponseSchema.from_domain_schema(schema=sheet)
                for sheet in schema.sheets
            ],
            grades=schema.grades,
            interview_frequencies=schema.interview_frequencies,
            sections=schema.sections,
            subsections=schema.subsections,
            publish_statuses=schema.publish_statuses,
        )
