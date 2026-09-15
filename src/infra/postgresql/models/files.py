from datetime import datetime
from typing import Self

from sqlalchemy import Enum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy_dev_utils.mixins.audit import AuditMixin
from sqlalchemy_dev_utils.types.datetime import UTCDateTime

from core.files.enums import FilePurpose
from core.files.schemas import StoredFile
from core.files.types import Namespace
from infra.postgresql.models.base import BaseModel, TableArgs
from infra.postgresql.models.mixins.ids import HexUuidIDMixin


class FileModel(HexUuidIDMixin, AuditMixin, BaseModel):
    purpose: Mapped[FilePurpose] = mapped_column(
        Enum(
            FilePurpose,
            native_enum=True,
            name="file_purpose_enum",
        ),
        doc="Business purpose that controls file validation and storage folder",
    )
    namespace: Mapped[Namespace] = mapped_column(
        String(length=63),
        doc="Object storage namespace or bucket",
    )
    relative_path: Mapped[str] = mapped_column(
        String(length=2048),
        doc="Object path relative to namespace",
    )
    mime_type: Mapped[str] = mapped_column(
        String(length=255),
        doc="Uploaded file MIME type",
    )
    size_bytes: Mapped[int] = mapped_column(
        doc="Uploaded file size in bytes",
    )
    name: Mapped[str] = mapped_column(
        String(length=255),
        doc="Display name",
    )
    original_name: Mapped[str] = mapped_column(
        String(length=255),
        doc="Original uploaded file name",
    )
    original_sha256: Mapped[str | None] = mapped_column(
        String(length=64),
        nullable=True,
        doc="SHA-256 hash of the original uploaded bytes, before processing",
    )
    orphaned_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(timezone=True),
        nullable=True,
        doc="UTC time when the managed public file lost its last usage",
    )

    @declared_attr.directive
    @classmethod
    def __table_args__(cls) -> TableArgs:
        return (
            UniqueConstraint(
                cls.namespace,
                cls.relative_path,
                name="files_file_namespace_relative_path_uniq",
            ),
            Index(
                "files_file_purpose_created_id_idx",
                cls.purpose,
                cls.created_at,
                cls.id,
            ),
            Index(
                "files_file_namespace_purpose_original_sha256_idx",
                cls.namespace,
                cls.purpose,
                cls.original_sha256,
            ),
            Index(
                "files_file_namespace_orphaned_id_idx",
                cls.namespace,
                cls.orphaned_at,
                cls.id,
                postgresql_where=cls.orphaned_at.is_not(None),
            ),
        )

    @classmethod
    def from_domain_schema(cls, file: StoredFile) -> Self:
        return cls(
            id=file.id,
            purpose=file.purpose,
            namespace=file.namespace,
            relative_path=file.relative_path,
            mime_type=file.mime_type,
            size_bytes=file.size_bytes,
            name=file.name,
            original_name=file.original_name,
            original_sha256=file.original_sha256,
            orphaned_at=file.orphaned_at,
            created_at=file.created_at,
            updated_at=file.updated_at,
        )

    def to_domain_schema(self) -> StoredFile:
        return StoredFile(
            id=self.id,
            purpose=self.purpose,
            namespace=self.namespace,
            relative_path=self.relative_path,
            mime_type=self.mime_type,
            size_bytes=self.size_bytes,
            name=self.name,
            original_name=self.original_name,
            original_sha256=self.original_sha256,
            orphaned_at=self.orphaned_at,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
