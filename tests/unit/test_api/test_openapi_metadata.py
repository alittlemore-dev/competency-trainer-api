from collections.abc import Iterable, Mapping
from typing import Any

from litestar import Litestar


class TestOpenApiMetadata:
    def test_public_openapi_schema_excludes_admin_routes(self, app: Litestar) -> None:
        schema = app.openapi_schema.to_schema()
        admin_paths = sorted(path for path in schema["paths"] if path.startswith("/api/admin"))

        assert admin_paths == []
        assert "/api/auth/login" in schema["paths"]

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
