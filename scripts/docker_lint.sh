#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

hadolint_image="${HADOLINT_IMAGE:-hadolint/hadolint:v2.14.0}"
dockle_image="${DOCKLE_IMAGE:-goodwithtech/dockle:v0.4.15}"
dockle_exit_level="${DOCKLE_EXIT_LEVEL:-warn}"
dockle_accept_keys="${DOCKLE_ACCEPT_KEYS:-KEY_SHA512}"
dockle_accept_files="${DOCKLE_ACCEPT_FILES:-settings.py}"
dockle_ignore_codes="${DOCKLE_IGNORE_CODES:-DKL-DI-0005}"

require_command() {
    local command_name="$1"

    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "${command_name} could not be found." >&2
        exit 2
    fi
}

run_hadolint() {
    require_command docker

    docker run --rm \
        -v "${repo_dir}:/workspace:ro" \
        -w /workspace \
        "$hadolint_image" \
        hadolint \
        --failure-threshold error \
        Dockerfile
}

run_dockle() {
    local image_ref
    local dockle_args=()
    local accept_key
    local accept_file
    local ignore_code

    require_command docker

    if [ "$#" -eq 0 ]; then
        echo "At least one image reference is required for Dockle." >&2
        exit 2
    fi

    IFS=","
    for accept_key in $dockle_accept_keys; do
        if [ -n "$accept_key" ]; then
            dockle_args+=(--accept-key "$accept_key")
        fi
    done
    for accept_file in $dockle_accept_files; do
        if [ -n "$accept_file" ]; then
            dockle_args+=(--accept-file "$accept_file")
        fi
    done
    for ignore_code in $dockle_ignore_codes; do
        if [ -n "$ignore_code" ]; then
            dockle_args+=(--ignore "$ignore_code")
        fi
    done
    unset IFS

    for image_ref in "$@"; do
        docker run --rm \
            -v /var/run/docker.sock:/var/run/docker.sock \
            "$dockle_image" \
            --exit-code 1 \
            --exit-level "$dockle_exit_level" \
            "${dockle_args[@]}" \
            "$image_ref"
    done
}

case "${1:-}" in
    hadolint)
        run_hadolint
        ;;
    dockle)
        shift
        run_dockle "$@"
        ;;
    *)
        echo "Usage: $0 {hadolint|dockle [image-ref ...]}" >&2
        exit 2
        ;;
esac
