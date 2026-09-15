import json
from io import BytesIO
from unittest.mock import AsyncMock, Mock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

from core.files.exceptions import FileClientInternalError, NamespaceNotAllowedError
from core.files.schemas import FileUploadResult
from infra.s3.clients import S3ClientBundle, S3FileClient


def create_client_error(code: str, operation_name: str = "HeadBucket") -> ClientError:
    return ClientError(
        error_response={
            "Error": {
                "Code": code,
                "Message": "S3 operation failed",
            },
        },
        operation_name=operation_name,
    )


def create_s3_client_double() -> Mock:
    client = Mock()
    client.head_bucket = AsyncMock()
    client.create_bucket = AsyncMock()
    client.put_bucket_policy = AsyncMock()
    client.put_bucket_cors = AsyncMock()
    client.put_object = AsyncMock()
    client.delete_object = AsyncMock()
    return client


class TestS3FileClient:
    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        self.internal_client = create_s3_client_double()
        self.public_client = create_s3_client_double()
        self.storage = S3FileClient(
            clients=S3ClientBundle(
                internal=self.internal_client,
                public=self.public_client,
            ),
        )

    async def test_ensure_bucket_exists_bucket_exists(self) -> None:
        bucket_name = "media"
        self.internal_client.head_bucket.return_value = {}

        await self.storage.ensure_namespace_exists(bucket_name)

        self.internal_client.head_bucket.assert_awaited_once_with(Bucket=bucket_name)
        self.internal_client.create_bucket.assert_not_awaited()
        self.internal_client.put_bucket_policy.assert_awaited_once()
        self.internal_client.put_bucket_cors.assert_awaited_once()

    async def test_ensure_bucket_exists_bucket_not_exists(self) -> None:
        bucket_name = "media"
        self.internal_client.head_bucket.side_effect = create_client_error("404")

        await self.storage.ensure_namespace_exists(bucket_name)

        self.internal_client.head_bucket.assert_awaited_once_with(Bucket=bucket_name)
        self.internal_client.create_bucket.assert_awaited_once_with(Bucket=bucket_name)
        self.internal_client.put_bucket_policy.assert_awaited_once()
        self.internal_client.put_bucket_cors.assert_awaited_once()

    async def test_ensure_bucket_exists_sets_public_read_policy_and_file_cors(self) -> None:
        bucket_name = "media"
        self.internal_client.head_bucket.return_value = {}

        with patch("infra.s3.clients.settings") as mock_settings:
            mock_settings.app.public_origin = "https://alittlemoron.ru"
            mock_settings.minio.cors_max_age_seconds = 300
            await self.storage.ensure_namespace_exists(bucket_name)

        policy_call = self.internal_client.put_bucket_policy.await_args.kwargs
        assert policy_call["Bucket"] == bucket_name
        assert json.loads(policy_call["Policy"]) == self.storage.create_bucket_policy(
            bucket_name=bucket_name,
        )
        self.internal_client.put_bucket_cors.assert_awaited_once_with(
            Bucket=bucket_name,
            CORSConfiguration={
                "CORSRules": [
                    {
                        "AllowedHeaders": ["*"],
                        "AllowedMethods": ["GET"],
                        "AllowedOrigins": ["https://alittlemoron.ru"],
                        "ExposeHeaders": ["ETag"],
                        "MaxAgeSeconds": 300,
                    },
                ],
            },
        )

    async def test_ensure_bucket_exists_tolerates_unsupported_bucket_cors(self) -> None:
        bucket_name = "media"
        self.internal_client.head_bucket.return_value = {}
        self.internal_client.put_bucket_cors.side_effect = create_client_error(
            code="NotImplemented",
            operation_name="PutBucketCors",
        )

        await self.storage.ensure_namespace_exists(bucket_name)

        self.internal_client.put_bucket_policy.assert_awaited_once()
        self.internal_client.put_bucket_cors.assert_awaited_once()

    @patch("infra.s3.clients.settings")
    async def test_upload_file_success(self, mock_settings: Mock) -> None:
        mock_settings.minio.get_object_url.return_value = "http://localhost/media/test.txt"
        file_data = BytesIO(b"test content")
        object_name = "test.txt"
        content_type = "text/plain"
        self.internal_client.head_bucket.return_value = {}
        self.internal_client.put_object.return_value = {}

        result = await self.storage.upload_file(
            file_data=file_data,
            object_name=object_name,
            namespace="media",
            content_type=content_type,
        )
        expected_result = FileUploadResult(
            url="http://localhost/media/test.txt",
            bucket="media",
            object_name=object_name,
            size=12,
        )
        assert result == expected_result
        self.internal_client.put_object.assert_awaited_once_with(
            Bucket="media",
            Key=object_name,
            Body=b"test content",
            ContentType=content_type,
        )
        mock_settings.minio.get_object_url.assert_called_once_with(
            bucket="media",
            object_path=object_name,
        )

    async def test_ensure_namespace_valid(self) -> None:
        file_data = BytesIO(b"test content")
        object_name = "test.txt"
        self.internal_client.head_bucket.return_value = {}
        with pytest.raises(NamespaceNotAllowedError):
            await self.storage.upload_file(
                file_data=file_data,
                object_name=object_name,
                namespace="NOT_VALID",
                content_type="application/octet-stream",
            )

    async def test_upload_file_minio_exception(self) -> None:
        file_data = BytesIO(b"test content")
        object_name = "test.txt"
        self.internal_client.head_bucket.return_value = {}
        self.internal_client.put_object.side_effect = create_client_error("500")
        with pytest.raises(FileClientInternalError, match="File upload failed"):
            await self.storage.upload_file(
                file_data=file_data,
                object_name=object_name,
                namespace="media",
                content_type="application/octet-stream",
            )

    async def test_delete_file_success(self) -> None:
        await self.storage.delete_file(object_name="test.txt", namespace="media")

        self.internal_client.delete_object.assert_awaited_once_with(
            Bucket="media",
            Key="test.txt",
        )

    async def test_delete_file_minio_exception(self) -> None:
        self.internal_client.delete_object.side_effect = create_client_error(
            code="500",
            operation_name="DeleteObject",
        )

        with pytest.raises(FileClientInternalError, match="File delete failed"):
            await self.storage.delete_file(object_name="test.txt", namespace="media")

    async def test_delete_file_minio_connection_exception(self) -> None:
        self.internal_client.delete_object.side_effect = EndpointConnectionError(
            endpoint_url="http://minio:9000",
        )

        with pytest.raises(FileClientInternalError, match="File delete failed"):
            await self.storage.delete_file(object_name="test.txt", namespace="media")

    async def test_init_storage(self) -> None:
        with patch.object(self.storage, "ensure_namespace_exists") as mock_ensure:
            mock_ensure.return_value = None
            await self.storage.init_storage()
            mock_ensure.assert_called_once_with(namespace="media")

    @patch("infra.s3.clients.settings")
    async def test_get_access_url_returns_public_object_url(
        self,
        mock_settings: Mock,
    ) -> None:
        mock_settings.minio.get_object_url.return_value = "http://localhost/media/test.txt"

        result = self.storage.get_access_url(object_name="test.txt", namespace="media")

        assert result == "http://localhost/media/test.txt"
        mock_settings.minio.get_object_url.assert_called_once_with(
            bucket="media",
            object_path="test.txt",
        )
