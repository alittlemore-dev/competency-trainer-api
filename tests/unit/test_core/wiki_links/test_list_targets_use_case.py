from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from core.articles.schemas import ArticleTreeItemData
from core.articles.storages import ArticlesStorage
from core.competency_matrix.schemas import CompetencyMatrixItemFilters
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.enums import PublishStatusEnum
from core.i18n.enums import LanguageEnum
from core.wiki_links.enums import WikiLinkTargetTypeEnum
from core.wiki_links.schemas import WikiLinkTarget, WikiLinkTargetGroup, WikiLinkTargets
from core.wiki_links.use_cases import WikiLinksUseCase
from tests.test_cases import TestCase


class TestWikiLinksUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.articles_storage = Mock(spec=ArticlesStorage)
        self.matrix_storage = Mock(spec=CompetencyMatrixStorage)
        self.use_case = WikiLinksUseCase(
            articles_storage=self.articles_storage,
            matrix_storage=self.matrix_storage,
        )

    @pytest.mark.parametrize(
        ("language", "article_title", "matrix_title"),
        [
            (LanguageEnum.RU, "Типизированные статьи", "Как написать функцию"),
            (LanguageEnum.EN, "Typed articles", "How to write a function"),
        ],
    )
    async def test_lists_article_and_matrix_targets_for_authoring(
        self,
        language: LanguageEnum,
        article_title: str,
        matrix_title: str,
    ) -> None:
        now = datetime.now(tz=UTC)
        self.articles_storage.list_tree_items.return_value = [
            ArticleTreeItemData(
                folder_id=self.factory.core.hex_id(1),
                folder_key="engineering",
                folder="Engineering",
                title=article_title,
                slug="typed-articles",
                publish_status=PublishStatusEnum.PUBLISHED,
                published_at=None,
                updated_at=now,
            ),
            ArticleTreeItemData(
                folder_id=self.factory.core.hex_id(1),
                folder_key="engineering",
                folder="Engineering",
                title="Draft articles",
                slug="draft-articles",
                publish_status=PublishStatusEnum.DRAFT,
                published_at=None,
                updated_at=now,
            ),
        ]
        self.matrix_storage.list_competency_matrix_items.return_value = [
            self.factory.core.competency_matrix_item(
                item_id=1,
                slug="how-to-write-function",
                question_ru="Как написать функцию",
                question_en="How to write a function",
            ),
            self.factory.core.competency_matrix_item(
                item_id=2,
                slug="draft-matrix-question",
                question_ru="Черновой вопрос матрицы",
                question_en="Draft matrix question",
                publish_status=PublishStatusEnum.DRAFT,
            ),
        ]

        result = await self.use_case.list_targets(language=language)

        assert result == WikiLinkTargets(
            values=[
                WikiLinkTargetGroup(
                    type=WikiLinkTargetTypeEnum.ARTICLES,
                    items=[
                        WikiLinkTarget(
                            slug="typed-articles",
                            title=article_title,
                            publish_status=PublishStatusEnum.PUBLISHED,
                        ),
                        WikiLinkTarget(
                            slug="draft-articles",
                            title="Draft articles",
                            publish_status=PublishStatusEnum.DRAFT,
                        ),
                    ],
                ),
                WikiLinkTargetGroup(
                    type=WikiLinkTargetTypeEnum.MATRIX,
                    items=[
                        WikiLinkTarget(
                            slug="how-to-write-function",
                            title=matrix_title,
                            publish_status=PublishStatusEnum.PUBLISHED,
                        ),
                        WikiLinkTarget(
                            slug="draft-matrix-question",
                            title=(
                                "Черновой вопрос матрицы"
                                if language == LanguageEnum.RU
                                else "Draft matrix question"
                            ),
                            publish_status=PublishStatusEnum.DRAFT,
                        ),
                    ],
                ),
            ],
        )
        self.articles_storage.list_tree_items.assert_called_once_with(
            only_published=False,
            language=language,
        )
        self.matrix_storage.list_competency_matrix_items.assert_called_once_with(
            filters=CompetencyMatrixItemFilters(only_published=False),
        )
