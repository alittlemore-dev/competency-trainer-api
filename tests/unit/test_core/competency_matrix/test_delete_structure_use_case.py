from unittest.mock import Mock

import pytest

from core.competency_matrix.exceptions import CompetencyMatrixStructureContainsQuestionsError
from core.competency_matrix.schemas import (
    CompetencyMatrixStructureDeletionImpact,
    CompetencyMatrixStructureNodeKind,
)
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from tests.test_cases import TestCase


class TestDeleteStructureUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=CompetencyMatrixStorage)
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=Mock(spec=QuestionSuggestionLimiter),
        )

    @pytest.mark.parametrize("kind", list(CompetencyMatrixStructureNodeKind))
    async def test_deletes_branch_without_questions(
        self, kind: CompetencyMatrixStructureNodeKind
    ) -> None:
        node_id = self.factory.core.hex_id(1)
        subsection_ids = (self.factory.core.hex_id(3),)
        self.storage.inspect_structure_deletion.return_value = (
            CompetencyMatrixStructureDeletionImpact(
                subsection_ids=subsection_ids,
                has_questions=False,
            )
        )

        await self.use_case.delete_structure_node(
            kind=kind,
            node_id=node_id,
            delete_with_questions=False,
        )

        self.storage.delete_structure_node.assert_called_once_with(
            kind=kind,
            node_id=node_id,
            subsection_ids=subsection_ids,
        )

    async def test_requires_confirmation_before_deleting_questions(self) -> None:
        self.storage.inspect_structure_deletion.return_value = (
            CompetencyMatrixStructureDeletionImpact(
                subsection_ids=(self.factory.core.hex_id(3),),
                has_questions=True,
            )
        )

        with pytest.raises(CompetencyMatrixStructureContainsQuestionsError):
            await self.use_case.delete_structure_node(
                kind=CompetencyMatrixStructureNodeKind.SHEET,
                node_id=self.factory.core.hex_id(1),
                delete_with_questions=False,
            )

        self.storage.delete_structure_node.assert_not_called()

    async def test_deletes_questions_after_confirmation(self) -> None:
        node_id = self.factory.core.hex_id(1)
        subsection_ids = (self.factory.core.hex_id(3),)
        self.storage.inspect_structure_deletion.return_value = (
            CompetencyMatrixStructureDeletionImpact(
                subsection_ids=subsection_ids,
                has_questions=True,
            )
        )

        await self.use_case.delete_structure_node(
            kind=CompetencyMatrixStructureNodeKind.SECTION,
            node_id=node_id,
            delete_with_questions=True,
        )

        self.storage.delete_structure_node.assert_called_once_with(
            kind=CompetencyMatrixStructureNodeKind.SECTION,
            node_id=node_id,
            subsection_ids=subsection_ids,
        )
