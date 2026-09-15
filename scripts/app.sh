#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
backend_dir="$(cd -- "${script_dir}/.." && pwd)"
cd "$backend_dir"

require_uv() {
    if ! command -v uv >/dev/null 2>&1; then
        echo "UV could not be found." >&2
        exit 2
    fi
}

run_cli() {
    PYTHONPATH=src LITESTAR_APP="cli:create_cli" uv run litestar "$@"
}

action="${1:?action is required}"
shift

require_uv

case "$action" in
    run)
        PYTHONPATH=src uv run granian --interface asgi --factory --host 0.0.0.0 --port 8080 main:create_app
        ;;
    run-local)
        PYTHONPATH=src APP_DEBUG=true DB_HOST=localhost MINIO_HOST=localhost VALKEY_HOST=localhost \
            uv run granian --interface asgi --factory --host localhost --port 8000 --reload main:create_app
        ;;
    cli)
        run_cli "$@"
        ;;
    collectstatic)
        run_cli collectstatic
        ;;
    initbuckets)
        run_cli initbuckets
        ;;
    taskiq-worker)
        PYTHONPATH=src uv run taskiq worker entrypoints.taskiq.worker:broker
        ;;
    taskiq-scheduler)
        PYTHONPATH=src uv run taskiq scheduler entrypoints.taskiq.worker:scheduler
        ;;
    shell)
        PYTHONPATH=src uv run ipython --no-confirm-exit --no-banner --quick \
            --InteractiveShellApp.extensions="autoreload" \
            --InteractiveShellApp.exec_lines="%autoreload 2"
        ;;
    *)
        echo "Unknown app action: $action" >&2
        exit 2
        ;;
esac
