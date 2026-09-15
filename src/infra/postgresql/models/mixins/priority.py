from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.orm.decl_api import declarative_mixin
from sqlalchemy_dev_utils.mixins.base import BaseModelMixin


@declarative_mixin
class PriorityMixin(BaseModelMixin):
    __abstract__ = True

    priority: Mapped[int] = mapped_column(
        Integer,
        doc="Lower values are shown first within an ordered sibling list",
    )
