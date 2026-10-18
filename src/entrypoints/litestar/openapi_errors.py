from typing import Any

from litestar.openapi.spec import Example, OpenAPIResponse, Reference, Schema
from litestar.openapi.spec.enums import OpenAPIType
from litestar.openapi.spec.media_type import OpenAPIMediaType
from verbose_http_exceptions import error_by_status_mapping

ERROR_SCHEMA_NAME = "VerboseHTTPError"
ERROR_SCHEMA_REFERENCE = Reference(ref=f"#/components/schemas/{ERROR_SCHEMA_NAME}")


class JSONExample(Example):
    def to_schema(self) -> dict[str, Any]:
        result = super().to_schema()
        # Litestar removes null dictionary entries, including required nullable JSON fields.
        if self.value is not None:
            result["value"] = self.value
        return result


def build_error_schema() -> Schema:
    return Schema(
        type=OpenAPIType.OBJECT,
        description=(
            "JSON error returned by the HTTP exception handlers. The keys keep their original "
            "snake_case spelling. A single validation issue may be returned directly; multiple "
            "issues are grouped in nested_errors. location and attr are null when the failure "
            "does not identify a request field. HTTP status is carried by the response status."
        ),
        required=["code", "type", "message", "location", "attr"],
        properties={
            "code": Schema(
                type=OpenAPIType.STRING,
                description="Error category; validation_error identifies request validation.",
                examples=["validation_error", "client_error"],
            ),
            "type": Schema(
                type=OpenAPIType.STRING,
                description="Specific error identifier within the category.",
                examples=["missing", "not_found"],
            ),
            "message": Schema(
                type=OpenAPIType.STRING,
                description="Human-readable explanation of the failure.",
                examples=["Article not found"],
            ),
            "location": Schema(
                type=[OpenAPIType.STRING, OpenAPIType.NULL],
                description="Request location associated with the error, or null.",
                examples=["query", "body", None],
            ),
            "attr": Schema(
                type=[OpenAPIType.STRING, OpenAPIType.NULL],
                description=(
                    "Invalid or missing field name, or null. Import errors may use file.row.N."
                ),
                examples=["pageSize", "file.row.2", None],
            ),
            "nested_errors": Schema(
                type=OpenAPIType.ARRAY,
                description="Present only when the error groups multiple issues.",
                items=ERROR_SCHEMA_REFERENCE,
            ),
        },
    )


def build_error_response(*, status_code: int, description: str) -> OpenAPIResponse:
    exception_type = error_by_status_mapping[status_code]
    examples: dict[str, Example | Reference] = {
        "error": JSONExample(value=exception_type().as_dict())
    }
    return OpenAPIResponse(
        description=description,
        content={
            "application/json": OpenAPIMediaType(
                schema=ERROR_SCHEMA_REFERENCE,
                examples=examples,
            ),
        },
    )
