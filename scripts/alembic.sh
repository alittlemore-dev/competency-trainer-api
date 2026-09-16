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

action="${1:?action is required}"
alembic_config="src/infra/postgresql/alembic/alembic.ini"

require_uv

case "$action" in
    revision)
        message="${2:-}"
        if [ -z "$message" ]; then
            echo 'Migration message is required. Use: make revision message="describe change"' >&2
            exit 2
        fi
        PYTHONPATH=src uv run alembic -c "$alembic_config" revision -m "$message" --autogenerate
        ;;
    migrate)
        PYTHONPATH=src uv run alembic -c "$alembic_config" upgrade head
        ;;
    downgrade)
        PYTHONPATH=src uv run alembic -c "$alembic_config" downgrade -1
        ;;
    *)
        echo "Unknown Alembic action: $action" >&2
        exit 2
        ;;
esac
