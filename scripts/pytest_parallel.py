from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha1
from pathlib import Path

_BACKEND_PYTEST_WORKERS_ENV = "BACKEND_PYTEST_WORKERS"
_POSTGRESQL_IDENTIFIER_MAX_BYTES = 63
_SAFE_POSTGRESQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

CommandRunner = Callable[[list[str]], str]


def parse_lscpu_physical_core_count(output: str) -> int:
    physical_cores: set[tuple[str, str]] = set()
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        columns = line.split(",")
        if len(columns) != 2:
            continue

        core_id, socket_id = columns
        if core_id and socket_id:
            physical_cores.add((socket_id, core_id))

    return len(physical_cores)


def detect_pytest_worker_count(
    env: Mapping[str, str],
    command_runner: CommandRunner,
    sysfs_cpu_root: Path,
) -> int:
    override = env.get(_BACKEND_PYTEST_WORKERS_ENV)
    if override is not None:
        return _parse_worker_count_override(override)

    lscpu_worker_count = _detect_from_lscpu(command_runner=command_runner)
    if lscpu_worker_count > 0:
        return lscpu_worker_count

    sysfs_worker_count = _detect_from_linux_sysfs(sysfs_cpu_root=sysfs_cpu_root)
    if sysfs_worker_count > 0:
        return sysfs_worker_count

    macos_worker_count = _detect_from_macos_sysctl(command_runner=command_runner)
    if macos_worker_count > 0:
        return macos_worker_count

    return 1


def build_worker_database_name(base_database_name: str, worker_id: str) -> str:
    safe_base_database_name = _validate_postgresql_identifier(base_database_name)
    if worker_id == "master":
        return safe_base_database_name

    safe_worker_id = _validate_postgresql_identifier(worker_id)
    return _validate_postgresql_identifier(f"{safe_base_database_name}_{safe_worker_id}")


def build_template_database_name(base_database_name: str, run_id: str) -> str:
    safe_base_database_name = _validate_postgresql_identifier(base_database_name)
    normalized_run_id = run_id.strip()
    if not normalized_run_id:
        raise ValueError("Template database run id must not be blank")

    run_hash = sha1(normalized_run_id.encode(), usedforsecurity=False).hexdigest()[:8]
    return _validate_postgresql_identifier(f"{safe_base_database_name}_template_{run_hash}")


def quote_postgresql_identifier(identifier: str) -> str:
    return f'"{_validate_postgresql_identifier(identifier)}"'


def run_command(command: list[str]) -> str:
    return subprocess.check_output(
        command,
        stderr=subprocess.DEVNULL,
        text=True,
    )


def main(argv: Sequence[str]) -> int:
    if len(argv) != 2 or argv[1] != "workers":
        print("Usage: pytest_parallel.py workers", file=sys.stderr)
        return 2

    print(
        detect_pytest_worker_count(
            env=os.environ,
            command_runner=run_command,
            sysfs_cpu_root=Path("/sys/devices/system/cpu"),
        ),
    )
    return 0


def _parse_worker_count_override(value: str) -> int:
    try:
        worker_count = int(value)
    except ValueError as exc:
        raise ValueError(
            f"{_BACKEND_PYTEST_WORKERS_ENV} must be a non-negative integer",
        ) from exc

    if worker_count < 0:
        raise ValueError(f"{_BACKEND_PYTEST_WORKERS_ENV} must be a non-negative integer")

    if worker_count <= 1:
        return 0

    return worker_count


def _detect_from_lscpu(command_runner: CommandRunner) -> int:
    try:
        return parse_lscpu_physical_core_count(command_runner(["lscpu", "-p=CORE,SOCKET"]))
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError):
        return 0


def _detect_from_linux_sysfs(sysfs_cpu_root: Path) -> int:
    physical_cores: set[tuple[str, str]] = set()
    for cpu_dir in sysfs_cpu_root.glob("cpu[0-9]*"):
        topology_dir = cpu_dir / "topology"
        package_id_file = topology_dir / "physical_package_id"
        core_id_file = topology_dir / "core_id"
        if not package_id_file.is_file() or not core_id_file.is_file():
            continue

        package_id = package_id_file.read_text(encoding="utf-8").strip()
        core_id = core_id_file.read_text(encoding="utf-8").strip()
        if package_id and core_id:
            physical_cores.add((package_id, core_id))

    return len(physical_cores)


def _detect_from_macos_sysctl(command_runner: CommandRunner) -> int:
    try:
        worker_count = int(command_runner(["sysctl", "-n", "hw.physicalcpu"]).strip())
    except (FileNotFoundError, PermissionError, subprocess.SubprocessError, ValueError):
        return 0

    return worker_count if worker_count > 0 else 0


def _validate_postgresql_identifier(identifier: str) -> str:
    if not _SAFE_POSTGRESQL_IDENTIFIER_RE.fullmatch(identifier):
        raise ValueError(f"Unsafe PostgreSQL identifier: {identifier!r}")

    if len(identifier.encode()) > _POSTGRESQL_IDENTIFIER_MAX_BYTES:
        raise ValueError(
            f"PostgreSQL identifier is too long: {identifier!r}",
        )

    return identifier


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
