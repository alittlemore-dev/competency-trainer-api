from datetime import datetime
from typing import Annotated, Self

from litestar.datastructures.upload_file import UploadFile
from pydantic import ConfigDict, Field, HttpUrl

from core.files.enums import FilePurpose
from core.files.schemas import FileRead
from entrypoints.litestar.api.schemas import CamelCaseSchema


class FileUploadRequestSchema(CamelCaseSchema):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    purpose: Annotated[FilePurpose, Field(title="File purpose")]
    name: Annotated[str, Field(title="Display name")]
    file: Annotated[UploadFile, Field(title="Uploaded file")]


class FileResponseSchema(CamelCaseSchema):
    id: Annotated[str, Field(title="File ID")]
    purpose: Annotated[FilePurpose, Field(title="File purpose")]
    namespace: Annotated[str, Field(title="Storage namespace")]
    relative_path: Annotated[str, Field(title="Storage-relative object path")]
    mime_type: Annotated[str, Field(title="MIME type")]
    size_bytes: Annotated[int, Field(title="File size in bytes")]
    name: Annotated[str, Field(title="Display name")]
    original_name: Annotated[str, Field(title="Original upload name")]
    access_url: Annotated[
        HttpUrl,
        Field(
            title="Access URL",
            description="Uploaded file access URL",
            examples=["https://example.com/path/to/file"],
        ),
    ]
    markdown_url: Annotated[
        HttpUrl,
        Field(
            title="Markdown URL",
            description="File URL with the file ID marker for markdown content.",
            examples=["https://example.com/path/to/file#fileId=00000000000000000000000000000001"],
        ),
    ]
    created_at: Annotated[datetime, Field(title="Created at")]
    updated_at: Annotated[datetime, Field(title="Updated at")]

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
    name: Annotated[str, Field(title="Display name")]
