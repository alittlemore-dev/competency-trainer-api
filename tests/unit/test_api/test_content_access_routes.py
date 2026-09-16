from entrypoints.litestar.api.articles.endpoints import AdminArticlesApiController
from entrypoints.litestar.api.competency_matrix.endpoints import AdminCompetencyMatrixApiController
from entrypoints.litestar.api.files.endpoints import FilesApiController
from entrypoints.litestar.api.wiki_links.endpoints import WikiLinksApiController
from entrypoints.litestar.guards import content_manager_guard


class TestContentAccessRoutes:
    def test_admin_articles_controller_uses_content_manager_guard(self) -> None:
        assert AdminArticlesApiController.guards == [content_manager_guard]

    def test_admin_matrix_controller_uses_content_manager_guard(self) -> None:
        assert AdminCompetencyMatrixApiController.guards == [content_manager_guard]

    def test_file_upload_controller_uses_content_manager_guard(self) -> None:
        assert FilesApiController.guards == [content_manager_guard]

    def test_wiki_link_targets_handler_uses_content_manager_guard(self) -> None:
        assert WikiLinksApiController.guards == [content_manager_guard]
