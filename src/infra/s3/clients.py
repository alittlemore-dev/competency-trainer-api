import json
from contextlib import suppress
from dataclasses import dataclass
from http import HTTPStatus
from io import BytesIO
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from types_aiobotocore_s3.client import S3Client
from types_aiobotocore_s3.type_defs import CORSConfigurationTypeDef

from core.files.clients import FileClient
from core.files.exceptions import FileClientInternalError, NamespaceNotAllowedError
from core.files.schemas import FileUploadResult
from core.files.types import Namespace
from infra.config.loggers import logger
from infra.config.settings import settings


@dataclass(frozen=True, kw_only=True, slots=True)
class S3ClientBundle:
    internal: S3Client
    public: S3Client


@dataclass(kw_only=True)
class S3FileClient(FileClient):
    clients: S3ClientBundle

    @staticmethod
    def create_bucket_policy(bucket_name: str) -> dict[str, Any]:
        return {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                    "Resource": f"arn:aws:s3:::{bucket_name}",
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": "s3:GetObject",
                    "Resource": f"arn:aws:s3:::{bucket_name}/*",
                },
            ],
        }

    @staticmethod
    def create_bucket_cors(allowed_origin: str, max_age_seconds: int) -> CORSConfigurationTypeDef:
        return {
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET"],
                    "AllowedOrigins": [allowed_origin],
                    "ExposeHeaders": ["ETag"],
                    "MaxAgeSeconds": max_age_seconds,
                },
            ],
        }

    @staticmethod
    def _ensure_valid_namespace(namespace: str) -> Namespace:
        if namespace != "media":
            logger.error("Passed incorrect namespace:", bucket_name=namespace)
            raise NamespaceNotAllowedError(namespace=namespace)
        return namespace  # type: ignore[return-value]

    async def ensure_namespace_exists(self, namespace: str) -> None:
        logger.info("Ensuring bucket exists", bucket_name=namespace)
        if not await self._bucket_exists(bucket_name=namespace):
            await self.clients.internal.create_bucket(Bucket=namespace)
            logger.info("Bucket created", bucket_name=namespace)
        await self.clients.internal.put_bucket_policy(
            Bucket=namespace,
            Policy=json.dumps(self.create_bucket_policy(bucket_name=namespace)),
        )
        try:
            await self.clients.internal.put_bucket_cors(
                Bucket=namespace,
                CORSConfiguration=self.create_bucket_cors(
                    allowed_origin=settings.app.public_origin,
                    max_age_seconds=settings.minio.cors_max_age_seconds,
                ),
            )
        except ClientError as exc:
            if not self._is_operation_not_implemented(exc):
                raise
            logger.warning(
                "S3 bucket CORS setup is not supported by the storage service",
                bucket_name=namespace,
            )
        logger.info("Bucket policy set and bucket CORS setup attempted", bucket_name=namespace)

    async def upload_file(
        self,
        file_data: BytesIO,
        object_name: str,
        namespace: str,
        content_type: str,
    ) -> FileUploadResult:
        _namespace = self._ensure_valid_namespace(namespace)
        logger.info("Uploading file", bucket_name=_namespace, object_name=object_name)
        object_bytes = file_data.getvalue()
        try:
            await self.ensure_namespace_exists(namespace=_namespace)
            await self.clients.internal.put_object(
                Bucket=_namespace,
                Key=object_name,
                Body=object_bytes,
                ContentType=content_type,
            )
            upload_result = FileUploadResult(
                url=self.get_access_url(object_name=object_name, namespace=_namespace),
                bucket=_namespace,
                object_name=object_name,
                size=len(object_bytes),
            )
        except ClientError as e:
            logger.exception(
                "S3 upload failed",
                bucket_name=_namespace,
                object_name=object_name,
            )
            raise FileClientInternalError(message="File upload failed") from e
        else:
            logger.info(
                "File uploaded successfully",
                result=upload_result,
            )
            return upload_result

    async def delete_file(self, object_name: str, namespace: str) -> None:
        _namespace = self._ensure_valid_namespace(namespace)
        logger.info("Deleting file", bucket_name=_namespace, object_name=object_name)
        try:
            await self.clients.internal.delete_object(Bucket=_namespace, Key=object_name)
        except (BotoCoreError, ClientError) as e:
            logger.exception(
                "S3 delete failed",
                bucket_name=_namespace,
                object_name=object_name,
            )
            raise FileClientInternalError(message="File delete failed") from e

    async def init_storage(self) -> None:
        logger.info("Initializing storage")
        await self.ensure_namespace_exists(namespace="media")
        logger.info("Storage initialized successfully")

    def get_access_url(self, object_name: str, namespace: str) -> str:
        _namespace = self._ensure_valid_namespace(namespace)
        return settings.minio.get_object_url(bucket=_namespace, object_path=object_name)

    async def _bucket_exists(self, bucket_name: str) -> bool:
        try:
            await self.clients.internal.head_bucket(Bucket=bucket_name)
        except ClientError as exc:
            if self._is_bucket_not_found(exc):
                return False
            raise
        return True

    @staticmethod
    def _is_bucket_not_found(exc: ClientError) -> bool:
        error_matches = False
        status_matches = False
        with suppress(KeyError):
            error_matches = str(exc.response["Error"]["Code"]) in {
                "404",
                "NoSuchBucket",
                "NotFound",
            }
        with suppress(KeyError):
            status_matches = (
                exc.response["ResponseMetadata"]["HTTPStatusCode"] == HTTPStatus.NOT_FOUND
            )
        return error_matches or status_matches

    @staticmethod
    def _is_operation_not_implemented(exc: ClientError) -> bool:
        with suppress(KeyError):
            return str(exc.response["Error"]["Code"]) == "NotImplemented"
        return False
