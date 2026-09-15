from datetime import datetime
from typing import Annotated

from dishka.integrations.litestar import DishkaRouter, FromDishka
from litestar import Controller, delete, get, post, put, status_codes

from core.files.exceptions import InvalidFileDataError
from core.files.schemas import FileUpdateParams, FileUploadParams
from core.files.services import FileService
from core.generators import HexUuidIdGenerator
from entrypoints.litestar.api.files.schemas import (
    FileResponseSchema,
    FilesResponseSchema,
    FileUpdateRequestSchema,
    FileUploadRequestSchema,
)
from entrypoints.litestar.api.parameters import (
    FileIdPath,
    FilePurposeQuery,
    api_json_body,
    api_multipart_body,
)
from entrypoints.litestar.guards import content_manager_guard


class FilesApiController(Controller):
    path = "/files"
    tags = ["admin files"]
    guards = [content_manager_guard]

    @post(
        "",
        description="Upload a managed file.",
        name="admin-files-upload-api-handler",
        status_code=status_codes.HTTP_201_CREATED,
    )
    async def upload_file(
        self,
        data: Annotated[
            FileUploadRequestSchema,
            api_multipart_body(
                title="File upload request",
                description="Multipart upload payload for a managed file.",
                examples=(
                    {
                        "purpose": "articleCoverImage",
                        "name": "Article cover",
                        "file": "cover.png",
                    },
                ),
            ),
        ],
        file_service: FromDishka[FileService],
        id_generator: FromDishka[HexUuidIdGenerator],
        current_datetime: FromDishka[datetime],
    ) -> FileResponseSchema:
        if data.file.filename is None:
            raise InvalidFileDataError
        file = await file_service.upload_file(
            params=FileUploadParams(
                id=id_generator.get_next(),
                purpose=data.purpose,
                name=data.name,
                original_name=data.file.filename,
                mime_type=data.file.content_type or "application/octet-stream",
                content=await data.file.read(),
            ),
            current_datetime=current_datetime,
        )
        return FileResponseSchema.from_domain_schema(schema=file)

    @get(
        "",
        description="List managed files.",
        name="admin-files-list-api-handler",
    )
    async def list_files(
        self,
        purpose: FilePurposeQuery,
        file_service: FromDishka[FileService],
    ) -> FilesResponseSchema:
        return FilesResponseSchema.from_domain_schema(
            schema=await file_service.list_files(purpose=purpose),
        )

    @get(
        "/{file_id:str}",
        description="Get managed file metadata.",
        name="admin-files-detail-api-handler",
    )
    async def get_file(
        self,
        file_id: FileIdPath,
        file_service: FromDishka[FileService],
    ) -> FileResponseSchema:
        return FileResponseSchema.from_domain_schema(
            schema=await file_service.get_file(file_id=file_id),
        )

    @put(
        "/{file_id:str}",
        description="Update managed file metadata.",
        name="admin-files-update-api-handler",
    )
    async def update_file(
        self,
        file_id: FileIdPath,
        data: Annotated[
            FileUpdateRequestSchema,
            api_json_body(
                title="File metadata update request",
                description="Managed file metadata replacement payload.",
                examples=({"name": "Article cover"},),
            ),
        ],
        file_service: FromDishka[FileService],
        current_datetime: FromDishka[datetime],
    ) -> FileResponseSchema:
        return FileResponseSchema.from_domain_schema(
            schema=await file_service.update_file(
                file_id=file_id,
                params=FileUpdateParams(name=data.name),
                current_datetime=current_datetime,
            ),
        )

    @delete(
        "/{file_id:str}",
        description="Delete a managed file.",
        name="admin-files-delete-api-handler",
        status_code=status_codes.HTTP_204_NO_CONTENT,
    )
    async def delete_file(
        self,
        file_id: FileIdPath,
        file_service: FromDishka[FileService],
    ) -> None:
        await file_service.delete_file(file_id=file_id)


admin_router = DishkaRouter("", route_handlers=[FilesApiController])
