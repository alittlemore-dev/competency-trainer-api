#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/../.." && pwd)"
cd "$repo_dir"

# shellcheck source=compose_secrets.sh
. "$script_dir/compose_secrets.sh"

readonly COMPOSE_WAIT_TIMEOUT_SECONDS=180
readonly DEPLOY_DRAIN_SECONDS=10
readonly DEPLOY_STATE_DIR="${repo_dir}/.deploy-state"
readonly ACTIVE_SLOT_FILE="${DEPLOY_STATE_DIR}/active-slot"

require_command() {
    local command_name="$1"

    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "${command_name} could not be found. Install it." >&2
        exit 1
    fi
}

require_env() {
    local variable_name="$1"
    local message="${2:-${variable_name} must be set in .env.}"

    if [ -z "${!variable_name:-}" ]; then
        echo "$message" >&2
        exit 1
    fi
}

require_env_set() {
    local variable_name="$1"
    local message="${2:-${variable_name} must be set in .env.}"

    if [ "${!variable_name+x}" != "x" ]; then
        echo "$message" >&2
        exit 1
    fi
}

require_environment() {
    local required_variables=(
        "VPN_BIND_ADDRESS"
        "APP_URL_SCHEMA"
        "APP_DEBUG"
        "APP_DOMAIN"
        "APP_SECRET_KEY"
        "APP_USE_CACHE"
        "APP_CONTACT_REQUESTS_ENABLED"
        "OWNER_INIT_LOGIN"
        "OWNER_INIT_PASSWORD"
        "DB_USER"
        "DB_PASSWORD"
        "DB_DRIVER"
        "DB_HOST"
        "DB_PORT"
        "DB_NAME"
        "DB_POOL_PRE_PING"
        "DB_POOL_SIZE"
        "DB_MAX_OVERFLOW"
        "DB_EXPIRE_ON_COMMIT"
        "DB_LOG_QUERY_METRICS"
        "DB_SLOW_QUERY_LOG_THRESHOLD_MS"
        "DB_SLOW_QUERY_LOG_STATEMENT_MAX_LENGTH"
        "AUTH_TOKEN_EXPIRE_SECONDS"
        "AUTH_SESSION_EXPIRE_SECONDS"
        "AUTH_SESSION_ABSOLUTE_EXPIRE_SECONDS"
        "AUTH_TOKEN_HEADER_NAME"
        "AUTH_TOKEN_PREFIX"
        "AUTH_PUBLIC_KEY"
        "AUTH_PRIVATE_KEY"
        "MINIO_HOST"
        "MINIO_PORT"
        "MINIO_REGION"
        "MINIO_SECRET_KEY"
        "MINIO_ACCESS_KEY"
        "MINIO_SECURE"
        "MINIO_PUBLIC_URL"
        "MINIO_CORS_MAX_AGE_SECONDS"
        "FILES_ORPHAN_RETENTION_SECONDS"
        "SENTRY_USE"
        "SENTRY_DSN"
        "VALKEY_HOST"
        "VALKEY_PORT"
        "I18N_DEFAULT_LANGUAGE"
        "COMPETENCY_MATRIX_QUESTION_SUGGESTION_ANONYMOUS_DAILY_LIMIT"
        "AGENT_ACCESS_ISSUING_CERTIFICATE"
        "AGENT_ACCESS_ISSUING_PRIVATE_KEY"
        "AGENT_ACCESS_CERTIFICATE_CHAIN"
        "TASKIQ_AUTH_SESSION_PRUNE_INTERVAL_SECONDS"
        "TASKIQ_AGENT_AUDIT_PRUNE_INTERVAL_SECONDS"
        "TASKIQ_CACHE_WARM_INTERVAL_SECONDS"
        "TASKIQ_FILE_ORPHAN_PRUNE_INTERVAL_SECONDS"
        "TASKIQ_RESULT_EXPIRE_SECONDS"
        "CACHE_WARM_ARTICLES_PAGE_SIZE"
        "LE_EMAIL"
        "SSL_CERT"
        "SSL_KEY"
        "IMAGE_TAG"
    )

    for variable_name in "${required_variables[@]}"; do
        if [ "$variable_name" = "VPN_BIND_ADDRESS" ]; then
            require_env "$variable_name" "VPN_BIND_ADDRESS must be set in .env."
            continue
        fi
        if [ "$variable_name" = "SENTRY_DSN" ]; then
            require_env_set "$variable_name"
            continue
        fi
        require_env "$variable_name"
    done
}

other_slot() {
    local slot="$1"

    case "$slot" in
        blue)
            printf '%s\n' "green"
            ;;
        green)
            printf '%s\n' "blue"
            ;;
        *)
            echo "Unknown deploy slot: ${slot}" >&2
            exit 1
            ;;
    esac
}

read_active_slot() {
    if [ -f "$ACTIVE_SLOT_FILE" ]; then
        cat "$ACTIVE_SLOT_FILE"
        return
    fi

    printf '%s\n' "${ACTIVE_DEPLOY_SLOT:-}"
}

compose_up_wait() {
    docker compose up \
        --wait \
        --build \
        --detach \
        --remove-orphans \
        --wait-timeout "$COMPOSE_WAIT_TIMEOUT_SECONDS" \
        "$@"
}

prepare_minio_volume_permissions() {
    docker compose build minio
    docker compose run \
        --rm \
        --no-deps \
        --user 0:0 \
        --entrypoint sh \
        minio \
        -c 'mkdir -p /data && chown -R 10002:10002 /data'
}

run_backend_init() {
    docker compose build backend-init
    docker compose run --rm backend-init
}

sync_certificates() {
    docker compose run --rm cert-sync
}

switch_nginx() {
    compose_up_wait --force-recreate nginx
}

verify_restart_policy() {
    local service_name="$1"
    local expected_policy="$2"
    local container_id
    local actual_policy

    container_id="$(docker compose ps -q "$service_name")"
    if [ -z "$container_id" ]; then
        echo "Running container for ${service_name} could not be found." >&2
        exit 1
    fi

    actual_policy="$(docker inspect --format '{{.HostConfig.RestartPolicy.Name}}' "$container_id")"
    if [ "$actual_policy" != "$expected_policy" ]; then
        echo "Unexpected restart policy for ${service_name}: expected ${expected_policy}, got ${actual_policy}." >&2
        exit 1
    fi
}

verify_runtime_restart_policies() {
    local service_name
    local unless_stopped_services=(
        "$ACTIVE_BACKEND_SLOT"
        "taskiq-worker"
        "taskiq-scheduler"
        "postgres"
        "valkey"
        "minio"
        "databasus"
    )

    for service_name in "${unless_stopped_services[@]}"; do
        verify_restart_policy "$service_name" "unless-stopped"
    done
    verify_restart_policy "nginx" "always"
}

smoke_edge() {
    local edge_health_urls=(
        "https://${APP_DOMAIN}/api/healthcheck"
        "https://${APP_DOMAIN}/healthz"
    )
    local attempt
    local edge_health_url

    for edge_health_url in "${edge_health_urls[@]}"; do
        for attempt in {1..30}; do
            if curl -k -fsS -o /dev/null --max-time 5 "$edge_health_url"; then
                break
            fi
            if [ "$attempt" -eq 30 ]; then
                echo "Edge healthcheck failed: ${edge_health_url}" >&2
                exit 1
            fi
            sleep 1
        done
    done
}

save_active_slot() {
    local slot="$1"

    mkdir -p "$DEPLOY_STATE_DIR"
    printf '%s\n' "$slot" >"$ACTIVE_SLOT_FILE"
}

stop_previous_slot() {
    local previous_slot="$1"

    if [ -z "$previous_slot" ]; then
        return
    fi

    sleep "$DEPLOY_DRAIN_SECONDS"
    docker compose stop "backend-${previous_slot}" || true
}

if [ ! -f .env ]; then
    echo ".env file could not be found" >&2
    echo "Please create a .env file in the root directory" >&2
    exit 1
fi

require_command docker
require_command curl

if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose plugin could not be found. Install it." >&2
    exit 1
fi

set -a
. .env
set +a

require_environment
prepare_compose_secret_files

previous_slot="$(read_active_slot)"
if [ -z "$previous_slot" ]; then
    target_slot="blue"
else
    target_slot="$(other_slot "$previous_slot")"
fi

export ACTIVE_DEPLOY_SLOT="$target_slot"
export ACTIVE_BACKEND_SLOT="backend-${target_slot}"

prepare_minio_volume_permissions
compose_up_wait postgres valkey minio databasus
run_backend_init
compose_up_wait "$ACTIVE_BACKEND_SLOT" taskiq-worker taskiq-scheduler
sync_certificates
switch_nginx
verify_runtime_restart_policies
smoke_edge
save_active_slot "$target_slot"
stop_previous_slot "$previous_slot"

echo "Deployment slot ${target_slot} is active."
