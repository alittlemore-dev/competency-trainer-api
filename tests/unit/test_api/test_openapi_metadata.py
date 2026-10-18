from collections.abc import Iterable, Mapping
from typing import Annotated, Any

from litestar import Litestar, post
from litestar.datastructures import UploadFile
from litestar.di import NamedDependency, Provide
from litestar.params import BodyKwarg
from litestar.routes.http import HTTPRoute
from litestar.testing import TestClient
from pydantic import BaseModel, TypeAdapter

from entrypoints.litestar.api.competency_matrix.schemas import (
    PublicQuestionSuggestionRequestSchema,
    QuestionSuggestionRequestSchema,
)
from entrypoints.litestar.api.parameters import api_json_body
from entrypoints.litestar.api.schemas import CamelCaseSchema, DetailResponseSchema


class TestOpenApiMetadata:
    def test_schema_is_anonymous_with_real_auth_plugin(self, sdk_auth_app: Litestar) -> None:
        with TestClient(sdk_auth_app) as client:
            response = client.get("/api/docs/openapi.json")
            assert response.status_code == 200
            assert "/api/articles" in response.json()["paths"]

    def test_openapi_schema_documents_protected_application_routes(self, app: Litestar) -> None:
        schema = app.openapi_schema.to_schema()
        admin_paths = sorted(path for path in schema["paths"] if path.startswith("/api/admin"))

        assert "/api/admin/articles" in admin_paths
        assert "/api/admin/competency-matrix/items" in admin_paths
        assert not any(path.startswith(("/api/auth", "/api/account")) for path in schema["paths"])

    def test_protected_operations_document_bearer_authentication(
        self, sdk_auth_app: Litestar
    ) -> None:
        schema = sdk_auth_app.openapi_schema.to_schema()
        protected_operations = [
            (path, method, operation)
            for path, method, operation in self._iter_operations(schema=schema)
            if path.startswith("/api/admin/")
        ]

        assert protected_operations
        assert {
            method for path, method, _ in protected_operations if path == "/api/admin/articles"
        } >= {
            "get",
            "post",
        }
        assert [
            f"{method.upper()} {path}"
            for path, method, operation in protected_operations
            if operation.get("security") != [{"bearerAuth": []}]
        ] == []
        assert schema["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"

    def test_public_operations_do_not_require_bearer_authentication(
        self, sdk_auth_app: Litestar
    ) -> None:
        schema = sdk_auth_app.openapi_schema.to_schema()

        assert [
            f"{method.upper()} {path}"
            for path, method, operation in self._iter_operations(schema=schema)
            if not path.startswith("/api/admin/")
            and operation.get("security")
            and {} not in operation["security"]
        ] == []

    def test_visible_parameters_include_descriptions_and_examples(self, app: Litestar) -> None:
        schema = app.openapi_schema.to_schema()
        missing_metadata = [
            f"{method.upper()} {path} parameter {parameter['in']}:{parameter['name']} "
            f"missing {', '.join(missing)}"
            for path, method, operation in self._iter_operations(schema=schema)
            for parameter in operation.get("parameters", ())
            if (missing := self._missing_parameter_metadata(parameter=parameter))
        ]

        assert missing_metadata == []

    def test_visible_request_bodies_include_descriptions_and_examples(self, app: Litestar) -> None:
        schema = app.openapi_schema.to_schema()
        missing_metadata = [
            f"{method.upper()} {path} request body missing {', '.join(missing)}"
            for path, method, operation in self._iter_operations(schema=schema)
            if (request_body := operation.get("requestBody")) is not None
            if (missing := self._missing_request_body_metadata(request_body=request_body))
        ]

        assert missing_metadata == []

    @staticmethod
    def _iter_operations(
        *,
        schema: Mapping[str, Any],
    ) -> Iterable[tuple[str, str, Mapping[str, Any]]]:
        for path, path_schema in schema["paths"].items():
            for method, operation in path_schema.items():
                if method in {"get", "post", "put", "patch", "delete"}:
                    yield path, method, operation

    @staticmethod
    def _missing_parameter_metadata(*, parameter: Mapping[str, Any]) -> list[str]:
        missing: list[str] = []
        if not parameter.get("description"):
            missing.append("description")
        parameter_schema = parameter.get("schema", {})
        if "examples" not in parameter_schema and "examples" not in parameter:
            missing.append("examples")
        return missing

    @staticmethod
    def _missing_request_body_metadata(*, request_body: Mapping[str, Any]) -> list[str]:
        missing: list[str] = []
        if not request_body.get("description"):
            missing.append("description")
        content = request_body.get("content", {})
        has_examples = any(
            "examples" in media_schema or "examples" in media_schema.get("schema", {})
            for media_schema in content.values()
        )
        if not has_examples:
            missing.append("examples")
        return missing

    def test_pagination_matches_required_runtime_contract(self, app: Litestar) -> None:
        schema = app.openapi_schema.to_schema()
        paginated = [
            operation
            for _, _, operation in self._iter_operations(schema=schema)
            if any(parameter["name"] == "page" for parameter in operation.get("parameters", []))
        ]
        assert paginated
        for operation in paginated:
            parameters = {parameter["name"]: parameter for parameter in operation["parameters"]}
            for name in ("page", "pageSize"):
                assert parameters[name]["required"] is True
                assert parameters[name]["schema"]["minimum"] == 1
                assert "default" not in parameters[name]["schema"]
            assert parameters["pageSize"]["schema"]["maximum"] == 100
            assert operation["responses"]["400"]["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/VerboseHTTPError"
            }
        with TestClient(app) as client:
            response = client.get("/api/articles", params={"language": "en", "pageSize": 20})
        assert response.status_code == 400
        assert set(response.json()) == {"code", "type", "message", "location", "attr"}
        assert response.json()["code"] == "validation_error"
        assert response.json()["attr"] == "page"
        assert response.json()["location"] == "query"

    def test_errors_document_actual_envelope_and_operation_specific_statuses(
        self, app: Litestar
    ) -> None:
        schema = app.openapi_schema.to_schema()
        error = schema["components"]["schemas"]["VerboseHTTPError"]
        assert set(error["required"]) == {"code", "type", "message", "location", "attr"}
        assert error["properties"]["nested_errors"]["items"] == {
            "$ref": "#/components/schemas/VerboseHTTPError"
        }
        assert error["properties"]["location"]["type"] == ["string", "null"]
        assert error["properties"]["attr"]["type"] == ["string", "null"]
        assert "status_code" not in error["properties"]
        paths = schema["paths"]
        assert "404" in paths["/api/articles/detail/{slug}"]["get"]["responses"]
        assert "409" not in paths["/api/articles"]["get"]["responses"]
        assert {"400", "409", "429"} <= set(
            paths["/api/competency-matrix/question-suggestions"]["post"]["responses"]
        )
        assert {"401", "403", "503"} <= set(paths["/api/admin/articles"]["get"]["responses"])
        optional = paths["/api/competency-matrix/question-suggestions"]["post"]
        assert optional["security"] == [{}, {"bearerAuth": []}]
        assert {"401", "403", "503"} <= set(optional["responses"])
        for _, _, operation in self._iter_operations(schema=schema):
            for status_code, response in operation["responses"].items():
                if status_code.isdigit() and int(status_code) >= 400:
                    content = response["content"]["application/json"]
                    assert content["schema"] == {"$ref": "#/components/schemas/VerboseHTTPError"}
                    for example in content["examples"].values():
                        assert set(error["required"]) <= set(example["value"])
                        assert example["value"]["location"] is None
                        assert example["value"]["attr"] is None

    def test_request_examples_validate_against_actual_request_models(self, app: Litestar) -> None:
        validated = 0
        for route in app.routes:
            if not isinstance(route, HTTPRoute):
                continue
            for handler in route.route_handlers:
                data = handler.parsed_fn_signature.parameters.get("data")
                if data is None or not isinstance(data.kwarg_definition, BodyKwarg):
                    continue
                model = data.annotation
                if not isinstance(model, type) or not issubclass(model, BaseModel):
                    continue
                for example in data.kwarg_definition.examples or []:
                    assert isinstance(example.value, dict)
                    value = dict(example.value)
                    upload = None
                    if "file" in value:
                        upload = UploadFile(
                            filename=value["file"], content_type="application/octet-stream"
                        )
                        value["file"] = upload
                    try:
                        model.model_validate(value)
                    finally:
                        if upload is not None:
                            upload.file.close()
                    validated += 1
        assert validated > 0
        schema = app.openapi_schema.to_schema()
        reaction = schema["paths"]["/api/articles/detail/{slug}/reaction"]["post"]["requestBody"]
        clear_example = reaction["content"]["application/json"]["examples"]["example2"]["value"]
        assert "reactionKind" in clear_example
        assert clear_example["reactionKind"] is None

    def test_uploads_document_binary_parts_and_real_mime_types(self, app: Litestar) -> None:
        schema = app.openapi_schema.to_schema()
        paths = schema["paths"]
        upload = paths["/api/admin/files"]["post"]["requestBody"]["content"]
        assert set(upload) == {"multipart/form-data"}
        assert upload["multipart/form-data"]["encoding"]["file"]["contentType"] == "*/*"
        for path in (
            "/api/admin/competency-matrix/queued-questions/import/preview",
            "/api/admin/competency-matrix/queued-questions/import",
        ):
            body = paths[path]["post"]["requestBody"]["content"]["multipart/form-data"]
            assert (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                in (body["encoding"]["file"]["contentType"])
            )
        upload_schema = schema["components"]["schemas"]["FileUploadRequestSchema"]
        assert upload_schema["properties"]["file"]["type"] == "string"
        assert upload_schema["properties"]["file"]["format"] == "binary"
        file_schema = schema["components"]["schemas"]["FileResponseSchema"]
        assert "application/pdf" in file_schema["properties"]["mimeType"]["examples"]
        assert (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            in (file_schema["properties"]["mimeType"]["examples"])
        )

    def test_field_examples_follow_the_actual_schema_types(self, app: Litestar) -> None:
        pending = list(CamelCaseSchema.__subclasses__())
        checked = set()
        validated = 0
        while pending:
            model = pending.pop()
            if model in checked:
                continue
            checked.add(model)
            pending.extend(model.__subclasses__())
            for field in model.model_fields.values():
                if field.examples:
                    adapter = TypeAdapter(field.rebuild_annotation())
                    for example in field.examples:
                        assert example != "string"
                        adapter.validate_python(example)
                        validated += 1
        assert validated > 0

    def test_multiple_validation_errors_use_the_documented_recursive_keys(
        self, app: Litestar
    ) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/api/contacts",
                json={"name": None, "email": "invalid", "telegram": "x", "message": ""},
            )
        assert response.status_code == 400
        error = response.json()
        assert set(error) == {"code", "type", "message", "location", "attr", "nested_errors"}
        assert len(error["nested_errors"]) > 1
        for issue in error["nested_errors"]:
            assert set(issue) == {"code", "type", "message", "location", "attr"}
            assert issue["location"] in {"body", None}

    def test_dependency_request_body_keeps_its_description_and_examples(
        self, app: Litestar
    ) -> None:
        def provide_payload(
            data: Annotated[
                DetailResponseSchema,
                api_json_body(
                    title="Operation result",
                    description="Result text supplied through a dependency.",
                    examples=({"detail": "Cache cleared successfully"},),
                ),
            ],
        ) -> DetailResponseSchema:
            return data

        @post(
            "/dependency-body",
            dependencies={"payload": Provide(provide_payload, sync_to_thread=False)},
        )
        async def dependency_body(
            payload: NamedDependency[DetailResponseSchema],
        ) -> DetailResponseSchema:
            return payload

        schema = Litestar(route_handlers=[dependency_body]).openapi_schema.to_schema()
        body = schema["paths"]["/dependency-body"]["post"]["requestBody"]
        assert body["description"] == "Result text supplied through a dependency."
        assert body["content"]["application/json"]["examples"]["example1"]["value"] == {
            "detail": "Cache cleared successfully"
        }

    def test_optional_queue_sheet_matches_runtime_without_weakening_public_suggestions(
        self, app: Litestar
    ) -> None:
        question = "How does asyncio.gather handle concurrent awaitables?"
        assert QuestionSuggestionRequestSchema.model_validate({"question": question}).sheet is None
        assert (
            PublicQuestionSuggestionRequestSchema.model_validate(
                {"question": question, "sheet": "python"}
            ).sheet
            == "python"
        )
        components = app.openapi_schema.to_schema()["components"]["schemas"]
        assert components["QuestionSuggestionRequestSchema"]["required"] == ["question"]
        assert set(components["PublicQuestionSuggestionRequestSchema"]["required"]) == {
            "question",
            "sheet",
        }
