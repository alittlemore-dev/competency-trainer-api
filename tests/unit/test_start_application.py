import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_run_loads_app_secret_from_file_and_unsets_file_reference(tmp_path: Path) -> None:
    secret_file = tmp_path / "app_secret_key"
    secret_file.write_text("test-competency-secret\n", encoding="utf-8")
    runtime_log = tmp_path / "runtime.log"
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    granian = binary_dir / "granian"
    granian.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n%s\\n' \"$APP_SECRET_KEY\" "
        '"${APP_SECRET_KEY_FILE-unset}" >"$FAKE_RUNTIME_LOG"\n',
        encoding="utf-8",
    )
    granian.chmod(0o755)
    environment = os.environ.copy()
    environment.pop("APP_SECRET_KEY", None)
    environment.update(
        {
            "APP_SECRET_KEY_FILE": str(secret_file),
            "FAKE_RUNTIME_LOG": str(runtime_log),
            "PATH": f"{binary_dir}:{environment['PATH']}",
        }
    )

    result = subprocess.run(  # noqa: S603
        ["/bin/bash", str(ROOT / "start_application.sh"), "run"],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stderr
    assert runtime_log.read_text(encoding="utf-8") == "test-competency-secret\nunset\n"
