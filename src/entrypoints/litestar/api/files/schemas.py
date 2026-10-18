from datetime import datetime
from typing import Annotated, Self

from litestar.datastructures.upload_file import UploadFile
from pydantic import ConfigDict, Field, HttpUrl

from core.files.enums import FilePurpose
from core.files.schemas import FileRead
from entrypoints.litestar.api.parameters import MultipartFileMediaTypes
from entrypoints.litestar.api.schemas import CamelCaseSchema


class FileUploadRequestSchema(CamelCaseSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    purpose: Annotated[
        FilePurpose,
        Field(
            title="File purpose",
            examples=["articleCoverImage"],
            description=(
                "Purpose controls storage path, accepted MIME types, image "
                "processing, and upload size limit."
            ),
        ),
    ]
    name: Annotated[
        str,
        Field(
            title="Display name",
            examples=["Asyncio article cover"],
            description="Human-readable managed file label.",
        ),
    ]
    file: Annotated[
        UploadFile,
        MultipartFileMediaTypes(content_types=("*/*",)),
        Field(
            title="Uploaded file",
            description=(
                "Binary file part with an original filename and Content-Type. "
                "Article images accept "
                "image/png, image/jpeg, image/webp, image/gif up to 5 MiB. Attachments accept any "
                "MIME type up to 20 MiB, including application/pdf and "
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document."
            ),
        ),
    ]


class FileResponseSchema(CamelCaseSchema):
    id: Annotated[
        str,
        Field(
            title="File ID",
            examples=["1b734fe27bc04ace9f2c18fa26ad5081"],
            description="Stable entity identifier.",
        ),
    ]
    purpose: Annotated[
        FilePurpose,
        Field(
            title="File purpose",
            examples=["articleCoverImage"],
            description=(
                "Purpose controls storage path, accepted MIME types, image "
                "processing, and upload size limit."
            ),
        ),
    ]
    namespace: Annotated[
        str,
        Field(
            title="Storage namespace",
            examples=["media"],
            description="Object-storage namespace containing the file.",
        ),
    ]
    relative_path: Annotated[
        str,
        Field(
            title="Storage-relative object path",
            examples=["article-cover-images/2026/10/asyncio-cover.webp"],
            description="Object key within the storage namespace.",
        ),
    ]
    mime_type: Annotated[
        str,
        Field(
            title="MIME type",
            examples=[
                "image/webp",
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ],
            description=(
                "Stored object MIME type. Images may be optimized to image/webp; "
                "attachments retain their upload MIME."
            ),
        ),
    ]
    size_bytes: Annotated[
        int,
        Field(
            title="File size in bytes",
            examples=[128430],
            description="Stored object size in bytes, after any image optimization.",
        ),
    ]
    name: Annotated[
        str,
        Field(
            title="Display name",
            examples=["Asyncio article cover"],
            description="Human-readable managed file label.",
        ),
    ]
    original_name: Annotated[
        str,
        Field(
            title="Original upload name",
            examples=["asyncio-cover.png"],
            description="Original client-supplied upload filename.",
        ),
    ]
    access_url: Annotated[
        HttpUrl,
        Field(
            title="Access URL",
            description="Uploaded file access URL",
            examples=[
                "https://media.alittlemore.dev/article-cover-images/2026/10/asyncio-cover.webp"
            ],
        ),
    ]
    markdown_url: Annotated[
        HttpUrl,
        Field(
            title="Markdown URL",
            description="File URL with the file ID marker for markdown content.",
            examples=[
                "https://media.alittlemore.dev/article-cover-images/2026/10/asyncio-cover.webp#fileId=1b734fe27bc04ace9f2c18fa26ad5081"
            ],
        ),
    ]
    created_at: Annotated[
        datetime,
        Field(
            title="Created at",
            examples=["2026-10-12T09:30:00+00:00"],
            description="Creation timestamp in ISO 8601 format.",
        ),
    ]
    updated_at: Annotated[
        datetime,
        Field(
            title="Updated at",
            examples=["2026-10-15T14:20:00+00:00"],
            description="Last update timestamp in ISO 8601 format.",
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: FileRead) -> Self:
        return cls(
            id=schema.file.id,
            purpose=schema.file.purpose,
            namespace=schema.file.namespace,
            relative_path=schema.file.relative_path,
            mime_type=schema.file.mime_type,
            size_bytes=schema.file.size_bytes,
            name=schema.file.name,
            original_name=schema.file.original_name,
            access_url=HttpUrl(schema.access_url),
            markdown_url=HttpUrl(schema.markdown_url),
            created_at=schema.file.created_at,
            updated_at=schema.file.updated_at,
        )


class FilesResponseSchema(CamelCaseSchema):
    files: Annotated[list[FileResponseSchema], Field(title="Files")]

    @classmethod
    def from_domain_schema(cls, *, schema: list[FileRead]) -> Self:
        return cls(
            files=[FileResponseSchema.from_domain_schema(schema=file) for file in schema],
        )


class FileUpdateRequestSchema(CamelCaseSchema):
    name: Annotated[
        str,
        Field(
            title="Display name",
            examples=["Asyncio article cover"],
            description="Human-readable managed file label.",
        ),
    ]
