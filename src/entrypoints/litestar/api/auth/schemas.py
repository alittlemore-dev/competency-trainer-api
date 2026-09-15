from typing import Annotated, Self

from pydantic import Field

from core.auth.schemas import AccessTokenResult
from entrypoints.litestar.api.schemas import CamelCaseSchema

PASETO_TOKEN_EXAMPLE = (
    "v2.public.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUs"  # noqa: S105  # nosec B105
    "ImlhdCI6IjIwMjYtMDEtMTVUMTM6MTY6MjQuMjI3WiIsImV4cCI6IjIwMjYtMDEtMTVUMTQ6MTY6Mj"
    "QuMjI3WiJ9gVOhHyX5I9118FXWTEd6S2npWqVnLVeytx0QJQNSWvhU-E-lBHYJOzZ6le94jb5SPfPO"
    "JY0EOZMcYuc6AXPQAA.eyJraWQiOiJ0b2tlbi1kZXYtMTIzIn0"
)


class AccessTokenResponseSchema(CamelCaseSchema):
    access_token: Annotated[
        str,
        Field(
            title="Access token",
            description="PASETO authorization token",
            examples=[PASETO_TOKEN_EXAMPLE],
        ),
    ]
    access_token_expires_in_seconds: Annotated[
        int,
        Field(
            title="Access token expiration seconds",
            description="Short-lived PASETO access token lifetime in seconds.",
            examples=[900],
        ),
    ]

    @classmethod
    def from_domain_schema(cls, *, schema: AccessTokenResult) -> Self:
        return cls(
            access_token=schema.token.decode(),
            access_token_expires_in_seconds=schema.expires_in_seconds,
        )


class LoginRequestSchema(CamelCaseSchema):
    username: Annotated[
        str,
        Field(),
    ]
    password: Annotated[
        str,
        Field(),
    ]
