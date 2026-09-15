from datetime import date

import pytest_asyncio
from httpx import codes

from core.articles.schemas import ArticleFilters
from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.i18n.enums import LanguageEnum
from entrypoints.litestar.api.competency_matrix.endpoints import (
    AdminCompetencyMatrixApiController,
)
from entrypoints.litestar.api.routers import api_router
from entrypoints.litestar.guards import content_manager_guard
from tests.test_cases import ApiTestCase


class TestApiScopeRoutes(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self) -> None:
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.articles_use_case = await self.container.get_articles_use_case()

    def test_public_articles_list_forces_public_visibility(self) -> None:
        self.articles_use_case.list_articles.return_value = self.factory.core.article_list(
            articles=[],
            total_count=0,
            total_pages=0,
        )

        response = self.no_auth_api.client.get(
            "/api/articles",
            params={
                "page": 1,
                "pageSize": 10,
                "language": "ru",
                "onlyPublished": "false",
            },
        )

        assert response.status_code == codes.OK, response.content
        self.articles_use_case.list_articles.assert_called_once_with(
            filters=ArticleFilters(
                page=1,
                page_size=10,
                language=LanguageEnum.RU,
                only_published=True,
                tag_slug=None,
                published_from=None,
                published_to=None,
                search_query=None,
                include_tags=True,
            ),
        )

    def test_admin_articles_list_uses_admin_prefix_for_draft_visibility(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.articles_use_case.list_articles.return_value = self.factory.core.article_list(
            articles=[],
            total_count=0,
            total_pages=0,
        )

        response = self.api.client.get(
            "/api/admin/articles",
            params={
                "page": 2,
                "pageSize": 5,
                "language": "en",
                "onlyPublished": "false",
                "publishedFrom": "2026-01-01",
                "publishedTo": "2026-01-31",
                "searchQuery": "  typed articles  ",
            },
        )

        assert response.status_code == codes.OK, response.content
        self.articles_use_case.list_articles.assert_called_once_with(
            filters=ArticleFilters(
                page=2,
                page_size=5,
                language=LanguageEnum.EN,
                only_published=False,
                tag_slug=None,
                published_from=date(2026, 1, 1),
                published_to=date(2026, 1, 31),
                search_query="typed articles",
                include_tags=True,
            ),
        )


class TestApiScopeRouteMetadata:
    def test_matrix_admin_urls_are_not_exposed_under_public_api(self) -> None:
        route_paths = _api_route_paths()

        assert AdminCompetencyMatrixApiController.guards == [content_manager_guard]
        assert "/api/competency-matrix/resources/search" not in route_paths
        assert "/api/competency-matrix/queued-questions" not in route_paths
        assert "/api/competency-matrix/queued-questions/import" not in route_paths
        assert "/api/admin/competency-matrix/resources/search" in route_paths
        assert "/api/admin/competency-matrix/queued-questions" in route_paths
        assert "/api/admin/competency-matrix/queued-questions/import" in route_paths


def _api_route_paths() -> set[str]:
    return {route.path for route in api_router.routes}
