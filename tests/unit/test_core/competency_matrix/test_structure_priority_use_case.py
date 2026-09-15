from unittest.mock import Mock

import pytest

from core.competency_matrix.exceptions import (
    CompetencyMatrixStructureNotFoundError,
    CompetencyMatrixStructurePriorityInvalidError,
)
from core.competency_matrix.schemas import (
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixStructure,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    CompetencyMatrixSubsectionPriorityUpdateParams,
)
from core.competency_matrix.services import QuestionSuggestionLimiter
from core.competency_matrix.storages import CompetencyMatrixStorage
from core.competency_matrix.use_cases import CompetencyMatrixUseCase
from tests.test_cases import TestCase


class TestCompetencyMatrixStructurePriorityUseCase(TestCase):
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.storage = Mock(spec=CompetencyMatrixStorage)
        self.question_suggestion_limiter = Mock(spec=QuestionSuggestionLimiter)
        self.use_case = CompetencyMatrixUseCase(
            storage=self.storage,
            question_suggestion_limiter=self.question_suggestion_limiter,
        )
        self.storage.list_structure.return_value = CompetencyMatrixStructure(
            sheets=[
                CompetencyMatrixStructureSheet(
                    id=self.factory.core.hex_id(1),
                    key="python",
                    name_ru="Питон",
                    name_en="Python",
                    priority=1,
                    sections=[
                        CompetencyMatrixStructureSection(
                            id=self.factory.core.hex_id(2),
                            name_ru="Основы",
                            name_en="Basics",
                            priority=1,
                            subsections=[
                                CompetencyMatrixStructureSubsection(
                                    id=self.factory.core.hex_id(4),
                                    name_ru="Функции",
                                    name_en="Functions",
                                    priority=1,
                                ),
                                CompetencyMatrixStructureSubsection(
                                    id=self.factory.core.hex_id(5),
                                    name_ru="Типизация",
                                    name_en="Typing",
                                    priority=2,
                                ),
                            ],
                        ),
                        CompetencyMatrixStructureSection(
                            id=self.factory.core.hex_id(3),
                            name_ru="Стиль",
                            name_en="Style",
                            priority=2,
                            subsections=[],
                        ),
                    ],
                ),
            ],
        )

    async def test_updates_valid_sheet_order(self) -> None:
        params = CompetencyMatrixSheetPriorityUpdateParams(
            ordered_ids=(self.factory.core.hex_id(1),),
        )

        await self.use_case.update_sheet_priorities(params=params)

        self.storage.update_sheet_priorities.assert_called_once_with(params=params)

    async def test_rejects_duplicate_or_stale_order(self) -> None:
        params = CompetencyMatrixSectionPriorityUpdateParams(
            sheet_id=self.factory.core.hex_id(1),
            ordered_ids=(self.factory.core.hex_id(2), self.factory.core.hex_id(2)),
        )

        with pytest.raises(CompetencyMatrixStructurePriorityInvalidError):
            await self.use_case.update_section_priorities(params=params)

        self.storage.update_section_priorities.assert_not_called()

    async def test_rejects_missing_parent(self) -> None:
        params = CompetencyMatrixSubsectionPriorityUpdateParams(
            section_id=self.factory.core.hex_id(-1),
            ordered_ids=(),
        )

        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            await self.use_case.update_subsection_priorities(params=params)

        self.storage.update_subsection_priorities.assert_not_called()

    def test_structure_validates_sheet_priority_order(self) -> None:
        structure = self.storage.list_structure.return_value

        structure.ensure_sheet_priority_order_matches(
            ordered_ids=(self.factory.core.hex_id(1),),
        )

        with pytest.raises(CompetencyMatrixStructurePriorityInvalidError):
            structure.ensure_sheet_priority_order_matches(
                ordered_ids=(self.factory.core.hex_id(1), self.factory.core.hex_id(1)),
            )

    def test_structure_finds_sheet_and_section(self) -> None:
        structure = self.storage.list_structure.return_value

        sheet = structure.require_sheet(sheet_id=self.factory.core.hex_id(1))
        section = structure.require_section(section_id=self.factory.core.hex_id(2))

        assert sheet.key == "python"
        assert section.name_en == "Basics"

        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            structure.require_sheet(sheet_id=self.factory.core.hex_id(-1))

        with pytest.raises(CompetencyMatrixStructureNotFoundError):
            structure.require_section(section_id=self.factory.core.hex_id(-1))

    def test_structure_nodes_validate_child_priority_order(self) -> None:
        structure = self.storage.list_structure.return_value
        sheet = structure.require_sheet(sheet_id=self.factory.core.hex_id(1))
        section = structure.require_section(section_id=self.factory.core.hex_id(2))

        sheet.ensure_section_priority_order_matches(
            ordered_ids=(self.factory.core.hex_id(3), self.factory.core.hex_id(2)),
        )
        section.ensure_subsection_priority_order_matches(
            ordered_ids=(self.factory.core.hex_id(5), self.factory.core.hex_id(4)),
        )

        with pytest.raises(CompetencyMatrixStructurePriorityInvalidError):
            sheet.ensure_section_priority_order_matches(ordered_ids=(self.factory.core.hex_id(2),))

        with pytest.raises(CompetencyMatrixStructurePriorityInvalidError):
            section.ensure_subsection_priority_order_matches(
                ordered_ids=(self.factory.core.hex_id(4), self.factory.core.hex_id(4)),
            )
