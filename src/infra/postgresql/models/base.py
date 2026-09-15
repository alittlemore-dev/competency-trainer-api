from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.schema import SchemaItem
from sqlalchemy_dev_utils.mixins.general import BetterReprMixin, TableNameMixin

type TableArgs = tuple[SchemaItem, ...]


class BaseModel(BetterReprMixin, TableNameMixin, DeclarativeBase):
    __abstract__ = True
    __join_application_prefix__ = True
    __table_name_delimiter__ = "__"
