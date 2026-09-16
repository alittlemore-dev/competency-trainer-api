#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"
env_file="${repo_dir}/.env.agent-bridge"

if [ ! -f "$env_file" ]; then
    echo ".env.agent-bridge could not be found." >&2
    echo "Copy .env.agent-bridge.example to .env.agent-bridge and fill the absolute paths." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv could not be found." >&2
    exit 2
fi

set -a
# shellcheck source=/dev/null
. "$env_file"
set +a

cd "$repo_dir"
exec env PYTHONPATH="${repo_dir}/src" \
    uv run --project "${repo_dir}" python -m agent_bridge
