#!/usr/bin/env bash
set -euo pipefail

action="${1:?action is required}"

load_secret_file() {
    local variable_name="$1"
    local file_variable_name="${variable_name}_FILE"
    local file_path="${!file_variable_name:-}"

    if [ -z "$file_path" ]; then
        return
    fi
    if [ ! -r "$file_path" ]; then
        echo "${file_variable_name} points to an unreadable file: ${file_path}" >&2
        exit 1
    fi

    export "$variable_name=$(<"$file_path")"
    unset "$file_variable_name"
}

load_runtime_secrets() {
    local secret_variable_names=(
        "APP_SECRET_KEY"
        "AUTH_PRIVATE_KEY"
        "DB_PASSWORD"
        "MINIO_ACCESS_KEY"
        "MINIO_SECRET_KEY"
        "OWNER_INIT_PASSWORD"
        "SENTRY_DSN"
    )
    local variable_name

    for variable_name in "${secret_variable_names[@]}"; do
        load_secret_file "$variable_name"
    done

    local certificate_variable_name
    for certificate_variable_name in AUTH_PRIVATE_KEY AUTH_PUBLIC_KEY; do
        if [ -n "${!certificate_variable_name:-}" ]; then
            printf -v "$certificate_variable_name" "%b" "${!certificate_variable_name}"
            export "$certificate_variable_name"
        fi
    done
}

load_runtime_secrets

case "$action" in
    init)
        alembic -c src/infra/postgresql/alembic/alembic.ini upgrade head
        LITESTAR_APP=cli:create_cli litestar invalidatecache
        LITESTAR_APP=cli:create_cli litestar initbuckets
        ;;
    run)
        granian --interface asgi --factory --host 0.0.0.0 --port 8080 main:create_app
        ;;
    taskiq-worker)
        taskiq worker entrypoints.taskiq.worker:broker
        ;;
    taskiq-scheduler)
        taskiq scheduler entrypoints.taskiq.worker:scheduler
        ;;
    *)
        echo "Unknown application action: ${action}" >&2
        exit 2
        ;;
esac
