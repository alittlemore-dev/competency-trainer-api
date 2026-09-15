import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from core.account.schemas import ManagedAccount, ManagedAccounts
from core.articles.schemas import (
    Article,
    ArticleFolder,
    ArticleFolders,
    ArticleMetadata,
    ArticleReactionCounts,
    Articles,
    Tag,
    Tags,
)
from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser, User
from core.auth.types import Token
from core.competency_matrix.enums import GradeEnum, InterviewFrequencyEnum
from core.competency_matrix.schemas import (
    AttachedExternalResource,
    AttachedExternalResources,
    CompetencyMatrixItem,
    CompetencyMatrixItemCreateParams,
    CompetencyMatrixItems,
    CompetencyMatrixItemStructure,
    CompetencyMatrixItemUpdateParams,
    ExistingExternalResourceAttachment,
    ExternalResource,
    ExternalResources,
    MatrixQuestionClaimSummary,
    NewExternalResourceAttachment,
    QueuedCompetencyMatrixQuestion,
    QueuedCompetencyMatrixQuestionCreateParams,
    QueuedCompetencyMatrixQuestions,
    Sheet,
    Sheets,
)
from core.contacts.schemas import ContactMe
from core.enums import PublishStatusEnum
from core.files.enums import FilePurpose
from core.files.schemas import (
    FileRead,
    StoredFile,
)
from core.files.types import Namespace
from core.schemas import Secret
from core.types import SearchName


class CoreFactoryHelper:
    @classmethod
    def hex_id(cls, value: int | str = 1) -> str:
        if isinstance(value, str):
            return value
        return f"{value % (1 << 128):032x}"

    @classmethod
    def hex_id_from_text(cls, value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()[:32]

    @staticmethod
    def _fallback(value: str | None, fallback: str) -> str:
        return value if value is not None else fallback

    @classmethod
    def external_resource(
        cls,
        resource_id: Any,
        name: str = "RESOURCE",
        name_ru: str | None = None,
        name_en: str | None = None,
        url: str = "https://example.com",
    ) -> ExternalResource:
        return ExternalResource(
            id=cls.hex_id(resource_id) if isinstance(resource_id, int) else resource_id,
            name_ru=name_ru or name,
            name_en=name_en or name,
            url=url,
        )

    @classmethod
    def external_resources(
        cls,
        values: list[ExternalResource] | None = None,
    ) -> ExternalResources:
        return ExternalResources(values=values or [])

    @classmethod
    def attached_external_resource(
        cls,
        resource_id: Any,
        name: str = "RESOURCE",
        name_ru: str | None = None,
        name_en: str | None = None,
        url: str = "https://example.com",
        context: str = "Context",
        context_ru: str | None = None,
        context_en: str | None = None,
    ) -> AttachedExternalResource:
        return AttachedExternalResource(
            id=cls.hex_id(resource_id) if isinstance(resource_id, int) else resource_id,
            name_ru=name_ru or name,
            name_en=name_en or name,
            url=url,
            context_ru=context_ru or context,
            context_en=context_en or context,
        )

    @classmethod
    def attached_external_resources(
        cls,
        values: list[AttachedExternalResource] | None = None,
    ) -> AttachedExternalResources:
        return AttachedExternalResources(values=values or [])

    @classmethod
    def existing_external_resource_attachment(
        cls,
        resource_id: Any,
        context: str = "Context",
        context_ru: str | None = None,
        context_en: str | None = None,
    ) -> ExistingExternalResourceAttachment:
        return ExistingExternalResourceAttachment(
            resource_id=cls.hex_id(resource_id) if isinstance(resource_id, int) else resource_id,
            context_ru=context_ru or context,
            context_en=context_en or context,
        )

    @classmethod
    def new_external_resource_attachment(
        cls,
        resource_id: Any,
        name: str = "RESOURCE",
        name_ru: str | None = None,
        name_en: str | None = None,
        url: str = "https://example.com",
        context: str = "Context",
        context_ru: str | None = None,
        context_en: str | None = None,
    ) -> NewExternalResourceAttachment:
        return NewExternalResourceAttachment(
            resource=cls.external_resource(
                resource_id=resource_id,
                name=name,
                name_ru=name_ru,
                name_en=name_en,
                url=url,
            ),
            context_ru=context_ru or context,
            context_en=context_en or context,
        )

    @classmethod
    def competency_matrix_item(
        cls,
        item_id: int | str,
        sheet_id: int | str = 1,
        section_id: int | str = 1,
        subsection_id: int | str = 1,
        slug: str | None = None,
        published_at: str | None = None,
        question: str = "QUESTION",
        question_ru: str | None = None,
        question_en: str | None = None,
        publish_status: PublishStatusEnum = PublishStatusEnum.PUBLISHED,
        answer: str = "Answer",
        answer_ru: str | None = None,
        answer_en: str | None = None,
        interview_answer_explanation: str = "Answer",
        interview_answer_explanation_ru: str | None = None,
        interview_answer_explanation_en: str | None = None,
        sheet_key: str | None = None,
        sheet: str = "Sheet",
        sheet_ru: str | None = None,
        sheet_en: str | None = None,
        grade: GradeEnum | None = GradeEnum.JUNIOR,
        interview_frequency: InterviewFrequencyEnum | None = InterviewFrequencyEnum.OFTEN,
        section: str = "Section",
        section_ru: str | None = None,
        section_en: str | None = None,
        subsection: str = "Subsection",
        subsection_ru: str | None = None,
        subsection_en: str | None = None,
        resources: list[AttachedExternalResource] | None = None,
        suggested_by_username: str = "owner",
    ) -> CompetencyMatrixItem:
        question_en_value = cls._fallback(question_en, question)
        return CompetencyMatrixItem(
            id=cls.hex_id(item_id),
            slug=cls._fallback(slug, slugify(question_en_value)),
            question_ru=cls._fallback(question_ru, question),
            question_en=question_en_value,
            publish_status=publish_status,
            published_at=(
                datetime.fromisoformat(published_at).replace(tzinfo=UTC)
                if published_at is not None
                else None
            ),
            answer_ru=cls._fallback(answer_ru, answer),
            answer_en=cls._fallback(answer_en, answer),
            interview_answer_explanation_ru=cls._fallback(
                interview_answer_explanation_ru,
                interview_answer_explanation,
            ),
            interview_answer_explanation_en=cls._fallback(
                interview_answer_explanation_en,
                interview_answer_explanation,
            ),
            structure=cls.competency_matrix_item_structure(
                sheet_id=sheet_id,
                section_id=section_id,
                subsection_id=subsection_id,
                sheet_key=cls._fallback(sheet_key, sheet.lower().replace(" ", "-")),
                sheet_ru=cls._fallback(sheet_ru, sheet),
                sheet_en=cls._fallback(sheet_en, sheet),
                section_ru=cls._fallback(section_ru, section),
                section_en=cls._fallback(section_en, section),
                subsection_ru=cls._fallback(subsection_ru, subsection),
                subsection_en=cls._fallback(subsection_en, subsection),
            ),
            grade=grade,
            interview_frequency=interview_frequency,
            suggested_by_username=suggested_by_username,
            resources=AttachedExternalResources(values=resources or []),
        )

    @classmethod
    def competency_matrix_item_structure(
        cls,
        subsection_id: int | str = 1,
        sheet_id: int | str = 1,
        sheet_key: str = "sheet",
        sheet_ru: str = "Sheet",
        sheet_en: str = "Sheet",
        section_id: int | str = 1,
        section_ru: str = "Section",
        section_en: str = "Section",
        subsection_ru: str = "Subsection",
        subsection_en: str = "Subsection",
    ) -> CompetencyMatrixItemStructure:
        return CompetencyMatrixItemStructure(
            sheet_id=cls.hex_id(sheet_id),
            sheet_key=sheet_key,
            sheet_ru=sheet_ru,
            sheet_en=sheet_en,
            section_id=cls.hex_id(section_id),
            section_ru=section_ru,
            section_en=section_en,
            subsection_id=cls.hex_id(subsection_id),
            subsection_ru=subsection_ru,
            subsection_en=subsection_en,
        )

    @classmethod
    def competency_matrix_item_create_params(
        cls,
        item_id: int | str,
        sheet_id: int | str = 1,
        section_id: int | str = 1,
        subsection_id: int | str = 1,
        slug: str | None = None,
        question: str = "QUESTION",
        question_ru: str | None = None,
        question_en: str | None = None,
        publish_status: PublishStatusEnum = PublishStatusEnum.PUBLISHED,
        answer: str = "Answer",
        answer_ru: str | None = None,
        answer_en: str | None = None,
        interview_answer_explanation: str = "Answer",
        interview_answer_explanation_ru: str | None = None,
        interview_answer_explanation_en: str | None = None,
        sheet_key: str | None = None,
        sheet: str = "Sheet",
        sheet_ru: str | None = None,
        sheet_en: str | None = None,
        grade: GradeEnum | None = GradeEnum.JUNIOR,
        interview_frequency: InterviewFrequencyEnum | None = InterviewFrequencyEnum.OFTEN,
        section: str = "Section",
        section_ru: str | None = None,
        section_en: str | None = None,
        subsection: str = "Subsection",
        subsection_ru: str | None = None,
        subsection_en: str | None = None,
        resources: (
            list[ExistingExternalResourceAttachment | NewExternalResourceAttachment] | None
        ) = None,
    ) -> CompetencyMatrixItemCreateParams:
        _ = (
            sheet_id,
            section_id,
            sheet_key,
            sheet,
            sheet_ru,
            sheet_en,
            section,
            section_ru,
            section_en,
            subsection,
            subsection_ru,
            subsection_en,
        )
        question_en_value = cls._fallback(question_en, question)
        return CompetencyMatrixItemCreateParams(
            id=cls.hex_id(item_id),
            slug=cls._fallback(slug, slugify(question_en_value)),
            question_ru=cls._fallback(question_ru, question),
            question_en=question_en_value,
            publish_status=publish_status,
            answer_ru=cls._fallback(answer_ru, answer),
            answer_en=cls._fallback(answer_en, answer),
            interview_answer_explanation_ru=cls._fallback(
                interview_answer_explanation_ru,
                interview_answer_explanation,
            ),
            interview_answer_explanation_en=cls._fallback(
                interview_answer_explanation_en,
                interview_answer_explanation,
            ),
            subsection_id=cls.hex_id(subsection_id),
            grade=grade,
            interview_frequency=interview_frequency,
            resources=resources or [],
        )

    @classmethod
    def competency_matrix_item_update_params(
        cls,
        item_id: int | str,
        sheet_id: int | str = 1,
        section_id: int | str = 1,
        subsection_id: int | str = 1,
        slug: str | None = None,
        question: str = "QUESTION",
        question_ru: str | None = None,
        question_en: str | None = None,
        publish_status: PublishStatusEnum = PublishStatusEnum.PUBLISHED,
        answer: str = "Answer",
        answer_ru: str | None = None,
        answer_en: str | None = None,
        interview_answer_explanation: str = "Answer",
        interview_answer_explanation_ru: str | None = None,
        interview_answer_explanation_en: str | None = None,
        sheet_key: str | None = None,
        sheet: str = "Sheet",
        sheet_ru: str | None = None,
        sheet_en: str | None = None,
        grade: GradeEnum | None = GradeEnum.JUNIOR,
        interview_frequency: InterviewFrequencyEnum | None = InterviewFrequencyEnum.OFTEN,
        section: str = "Section",
        section_ru: str | None = None,
        section_en: str | None = None,
        subsection: str = "Subsection",
        subsection_ru: str | None = None,
        subsection_en: str | None = None,
        resources: (
            list[ExistingExternalResourceAttachment | NewExternalResourceAttachment] | None
        ) = None,
    ) -> CompetencyMatrixItemUpdateParams:
        _ = (
            sheet_id,
            section_id,
            sheet_key,
            sheet,
            sheet_ru,
            sheet_en,
            section,
            section_ru,
            section_en,
            subsection,
            subsection_ru,
            subsection_en,
        )
        question_en_value = cls._fallback(question_en, question)
        return CompetencyMatrixItemUpdateParams(
            id=cls.hex_id(item_id),
            slug=cls._fallback(slug, slugify(question_en_value)),
            question_ru=cls._fallback(question_ru, question),
            question_en=question_en_value,
            publish_status=publish_status,
            answer_ru=cls._fallback(answer_ru, answer),
            answer_en=cls._fallback(answer_en, answer),
            interview_answer_explanation_ru=cls._fallback(
                interview_answer_explanation_ru,
                interview_answer_explanation,
            ),
            interview_answer_explanation_en=cls._fallback(
                interview_answer_explanation_en,
                interview_answer_explanation,
            ),
            subsection_id=cls.hex_id(subsection_id),
            grade=grade,
            interview_frequency=interview_frequency,
            resources=resources or [],
        )

    @classmethod
    def sheet(
        cls,
        key: str = "python",
        name: str = "Python",
        name_ru: str | None = None,
        name_en: str | None = None,
    ) -> Sheet:
        return Sheet(key=key, name_ru=name_ru or name, name_en=name_en or name)

    @classmethod
    def sheets(cls, values: list[Sheet] | list[str] | None = None) -> Sheets:
        if values is None:
            return Sheets(values=[])
        return Sheets(
            values=[
                cls.sheet(key=value.lower(), name=value) if isinstance(value, str) else value
                for value in values
            ],
        )

    @classmethod
    def queued_competency_matrix_question(
        cls,
        question_id: int | str,
        question: str = "What is PEP 8?",
        grade: GradeEnum | None = None,
        sheet: str | None = None,
        section: str | None = None,
        subsection: str | None = None,
        suggested_by_username: str = "anon",
        created_at: datetime | None = None,
        claim: MatrixQuestionClaimSummary | None = None,
    ) -> QueuedCompetencyMatrixQuestion:
        return QueuedCompetencyMatrixQuestion(
            id=cls.hex_id(question_id),
            question=question,
            grade=grade,
            sheet=sheet,
            section=section,
            subsection=subsection,
            suggested_by_username=suggested_by_username,
            created_at=created_at or datetime.now(tz=UTC),
            claim=claim,
        )

    @classmethod
    def queued_competency_matrix_questions(
        cls,
        values: list[QueuedCompetencyMatrixQuestion] | None = None,
    ) -> QueuedCompetencyMatrixQuestions:
        return QueuedCompetencyMatrixQuestions(values=values or [])

    @classmethod
    def queued_competency_matrix_question_create_params(
        cls,
        question: str = "What is PEP 8?",
        grade: GradeEnum | None = None,
        sheet: str | None = None,
    ) -> QueuedCompetencyMatrixQuestionCreateParams:
        return QueuedCompetencyMatrixQuestionCreateParams(
            question=question,
            grade=grade,
            sheet=sheet,
        )

    @classmethod
    def user(
        cls,
        username: str = "",
        password_hash: str = "",
        role: RoleEnum = RoleEnum.USER,
        is_active: bool = True,
    ) -> User:
        return User(
            username=username,
            password_hash=Secret(password_hash),
            role=role,
            is_active=is_active,
        )

    @classmethod
    def managed_accounts(
        cls,
        values: list[ManagedAccount] | None = None,
        total_count: int = 0,
        total_pages: int = 0,
    ) -> ManagedAccounts:
        return ManagedAccounts(
            values=values or [],
            total_count=total_count,
            total_pages=total_pages,
        )

    @classmethod
    def competency_matrix_items(
        cls,
        values: list[CompetencyMatrixItem] | None = None,
    ) -> CompetencyMatrixItems:
        return CompetencyMatrixItems(values=values or [])

    @classmethod
    def contact_me(
        cls,
        contact_me_id: str | None = None,
        name: str | None = None,
        email: str | None = None,
        telegram: str | None = None,
        message: str = "Message",
    ) -> ContactMe:
        return ContactMe(
            id=contact_me_id or cls.hex_id(1),
            name=name,
            email=email,
            telegram=telegram,
            message=message,
        )

    @classmethod
    def article(
        cls,
        article_id: str | None = None,
        title: str = "Test Article",
        content: str = "This is a test article content.",
        slug: str = "test-articles-article",
        folder: str = "General",
        folder_id: str | None = None,
        folder_key: str = "general",
        folder_priority: int = 1,
        title_ru: str | None = None,
        title_en: str | None = None,
        content_ru: str | None = None,
        content_en: str | None = None,
        folder_ru: str | None = None,
        folder_en: str | None = None,
        seo_title_ru: str | None = None,
        seo_title_en: str | None = None,
        seo_description_ru: str | None = None,
        seo_description_en: str | None = None,
        cover_image_file_id: str | None = None,
        cover_image_file: StoredFile | None = None,
        cover_image_url: str | None = None,
        cover_image_alt_ru: str | None = None,
        cover_image_alt_en: str | None = None,
        content_file_ids: frozenset[str] | None = None,
        metadata: ArticleMetadata | None = None,
        author_username: str = "admin",
        publish_status: PublishStatusEnum = PublishStatusEnum.PUBLISHED,
        published_at: str | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        tags: list[Tag] | None = None,
    ) -> Article:
        now = datetime.now(tz=UTC)
        return Article(
            id=article_id or cls.hex_id_from_text(f"article:{slug}"),
            slug=slug,
            title_ru=title_ru or title,
            title_en=title_en or title,
            content_ru=content_ru or content,
            content_en=content_en or content,
            folder=cls.article_folder(
                folder_id=folder_id,
                key=folder_key,
                name_ru=folder_ru or folder,
                name_en=folder_en or folder,
                priority=folder_priority,
            ),
            author_username=author_username,
            metadata=metadata
            or ArticleMetadata(
                seo_title_ru=seo_title_ru,
                seo_title_en=seo_title_en,
                seo_description_ru=seo_description_ru,
                seo_description_en=seo_description_en,
                cover_image_file_id=cover_image_file_id
                or (cover_image_file.id if cover_image_file is not None else None),
                cover_image_file=cover_image_file,
                cover_image_url=cover_image_url,
                cover_image_alt_ru=cover_image_alt_ru,
                cover_image_alt_en=cover_image_alt_en,
            ),
            publish_status=publish_status,
            published_at=(
                datetime.fromisoformat(published_at).replace(tzinfo=UTC)
                if published_at is not None
                else None
            ),
            created_at=(
                datetime.fromisoformat(created_at).replace(tzinfo=UTC)
                if created_at is not None
                else now
            ),
            updated_at=(
                datetime.fromisoformat(updated_at).replace(tzinfo=UTC)
                if updated_at is not None
                else now
            ),
            content_file_ids=content_file_ids or frozenset(),
            tags=Tags(values=tags or []),
        )

    @classmethod
    def article_folder(
        cls,
        folder_id: str | None = None,
        key: str = "general",
        name_ru: str = "Общее",
        name_en: str = "General",
        priority: int = 1,
    ) -> ArticleFolder:
        return ArticleFolder(
            id=folder_id or cls.hex_id_from_text(f"article-folder:{key}"),
            key=key,
            name_ru=name_ru,
            name_en=name_en,
            priority=priority,
        )

    @classmethod
    def article_folders(cls, values: list[ArticleFolder] | None = None) -> ArticleFolders:
        return ArticleFolders(values=values or [])

    @classmethod
    def article_list(
        cls,
        articles: list[Article] | None = None,
        total_count: int = 0,
        total_pages: int = 0,
    ) -> Articles:
        return Articles(values=articles or [], total_count=total_count, total_pages=total_pages)

    @classmethod
    def tag(
        cls,
        tag_id: int | str = 1,
        name: str = "Python",
        name_ru: str | None = None,
        name_en: str | None = None,
        slug: str = "python",
    ) -> Tag:
        return Tag(
            id=cls.hex_id(tag_id),
            name_ru=name_ru or name,
            name_en=name_en or name,
            slug=slug,
        )

    @classmethod
    def tags(cls, values: list[Tag] | None = None) -> Tags:
        return Tags(values=values or [])

    @classmethod
    def article_reaction_counts(
        cls,
        heart: int = 0,
        fire: int = 0,
        thinking: int = 0,
        neutral: int = 0,
        poop: int = 0,
    ) -> ArticleReactionCounts:
        return ArticleReactionCounts(
            heart=heart,
            fire=fire,
            thinking=thinking,
            neutral=neutral,
            poop=poop,
        )

    @classmethod
    def jwt_user(
        cls,
        username: str = "test",
        role: RoleEnum = RoleEnum.ADMIN,
    ) -> JwtUser:
        return JwtUser(username=username, role=role)

    @classmethod
    def stored_file(
        cls,
        file_id: int | str = 1,
        purpose: FilePurpose = FilePurpose.ARTICLE_CONTENT_IMAGE,
        namespace: Namespace = "media",
        relative_path: str = "article-content-images/file.png",
        mime_type: str = "image/png",
        size_bytes: int = 4,
        name: str = "Inline image",
        original_name: str = "original.png",
        original_sha256: str | None = None,
        orphaned_at: datetime | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> StoredFile:
        now = datetime(2026, 7, 3, 10, 0, tzinfo=UTC)
        return StoredFile(
            id=cls.hex_id(file_id) if isinstance(file_id, int) else file_id,
            purpose=purpose,
            namespace=namespace,
            relative_path=relative_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
            name=name,
            original_name=original_name,
            original_sha256=original_sha256,
            orphaned_at=orphaned_at,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )

    @classmethod
    def file_read(
        cls,
        file: StoredFile | None = None,
        access_url: str = "https://cdn.example.test/media/article-content-images/file.png",
        markdown_url: str = "https://cdn.example.test/media/article-content-images/file.png#fileId=00000000000000000000000000000001",
    ) -> FileRead:
        return FileRead(
            file=file or cls.stored_file(),
            access_url=access_url,
            markdown_url=markdown_url,
        )

    @classmethod
    def token(cls, value: bytes) -> Token:
        return Token(value)

    @classmethod
    def search_name(cls, value: Any) -> SearchName:
        return SearchName(value)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
