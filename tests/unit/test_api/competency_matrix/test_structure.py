import pytest_asyncio
from httpx import codes

from core.competency_matrix.schemas import (
    CompetencyMatrixSectionPriorityUpdateParams,
    CompetencyMatrixSheetPriorityUpdateParams,
    CompetencyMatrixStructure,
    CompetencyMatrixStructureSection,
    CompetencyMatrixStructureSheet,
    CompetencyMatrixStructureSubsection,
    CompetencyMatrixSubsectionPriorityUpdateParams,
)
from entrypoints.litestar.api.competency_matrix.endpoints import (
    AdminCompetencyMatrixApiController,
    PublicCompetencyMatrixApiController,
)
from entrypoints.litestar.api.routers import api_router
from entrypoints.litestar.guards import content_manager_guard
from tests.test_cases import ApiTestCase


class TestMatrixStructureAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.use_case = await self.container.get_competency_matrix_use_case()

    def test_lists_admin_structure_tree(self) -> None:
        self.use_case.list_structure.return_value = CompetencyMatrixStructure(
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
                                    id=self.factory.core.hex_id(3),
                                    name_ru="Функции",
                                    name_en="Functions",
                                    priority=1,
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        )

        response = self.api.client.get(
            "/api/admin/competency-matrix/structure",
            params={"language": "en"},
        )

        assert response.status_code == codes.OK, response.content
        assert response.json() == {
            "sheets": [
                {
                    "id": self.factory.core.hex_id(1),
                    "key": "python",
                    "name": "Python",
                    "priority": 1,
                    "translations": {
                        "ru": {"name": "Питон"},
                        "en": {"name": "Python"},
                    },
                    "sections": [
                        {
                            "id": self.factory.core.hex_id(2),
                            "name": "Basics",
                            "priority": 1,
                            "translations": {
                                "ru": {"name": "Основы"},
                                "en": {"name": "Basics"},
                            },
                            "subsections": [
                                {
                                    "id": self.factory.core.hex_id(3),
                                    "name": "Functions",
                                    "priority": 1,
                                    "translations": {
                                        "ru": {"name": "Функции"},
                                        "en": {"name": "Functions"},
                                    },
                                },
                            ],
                        },
                    ],
                },
            ],
        }
        self.use_case.list_structure.assert_called_once_with()

    def test_creates_sheet_section_and_subsection(self) -> None:
        self.use_case.create_sheet.return_value = CompetencyMatrixStructureSheet(
            id=self.factory.core.hex_id(1),
            key="python",
            name_ru="Питон",
            name_en="Python",
            priority=1,
            sections=[],
        )
        self.use_case.create_section.return_value = CompetencyMatrixStructureSection(
            id=self.factory.core.hex_id(2),
            name_ru="Основы",
            name_en="Basics",
            priority=1,
            subsections=[],
        )
        self.use_case.create_subsection.return_value = CompetencyMatrixStructureSubsection(
            id=self.factory.core.hex_id(3),
            name_ru="Функции",
            name_en="Functions",
            priority=1,
        )

        sheet_response = self.api.client.post(
            "/api/admin/competency-matrix/sheets",
            params={"language": "en"},
            json={
                "key": "python",
                "translations": {
                    "ru": {"name": "Питон"},
                    "en": {"name": "Python"},
                },
            },
        )
        section_response = self.api.client.post(
            "/api/admin/competency-matrix/sheets/1/sections",
            params={"language": "en"},
            json={
                "translations": {
                    "ru": {"name": "Основы"},
                    "en": {"name": "Basics"},
                },
            },
        )
        subsection_response = self.api.client.post(
            "/api/admin/competency-matrix/sections/2/subsections",
            params={"language": "en"},
            json={
                "translations": {
                    "ru": {"name": "Функции"},
                    "en": {"name": "Functions"},
                },
            },
        )

        assert sheet_response.status_code == codes.CREATED, sheet_response.content
        assert section_response.status_code == codes.CREATED, section_response.content
        assert subsection_response.status_code == codes.CREATED, subsection_response.content
        assert sheet_response.json()["key"] == "python"
        assert section_response.json()["name"] == "Basics"
        assert subsection_response.json()["name"] == "Functions"

    def test_updates_structure_priorities(self) -> None:
        sheet_response = self.api.put_update_matrix_sheet_priorities(ordered_ids=[2, 1])
        section_response = self.api.put_update_matrix_section_priorities(
            sheet_id=1,
            ordered_ids=[3, 2],
        )
        subsection_response = self.api.put_update_matrix_subsection_priorities(
            section_id=2,
            ordered_ids=[5, 4],
        )

        assert sheet_response.status_code == codes.NO_CONTENT, sheet_response.content
        assert section_response.status_code == codes.NO_CONTENT, section_response.content
        assert subsection_response.status_code == codes.NO_CONTENT, subsection_response.content
        self.use_case.update_sheet_priorities.assert_called_once_with(
            params=CompetencyMatrixSheetPriorityUpdateParams(
                ordered_ids=(self.factory.core.hex_id(2), self.factory.core.hex_id(1)),
            ),
        )
        self.use_case.update_section_priorities.assert_called_once_with(
            params=CompetencyMatrixSectionPriorityUpdateParams(
                sheet_id=self.factory.core.hex_id(1),
                ordered_ids=(self.factory.core.hex_id(3), self.factory.core.hex_id(2)),
            ),
        )
        self.use_case.update_subsection_priorities.assert_called_once_with(
            params=CompetencyMatrixSubsectionPriorityUpdateParams(
                section_id=self.factory.core.hex_id(2),
                ordered_ids=(self.factory.core.hex_id(5), self.factory.core.hex_id(4)),
            ),
        )

    def test_create_sheet_rejects_invalid_key(self) -> None:
        response = self.api.client.post(
            "/api/admin/competency-matrix/sheets",
            params={"language": "en"},
            json={
                "key": "Python Core",
                "translations": {
                    "ru": {"name": "Питон"},
                    "en": {"name": "Python"},
                },
            },
        )

        assert response.status_code == codes.BAD_REQUEST, response.content
        self.use_case.create_sheet.assert_not_called()

    def test_create_structure_node_rejects_whitespace_name(self) -> None:
        response = self.api.client.post(
            "/api/admin/competency-matrix/sheets/1/sections",
            params={"language": "en"},
            json={
                "translations": {
                    "ru": {"name": "Основы"},
                    "en": {"name": "   "},
                },
            },
        )

        assert response.status_code == codes.BAD_REQUEST, response.content
        self.use_case.create_section.assert_not_called()


class TestMatrixStructureRouteMetadata:
    def test_structure_endpoints_are_admin_only(self) -> None:
        route_paths = _api_route_paths()

        assert AdminCompetencyMatrixApiController.guards == [content_manager_guard]
        assert not hasattr(
            PublicCompetencyMatrixApiController,
            "list_competency_matrix_structure",
        )
        assert "/api/competency-matrix/structure" not in route_paths
        assert "/api/admin/competency-matrix/structure" in route_paths
        assert "POST" not in _api_route_methods(path="/api/competency-matrix/sheets")
        assert "/api/admin/competency-matrix/sheets" in route_paths
        assert "/api/admin/competency-matrix/sheets/priorities" in route_paths


def _api_route_paths() -> set[str]:
    return {route.path for route in api_router.routes}


def _api_route_methods(path: str) -> set[str]:
    for route in api_router.routes:
        if route.path == path:
            return set(route.methods)

    raise AssertionError(path)
