#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$script_dir/common.sh"
cd "$backend_dir"

run_bandit() {
    uv run bandit --configfile ./pyproject.toml -r ./src -lll -ii
}

run_pip_audit() {
    local cache_dir

    cache_dir="$(mktemp -d)"
    trap "rm -rf '${cache_dir}'" RETURN
    uv run pip-audit --local --strict --progress-spinner off --cache-dir "$cache_dir"
}

action="${1:?action is required}"

ensure_backend_deps

case "$action" in
    bandit)
        run_bandit
        ;;
    pip-audit)
        run_pip_audit
        ;;
    security)
        run_bandit
        run_pip_audit
        ;;
    *)
        echo "Unknown security action: $action" >&2
        exit 2
        ;;
esac
