from typing import Annotated

from entrypoints.litestar.api.parameters import api_path_parameter

CacheWarmOperationIdPath = Annotated[
    str,
    api_path_parameter(
        name="operation_id",
        title="Cache warm operation ID",
        description="Identifier returned by a manual cache warm request.",
        examples=("operation-example",),
    ),
]
