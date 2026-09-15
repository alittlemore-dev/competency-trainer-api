import ast
import sys
from pathlib import Path


class TestCoreImportBoundaries:
    def test_core_imports_only_stdlib_and_core_modules(self) -> None:
        source_root = Path(__file__).parents[3] / "src"
        core_root = source_root / "core"
        allowed_top_level_modules = sys.stdlib_module_names | {"__future__", "core"}
        offenders: list[str] = []

        for path in sorted(core_root.rglob("*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    offenders.extend(
                        self._format_offender(
                            source_root=source_root,
                            path=path,
                            line=node.lineno,
                            module=alias.name,
                        )
                        for alias in node.names
                        if alias.name.split(".", maxsplit=1)[0] not in allowed_top_level_modules
                    )
                if isinstance(node, ast.ImportFrom):
                    if node.level > 0 or node.module is None:
                        continue
                    if node.module.split(".", maxsplit=1)[0] not in allowed_top_level_modules:
                        offenders.append(
                            self._format_offender(
                                source_root=source_root,
                                path=path,
                                line=node.lineno,
                                module=node.module,
                            ),
                        )

        assert offenders == []

    @staticmethod
    def _format_offender(*, source_root: Path, path: Path, line: int, module: str) -> str:
        return f"{path.relative_to(source_root)}:{line}:{module}"
