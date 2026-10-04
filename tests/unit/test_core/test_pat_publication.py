from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from core.articles.schemas import ArticleCreateParams, ArticleUpdateParams
from core.articles.storages import ArticlesStorage
from core.articles.use_cases import ArticlesUseCase
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from core.enums import PublishStatusEnum
from core.files.clients import FileClient
from core.files.services import FileService
from core.identity import ForbiddenError, PublicationAccess
from tests.test_cases import TestCase


class TestPatPublication(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.now = datetime(2026, 10, 4, tzinfo=UTC)
        self.articles_storage = Mock(spec=ArticlesStorage)
        self.matrix_storage = Mock(spec=CompetencyMatrixStorage)
        self.articles = ArticlesUseCase(
            publication=PublicationAccess(allowed=False),
            storage=self.articles_storage,
            file_service=Mock(spec=FileService),
            file_client=Mock(spec=FileClient),
        )
        self.matrix = CompetencyMatrixUseCase(
            publication=PublicationAccess(allowed=False),
            storage=self.matrix_storage,
            question_suggestion_limiter=Mock(spec=QuestionSuggestionLimiter),
        )

    async def test_published_article_creation_requires_publication(self) -> None:
        params = Mock(spec=ArticleCreateParams, publish_status=PublishStatusEnum.PUBLISHED)
        with pytest.raises(ForbiddenError):
            await self.articles.create_article(params=params, current_datetime=self.now)
        self.articles_storage.create_article.assert_not_called()
        self.articles_storage.get_tags_by_ids.assert_not_called()

    @pytest.mark.parametrize("existing_status", list(PublishStatusEnum))
    async def test_article_update_checks_current_and_requested_publication(
        self,
        existing_status: PublishStatusEnum,
    ) -> None:
        self.articles_storage.get_article_by_slug.return_value = self.factory.core.article(
            publish_status=existing_status,
        )
        requested_status = (
            PublishStatusEnum.DRAFT
            if existing_status == PublishStatusEnum.PUBLISHED
            else PublishStatusEnum.PUBLISHED
        )
        params = Mock(spec=ArticleUpdateParams, publish_status=requested_status)
        with pytest.raises(ForbiddenError):
            await self.articles.update_article(
                slug="protected", params=params, current_datetime=self.now
            )
        self.articles_storage.get_article_by_slug.assert_called_once_with(
            slug="protected", lock=True
        )
        self.articles_storage.update_article.assert_not_called()

    async def test_published_article_deletion_requires_publication(self) -> None:
        self.articles_storage.get_article_by_slug.return_value = self.factory.core.article(
            publish_status=PublishStatusEnum.PUBLISHED,
        )
        with pytest.raises(ForbiddenError):
            await self.articles.delete_article(slug="published", current_datetime=self.now)
        self.articles_storage.delete_article.assert_not_called()

    async def test_published_question_cannot_be_replaced_with_draft(self) -> None:
        params = self.factory.core.competency_matrix_item_update_params(
            item_id=1,
            publish_status=PublishStatusEnum.DRAFT,
        )
        self.matrix_storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=1,
                publish_status=PublishStatusEnum.PUBLISHED,
            )
        )
        self.matrix_storage.get_resources_by_ids.return_value = (
            self.factory.core.external_resources(values=[])
        )
        self.matrix_storage.get_item_structure_by_subsection_id.return_value = (
            self.factory.core.competency_matrix_item_structure()
        )
        with pytest.raises(ForbiddenError):
            await self.matrix.update_item(params=params)
        self.matrix_storage.get_competency_matrix_item.assert_called_once_with(
            item_id=params.id, lock=True
        )
        self.matrix_storage.update_competency_matrix_item.assert_not_called()

    @pytest.mark.parametrize("published", [True, False])
    async def test_question_delete_locks_current_state_and_allows_drafts(
        self, published: bool
    ) -> None:
        status = PublishStatusEnum.PUBLISHED if published else PublishStatusEnum.DRAFT
        self.matrix_storage.get_competency_matrix_item.return_value = (
            self.factory.core.competency_matrix_item(
                item_id=1,
                publish_status=status,
            )
        )
        item_id = self.factory.core.hex_id(1)
        if published:
            with pytest.raises(ForbiddenError):
                await self.matrix.delete_item(item_id=item_id)
            self.matrix_storage.delete_competency_matrix_item.assert_not_called()
        else:
            await self.matrix.delete_item(item_id=item_id)
            self.matrix_storage.delete_competency_matrix_item.assert_called_once_with(
                item_id=item_id
            )
        self.matrix_storage.get_competency_matrix_item.assert_called_once_with(
            item_id=item_id, lock=True
        )
