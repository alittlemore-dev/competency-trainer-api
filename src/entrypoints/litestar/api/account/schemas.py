from typing import Annotated, Self

from pydantic import Field

from core.auth.enums import RoleEnum
from core.auth.schemas import BaseUser
from entrypoints.litestar.api.schemas import CamelCaseSchema


class GetBaseCurrentUserAccountResponseSchema(CamelCaseSchema):
    username: Annotated[
        str,
        Field(
            title="Username",
            description="Username",
            examples=["user1"],
        ),
    ]
    role: Annotated[
        RoleEnum,
        Field(
            title="User role",
            description="User role",
            examples=[RoleEnum.USER],
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: BaseUser) -> Self:
        return cls(
            username=schema.username,
            role=schema.role,
        )
