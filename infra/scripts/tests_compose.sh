#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/../.." && pwd)"
# shellcheck source=test_services.sh
. "$script_dir/test_services.sh"
cd "$repo_dir"

mode="${1:?mode is required}"
test_env_file="${TEST_ENV_FILE:-.env.test}"
status=0

ensure_test_db "$test_env_file"
trap cleanup_owned_test_db EXIT

case "$mode" in
    backend)
        make test TEST_ENV_FILE="$TEST_DB_ENV_FILE" || status=$?
        ;;
    all)
        make test TEST_ENV_FILE="$TEST_DB_ENV_FILE" || status=$?
        ;;
    *)
        echo "Unknown compose test mode: $mode" >&2
        exit 2
        ;;
esac

exit "$status"
