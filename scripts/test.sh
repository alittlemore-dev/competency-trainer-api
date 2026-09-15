#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
. "$script_dir/common.sh"
cd "$backend_dir"

action="${1:?action is required}"
TEST_ENV_FILE="${2:-${TEST_ENV_FILE:-.env.test}}"
TEST_ENV_OVERRIDES="${3:-${TEST_ENV_OVERRIDES:-}}"

ensure_backend_deps
load_env_file "$TEST_ENV_FILE"

pytest_worker_count() {
    uv run python scripts/pytest_parallel.py workers
}

pytest_template_run_id() {
    printf '%s_%s\n' "$(date -u +%Y%m%d%H%M%S%N)" "$$"
}

cleanup_pytest_template_database() {
    if [ -z "${BACKEND_PYTEST_DB_TEMPLATE_ID:-}" ]; then
        return
    fi

    run_with_test_env uv run python -m scripts.pytest_databases drop-template || true
    unset BACKEND_PYTEST_DB_TEMPLATE_ID
}

cleanup_test_resources() {
    cleanup_pytest_template_database
    cleanup_owned_test_db
}

run_pytest_parallel() {
    local workers
    local -a parallel_args

    workers="$(pytest_worker_count)"
    parallel_args=(-n "$workers")
    if [ "$workers" -gt 0 ]; then
        parallel_args+=(--dist worksteal)
    fi
    run_with_test_env uv run pytest --durations=10 -vvv -x "${parallel_args[@]}" "$@"
}

run_pytest_serial() {
    run_with_test_env uv run pytest --durations=10 -vvv -x -n 0 "$@"
}

run_pytest_integration_parallel() {
    BACKEND_PYTEST_DB_TEMPLATE_ID="$(pytest_template_run_id)"
    export BACKEND_PYTEST_DB_TEMPLATE_ID
    run_pytest_parallel tests/integration/
}

reset_base_test_database() {
    run_with_test_env uv run python -m scripts.pytest_databases reset-base
}

run_pytest_cov_parallel() {
    local workers
    local -a parallel_args

    workers="$(pytest_worker_count)"
    parallel_args=(-n "$workers")
    if [ "$workers" -gt 0 ]; then
        parallel_args+=(--dist worksteal)
    fi
    run_with_test_env uv run pytest \
        --cov=src \
        --cov-branch \
        --cov-report= \
        --cov-append \
        -x \
        "${parallel_args[@]}" \
        "$@"
}

run_pytest_cov_serial() {
    run_with_test_env uv run pytest \
        --cov=src \
        --cov-branch \
        --cov-report= \
        --cov-append \
        -x \
        -n 0 \
        "$@"
}

run_pytest_cov_integration_parallel() {
    BACKEND_PYTEST_DB_TEMPLATE_ID="$(pytest_template_run_id)"
    export BACKEND_PYTEST_DB_TEMPLATE_ID
    run_pytest_cov_parallel tests/integration/
}

case "$action" in
    test)
        run_pytest_parallel tests/unit/
        ensure_backend_test_db
        trap cleanup_test_resources EXIT
        run_pytest_integration_parallel
        reset_base_test_database
        run_pytest_serial tests/migrations/
        ;;
    test-unit)
        run_pytest_parallel tests/unit/
        ;;
    test-integration)
        ensure_backend_test_db
        trap cleanup_test_resources EXIT
        run_pytest_integration_parallel
        reset_base_test_database
        run_pytest_serial tests/migrations/
        ;;
    tests-coverage)
        run_with_test_env uv run coverage erase
        run_pytest_cov_parallel tests/unit/
        ensure_backend_test_db
        trap cleanup_test_resources EXIT
        run_pytest_cov_integration_parallel
        reset_base_test_database
        run_pytest_cov_serial tests/migrations/
        run_with_test_env uv run coverage xml
        run_with_test_env uv run coverage report --fail-under=85
        ;;
    *)
        echo "Unknown test action: $action" >&2
        exit 2
        ;;
esac
