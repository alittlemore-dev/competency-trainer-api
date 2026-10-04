#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$script_dir/common.sh"
cd "$backend_dir"

action="${1:?action is required}"
alembic_config="src/infra/postgresql/alembic/alembic.ini"

require_uv

if [ -n "${MIGRATION_ENV_FILE:-}" ]; then
    ensure_backend_deps
    TEST_ENV_FILE="$MIGRATION_ENV_FILE"
    ensure_backend_test_db
    trap cleanup_owned_test_db EXIT
    if [ "$action" = "revision" ]; then
        PYTHONPATH=src uv run alembic -c "$alembic_config" upgrade head
    fi
fi

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
