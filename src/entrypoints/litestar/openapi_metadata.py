from dataclasses import dataclass
from functools import cache
from typing import cast

from litestar import Litestar, status_codes
from litestar._openapi.plugin import OpenAPIPlugin
from litestar.handlers.http_handlers import HTTPRouteHandler
from litestar.openapi.spec import (
    Components,
    Encoding,
    Example,
    OpenAPI,
    Operation,
    RequestBody,
    Schema,
)
from litestar.params import BodyKwarg
from litestar.routes.http import HTTPRoute
from pydantic import BaseModel

from entrypoints.litestar.api.parameters import MultipartFileMediaTypes
from entrypoints.litestar.openapi_errors import (
    ERROR_SCHEMA_NAME,
    build_error_response,
    build_error_schema,
)


@dataclass(frozen=True)
class RequestBodyMetadata:
    description: str
    examples: dict[str, Example]


@cache
def install_openapi_request_body_metadata() -> None:
    build_openapi = OpenAPIPlugin._build_openapi  # noqa: SLF001

    def build_openapi_with_request_body_metadata(plugin: OpenAPIPlugin) -> OpenAPI:
        openapi_schema = build_openapi(plugin)
        apply_openapi_request_body_metadata(app=plugin.app, openapi_schema=openapi_schema)
        return openapi_schema

    setattr(  # noqa: B010
        OpenAPIPlugin,
        "_build_openapi",
        build_openapi_with_request_body_metadata,
    )


def apply_openapi_request_body_metadata(
    *,
    app: Litestar,
    openapi_schema: OpenAPI,
) -> None:
    if openapi_schema.paths is None:
        return

    if openapi_schema.components is None:
        openapi_schema.components = Components()
    if openapi_schema.components.schemas is None:
        openapi_schema.components.schemas = {}
    openapi_schema.components.schemas[ERROR_SCHEMA_NAME] = build_error_schema()

    for route in app.routes:
        if not isinstance(route, HTTPRoute) or route.path_format is None:
            continue
        path_item = openapi_schema.paths.get(route.path_format)
        if path_item is None:
            continue
        for route_handler in route.route_handlers:
            for method in route_handler.http_methods:
                operation = cast("Operation | None", getattr(path_item, method.lower()))
                if operation is not None:
                    apply_operation_error_metadata(operation=operation, handler=route_handler)
                    apply_handler_body_metadata(
                        operation=operation, handler=route_handler, openapi_schema=openapi_schema
                    )


def apply_operation_error_metadata(*, operation: Operation, handler: HTTPRouteHandler) -> None:
    if operation.responses is None:
        operation.responses = {}
    error_descriptions = {
        500: "An unexpected application or dependency failure prevented completion.",
        **handler.opt.get("openapi_errors", {}),
    }
    if "400" in operation.responses:
        error_descriptions.setdefault(
            400,
            "Invalid request: a required field is missing, a value fails validation, "
            "or the operation's input rules are not satisfied. Request validation "
            "uses HTTP 400, including missing required query parameters.",
        )
    optional_auth = handler.opt.get("auth_optional") is True
    if optional_auth:
        operation.security = [{}, {"bearerAuth": []}]
    if operation.security:
        error_descriptions.update(
            {
                401: (
                    "The supplied authentication credential is expired or invalid. "
                    "Omit Authorization to use this operation anonymously."
                    if optional_auth
                    else "Authentication is missing, expired, or invalid."
                ),
                403: "The user role or personal API token permissions do not allow this action.",
                503: "The authentication service is temporarily unavailable.",
            }
        )
    for status_code, description in error_descriptions.items():
        response_description = description
        if status_code == status_codes.HTTP_400_BAD_REQUEST and "400" in operation.responses:
            response_description = "Missing or invalid request parameters or body. " + description
        operation.responses[str(status_code)] = build_error_response(
            status_code=status_code,
            description=response_description,
        )


def apply_handler_body_metadata(
    *, operation: Operation, handler: HTTPRouteHandler, openapi_schema: OpenAPI
) -> None:
    signatures = [
        handler.parsed_fn_signature,
        *(provider.parsed_fn_signature for provider in handler.resolve_dependencies().values()),
    ]
    for signature in signatures:
        data_field = signature.parameters.get("data")
        if data_field is None or not isinstance(data_field.kwarg_definition, BodyKwarg):
            continue
        metadata = build_request_body_metadata(body_kwarg=data_field.kwarg_definition)
        if metadata is not None:
            apply_request_body_metadata(operation=operation, metadata=metadata)
        if isinstance(data_field.annotation, type) and issubclass(data_field.annotation, BaseModel):
            apply_multipart_encoding(operation=operation, model=data_field.annotation)
            apply_request_model_metadata(openapi_schema=openapi_schema, model=data_field.annotation)


def build_request_body_metadata(body_kwarg: BodyKwarg) -> RequestBodyMetadata | None:
    if body_kwarg.description is None or body_kwarg.examples is None:
        return None
    return RequestBodyMetadata(
        description=body_kwarg.description,
        examples=format_request_body_examples(examples=body_kwarg.examples),
    )


def format_request_body_examples(*, examples: list[Example]) -> dict[str, Example]:
    return {
        example.id or f"example{index}": example for index, example in enumerate(examples, start=1)
    }


def apply_request_body_metadata(
    *,
    operation: Operation,
    metadata: RequestBodyMetadata,
) -> None:
    if not isinstance(operation.request_body, RequestBody):
        return

    request_body = operation.request_body
    if request_body.description is None:
        request_body.description = metadata.description
    for media_type_schema in request_body.content.values():
        if media_type_schema.examples is None:
            media_type_schema.examples = dict(metadata.examples)


def apply_multipart_encoding(*, operation: Operation, model: type[BaseModel]) -> None:
    if not isinstance(operation.request_body, RequestBody):
        return
    multipart = operation.request_body.content.get("multipart/form-data")
    if multipart is None:
        return
    encoding = {}
    for name, field in model.model_fields.items():
        for metadata in field.metadata:
            if isinstance(metadata, MultipartFileMediaTypes):
                encoding[field.alias or name] = Encoding(
                    content_type=", ".join(metadata.content_types)
                )
    if encoding:
        multipart.encoding = encoding


def apply_request_model_metadata(*, openapi_schema: OpenAPI, model: type[BaseModel]) -> None:
    extra = model.model_config.get("json_schema_extra")
    if not isinstance(extra, dict) or not isinstance(required := extra.get("required"), list):
        return
    if openapi_schema.components is None or openapi_schema.components.schemas is None:
        return
    schema = openapi_schema.components.schemas.get(model.__name__)
    if isinstance(schema, Schema):
        # Litestar's Pydantic plugin ignores model-level JSON Schema overrides.
        schema.required = [str(name) for name in required]
