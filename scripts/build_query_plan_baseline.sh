#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$script_dir/common.sh"
cd "$backend_dir"

source_sha="${1:?source SHA is required}"
output_path="${2:?output path is required}"
summary_1="${3:?first summary path is required}"
summary_2="${4:?second summary path is required}"
summary_3="${5:?third summary path is required}"
summary_4="${6:?fourth summary path is required}"
summary_5="${7:?fifth summary path is required}"

ensure_backend_deps
PYTHONPATH=src uv run --locked --all-groups python -m performance.query_plans.baseline \
    --source-sha "$source_sha" \
    --output "$output_path" \
    --summary "$summary_1" \
    --summary "$summary_2" \
    --summary "$summary_3" \
    --summary "$summary_4" \
    --summary "$summary_5"
