from typing import Any


class ApiFactoryHelper:
    @classmethod
    def hex_id(cls, value: int | str) -> str:
        if isinstance(value, str):
            return value
        return f"{value:032x}"

    @classmethod
    def contact_me_request(
        cls,
        name: str | None = None,
        email: str | None = None,
        telegram: str | None = None,
        message: str = "Message",
    ) -> dict[str, Any]:
        return {
            "name": name,
            "email": email,
            "telegram": telegram,
            "message": message,
        }

    @classmethod
    def login_request(cls, username: str = "TEST", password: str | None = None) -> dict[str, Any]:
        return {"username": username, "password": password or "TEST"}

    @classmethod
    def article_request(
        cls,
        title_ru: str = "Статья",
        title_en: str = "Article",
        content_ru: str = "Содержимое статьи",
        content_en: str = "Article content",
        slug: str = "article",
        folder_id: str | None = None,
        publish_status: str = "Draft",
        metadata: dict[str, Any] | None = None,
        tag_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "slug": slug,
            "folderId": folder_id or cls.hex_id(20),
            "publishStatus": publish_status,
            "tagIds": tag_ids or [],
            "metadata": metadata
            if metadata is not None
            else {
                "seoTitleRu": "SEO статья",
                "seoTitleEn": "SEO article",
                "seoDescriptionRu": "Описание для выдачи",
                "seoDescriptionEn": "Search result description",
                "coverImageFileId": cls.hex_id(30),
                "coverImageAltRu": "Обложка статьи",
                "coverImageAltEn": "Article cover",
            },
            "translations": {
                "ru": {"title": title_ru, "content": content_ru},
                "en": {"title": title_en, "content": content_en},
            },
        }

    @classmethod
    def article_folder_request(
        cls,
        key: str = "general",
        name_ru: str = "Общее",
        name_en: str = "General",
    ) -> dict[str, Any]:
        return {
            "key": key,
            "translations": {
                "ru": {"name": name_ru},
                "en": {"name": name_en},
            },
        }

    @classmethod
    def tag_request(
        cls,
        name_ru: str = "Питон",
        name_en: str = "Python",
        slug: str = "python",
    ) -> dict[str, Any]:
        return {
            "slug": slug,
            "translations": {
                "ru": {"name": name_ru},
                "en": {"name": name_en},
            },
        }

    @classmethod
    def competency_matrix_item_request(
        cls,
        slug: str = "question-1",
        subsection_id: int | str = "00000000000000000000000000000001",
        question_ru: str = "вопрос 1",
        question_en: str = "question 1",
        answer_ru: str = "ответ 1",
        answer_en: str = "answer 1",
        interview_answer_explanation_ru: str = "объяснение ответа 1",
        interview_answer_explanation_en: str = "interview answer explanation 1",
        sheet_key: str = "python",
        sheet_ru: str = "Питон",
        sheet_en: str = "Python",
        grade: str | None = "Junior",
        interview_frequency: str | None = "often",
        section_ru: str = "Основы",
        section_en: str = "Basics",
        subsection_ru: str = "Функции",
        subsection_en: str = "Functions",
        publish_status: str = "Draft",
        resources: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        _ = (
            sheet_key,
            sheet_ru,
            sheet_en,
            section_ru,
            section_en,
            subsection_ru,
            subsection_en,
        )
        return {
            "slug": slug,
            "subsectionId": cls.hex_id(subsection_id),
            "grade": grade,
            "interviewFrequency": interview_frequency,
            "publishStatus": publish_status,
            "translations": {
                "ru": {
                    "question": question_ru,
                    "answer": answer_ru,
                    "interviewAnswerExplanation": interview_answer_explanation_ru,
                },
                "en": {
                    "question": question_en,
                    "answer": answer_en,
                    "interviewAnswerExplanation": interview_answer_explanation_en,
                },
            },
            "resources": resources or [],
        }

    @classmethod
    def question_suggestion_request(cls, question: str = "What is PEP 8?") -> dict[str, Any]:
        return {"question": question}

    @classmethod
    def existing_matrix_resource_attachment_request(
        cls,
        resource_id: int | str = "00000000000000000000000000000001",
        context_ru: str = "контекст ресурса",
        context_en: str = "resource context",
    ) -> dict[str, Any]:
        return {
            "resourceId": cls.hex_id(resource_id),
            "translations": {
                "ru": {"context": context_ru},
                "en": {"context": context_en},
            },
        }

    @classmethod
    def new_matrix_resource_attachment_request(
        cls,
        name_ru: str = "ресурс",
        name_en: str = "resource",
        url: str = "http://example.com",
        context_ru: str = "контекст ресурса",
        context_en: str = "resource context",
    ) -> dict[str, Any]:
        return {
            "resource": {
                "url": url,
                "translations": {
                    "ru": {"name": name_ru},
                    "en": {"name": name_en},
                },
            },
            "translations": {
                "ru": {"context": context_ru},
                "en": {"context": context_en},
            },
        }
