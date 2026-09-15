from typing import Annotated

from litestar.params import PathParameter

CacheWarmOperationIdPath = Annotated[
    str,
    PathParameter(name="operation_id", min_length=1, max_length=64),
]
