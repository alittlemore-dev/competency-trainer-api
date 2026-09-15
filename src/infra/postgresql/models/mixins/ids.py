import uuid

from sqlalchemy import String, cast, func
from sqlalchemy.orm import Mapped, mapped_column, synonym
from sqlalchemy.orm.decl_api import declarative_mixin, declared_attr
from sqlalchemy_dev_utils.mixins.base import BaseModelMixin


def generate_uuid4_hex() -> str:
    return uuid.uuid4().hex


@declarative_mixin
class HexUuidIDMixin(BaseModelMixin):
    @declared_attr
    def id(cls) -> Mapped[str]:
        return mapped_column(
            String(length=32),
            primary_key=True,
            default=generate_uuid4_hex,
            server_default=func.replace(cast(func.gen_random_uuid(), String()), "-", ""),
            doc="UUIDv4 hex identifier",
        )

    @declared_attr
    def pk(cls) -> Mapped[str]:
        return synonym("id")
