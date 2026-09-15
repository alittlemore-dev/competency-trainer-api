import pytest_asyncio
from httpx import codes

from core.auth.enums import RoleEnum
from core.auth.schemas import JwtUser
from core.files.enums import FilePurpose
from core.files.schemas import FileUpdateParams, FileUploadParams
from entrypoints.litestar.api.files.schemas import FileUploadRequestSchema
from entrypoints.litestar.api.schemas import CamelCaseSchema
from tests.test_cases import ApiTestCase
from tests.unit.mocks.providers.auth import test_current_datetime


class TestAdminFilesAPI(ApiTestCase):
    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, jwt_user: JwtUser, jwt_admin: JwtUser) -> None:
        self.user = jwt_user
        self.admin = jwt_admin
        self.authentication_use_case = await self.container.get_auth_use_case()
        self.use_case = await self.container.get_file_service()
        self.id_generator = await self.container.get_hex_uuid_id_generator()
        self.file_id = self.id_generator.get_next()
        self.file = self.factory.core.stored_file(
            file_id=self.file_id,
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
            relative_path="article-cover-images/file.png",
            name="Cover",
            original_name="cover.png",
        )
        self.file_read = self.factory.core.file_read(
            file=self.file,
            access_url="https://cdn.example.test/media/article-cover-images/file.png",
            markdown_url=(
                "https://cdn.example.test/media/article-cover-images/file.png"
                f"#fileId={self.file_id}"
            ),
        )

    def test_upload_request_schema_is_pydantic_api_schema(self) -> None:
        assert issubclass(FileUploadRequestSchema, CamelCaseSchema)
        assert set(FileUploadRequestSchema.model_fields) == {"purpose", "name", "file"}

    def test_upload_file_requires_content_manager_permission(self) -> None:
        self.authentication_use_case.authenticate.return_value = self.user

        response = self.api.post_admin_file(
            purpose=FilePurpose.ARTICLE_COVER_IMAGE.value,
            name="Cover",
            filename="cover.png",
            content=b"data",
            content_type="image/png",
        )

        assert response.status_code == codes.UNAUTHORIZED

    def test_upload_file_allows_moderator(self) -> None:
        self.authentication_use_case.authenticate.return_value = JwtUser(
            username="moderator",
            role=RoleEnum.MODERATOR,
        )
        self.use_case.upload_file.return_value = self.file_read

        response = self.api.post_admin_file(
            purpose=FilePurpose.ARTICLE_COVER_IMAGE.value,
            name="Cover",
            filename="cover.png",
            content=b"data",
            content_type="image/png",
        )

        assert response.status_code == codes.CREATED, response.content

    def test_upload_file_maps_multipart_request_and_response(self) -> None:
        self.authentication_use_case.authenticate.return_value = self.admin
        self.use_case.upload_file.return_value = self.file_read

        response = self.api.post_admin_file(
            purpose=FilePurpose.ARTICLE_COVER_IMAGE.value,
            name="Cover",
            filename="cover.png",
            content=b"data",
            content_type="image/png",
        )

        assert response.status_code == codes.CREATED, response.content
        assert response.json() == {
            "id": self.file_id,
            "purpose": "articleCoverImage",
            "namespace": "media",
            "relativePath": "article-cover-images/file.png",
            "mimeType": "image/png",
            "sizeBytes": 4,
            "name": "Cover",
            "originalName": "cover.png",
            "accessUrl": "https://cdn.example.test/media/article-cover-images/file.png",
            "markdownUrl": (
                "https://cdn.example.test/media/article-cover-images/file.png"
                f"#fileId={self.file_id}"
            ),
            "createdAt": "2026-07-03T10:00:00Z",
            "updatedAt": "2026-07-03T10:00:00Z",
        }
        self.use_case.upload_file.assert_called_once_with(
            params=FileUploadParams(
                id=self.file_id,
                purpose=FilePurpose.ARTICLE_COVER_IMAGE,
                name="Cover",
                original_name="cover.png",
                mime_type="image/png",
                content=b"data",
            ),
            current_datetime=test_current_datetime,
        )

    def test_list_files_maps_purpose_filter(self) -> None:
        self.authentication_use_case.authenticate.return_value = self.admin
        self.use_case.list_files.return_value = [self.file_read]

        response = self.api.get_admin_files(purpose=FilePurpose.ARTICLE_COVER_IMAGE.value)

        assert response.status_code == codes.OK, response.content
        assert response.json()["files"][0]["id"] == self.file_id
        self.use_case.list_files.assert_called_once_with(
            purpose=FilePurpose.ARTICLE_COVER_IMAGE,
        )

    def test_get_file_maps_file_id(self) -> None:
        self.authentication_use_case.authenticate.return_value = self.admin
        self.use_case.get_file.return_value = self.file_read

        response = self.api.get_admin_file(file_id=self.file_id)

        assert response.status_code == codes.OK, response.content
        assert response.json()["id"] == self.file_id
        self.use_case.get_file.assert_called_once_with(file_id=self.file_id)

    def test_update_file_maps_request(self) -> None:
        self.authentication_use_case.authenticate.return_value = self.admin
        self.use_case.update_file.return_value = self.file_read

        response = self.api.put_admin_file(file_id=self.file_id, name="Updated cover")

        assert response.status_code == codes.OK, response.content
        self.use_case.update_file.assert_called_once_with(
            file_id=self.file_id,
            params=FileUpdateParams(name="Updated cover"),
            current_datetime=test_current_datetime,
        )

    def test_delete_file_maps_file_id(self) -> None:
        self.authentication_use_case.authenticate.return_value = self.admin

        response = self.api.delete_admin_file(file_id=self.file_id)

        assert response.status_code == codes.NO_CONTENT, response.content
        self.use_case.delete_file.assert_called_once_with(file_id=self.file_id)
