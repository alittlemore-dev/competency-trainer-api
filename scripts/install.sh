#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$script_dir/common.sh"
cd "$backend_dir"

action="${1:?action is required}"

require_uv

case "$action" in
    install)
        invalidate_backend_deps_marker
        uv sync --locked --all-extras
        ;;
    *)
        echo "Unknown install action: $action" >&2
        exit 2
        ;;
esac
