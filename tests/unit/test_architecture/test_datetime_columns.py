from datetime import datetime

from sqlalchemy_dev_utils.types.datetime import UTCDateTime

from infra.postgresql.models import BaseModel


def test_all_datetime_columns_use_utc_datetime_type() -> None:
    datetime_columns = []
    for table in BaseModel.metadata.sorted_tables:
        for column in table.columns:
            try:
                python_type = column.type.python_type
            except NotImplementedError:
                continue
            if python_type is datetime:
                datetime_columns.append(column)

    assert datetime_columns
    assert [
        f"{column.table.name}.{column.name}"
        for column in datetime_columns
        if not isinstance(column.type, UTCDateTime)
    ] == []
