from typing import Annotated

import msgspec
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel as camel_case
from pydantic.alias_generators import to_snake as snake_case

from infra.config.constants import constants


class CamelCaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=camel_case,
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
    )

    def response_cache_payload(self) -> bytes:
        messages = [
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (
                        constants.response_cache.json_content_type_header_name,
                        constants.response_cache.json_content_type_header_value,
                    ),
                ],
            },
            {
                "type": "http.response.body",
                "body": self.model_dump_json(by_alias=True).encode(),
            },
        ]
        return msgspec.msgpack.encode(messages)


class SnakeCaseSchema(BaseModel):
    model_config = ConfigDict(
        alias_generator=snake_case,
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
    )


class DetailResponseSchema(CamelCaseSchema):
    detail: Annotated[
        str,
        Field(
            title="Message",
            description="Detailed operation result description",
            examples=["Operation completed successfully"],
        ),
    ]
