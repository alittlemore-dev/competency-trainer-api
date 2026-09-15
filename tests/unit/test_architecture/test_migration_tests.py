import ast
from pathlib import Path


class TestMigrationTestBoundaries:
    def test_migration_tests_do_not_import_application_orm_models(self) -> None:
        tests_root = Path(__file__).parents[2]
        migrations_root = tests_root / "migrations"
        offenders: list[str] = []

        for path in sorted(migrations_root.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    offenders.extend(
                        self._format_offender(
                            tests_root=tests_root,
                            path=path,
                            line=node.lineno,
                            module=alias.name,
                        )
                        for alias in node.names
                        if alias.name == "infra.postgresql.models"
                        or alias.name.startswith("infra.postgresql.models.")
                    )
                if isinstance(node, ast.ImportFrom):
                    if node.module is None:
                        continue
                    if node.module == "infra.postgresql" and any(
                        alias.name == "models" for alias in node.names
                    ):
                        offenders.append(
                            self._format_offender(
                                tests_root=tests_root,
                                path=path,
                                line=node.lineno,
                                module=f"{node.module}.models",
                            ),
                        )
                    if node.module == "infra.postgresql.models" or node.module.startswith(
                        "infra.postgresql.models.",
                    ):
                        offenders.append(
                            self._format_offender(
                                tests_root=tests_root,
                                path=path,
                                line=node.lineno,
                                module=node.module,
                            ),
                        )

        assert offenders == []

    def test_migration_tests_do_not_use_raw_sql_helpers(self) -> None:
        tests_root = Path(__file__).parents[2]
        migrations_root = tests_root / "migrations"
        offenders: list[str] = []

        for path in sorted(migrations_root.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            sqlalchemy_aliases: set[str] = set()
            text_aliases: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    sqlalchemy_aliases.update(
                        alias.asname or alias.name
                        for alias in node.names
                        if alias.name == "sqlalchemy"
                    )
                if isinstance(node, ast.ImportFrom) and node.module == "sqlalchemy":
                    text_aliases.update(
                        alias.asname or alias.name for alias in node.names if alias.name == "text"
                    )
                    offenders.extend(
                        self._format_offender(
                            tests_root=tests_root,
                            path=path,
                            line=node.lineno,
                            module=f"{node.module}.{alias.name}",
                        )
                        for alias in node.names
                        if alias.name == "text"
                    )
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id in text_aliases:
                        offenders.append(
                            self._format_offender(
                                tests_root=tests_root,
                                path=path,
                                line=node.lineno,
                                module=node.func.id,
                            ),
                        )
                    if (
                        isinstance(node.func, ast.Attribute)
                        and node.func.attr == "text"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in sqlalchemy_aliases
                    ):
                        offenders.append(
                            self._format_offender(
                                tests_root=tests_root,
                                path=path,
                                line=node.lineno,
                                module=f"{node.func.value.id}.{node.func.attr}",
                            ),
                        )
                    if isinstance(node.func, ast.Attribute) and node.func.attr == "exec_driver_sql":
                        offenders.append(
                            self._format_offender(
                                tests_root=tests_root,
                                path=path,
                                line=node.lineno,
                                module=node.func.attr,
                            ),
                        )

        assert offenders == []

    @staticmethod
    def _format_offender(*, tests_root: Path, path: Path, line: int, module: str) -> str:
        return f"{path.relative_to(tests_root)}:{line}:{module}"
