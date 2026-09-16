#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

require_command() {
    local command_name="$1"

    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "${command_name} could not be found." >&2
        exit 2
    fi
}

run_config_scan() {
    local trivy_image="$1"

    docker run --rm \
        -v "${repo_dir}:/workspace:ro" \
        "$trivy_image" \
        --cache-dir /tmp/trivy-cache \
        --quiet \
        config \
        --exit-code 1 \
        --format table \
        --severity HIGH,CRITICAL \
        /workspace
}

run_image_scan() {
    local trivy_image="$1"
    local image_ref="$2"

    docker run --rm \
        -v /var/run/docker.sock:/var/run/docker.sock \
        "$trivy_image" \
        --cache-dir /tmp/trivy-cache \
        --quiet \
        image \
        --exit-code 1 \
        --format table \
        --ignore-unfixed \
        --image-src docker \
        --pkg-types os,library \
        --scanners vuln \
        --severity HIGH,CRITICAL \
        "$image_ref"
}

require_command docker

action="${1:?action is required}"
trivy_image="${2:?Trivy image is required}"

case "$action" in
    config)
        run_config_scan "$trivy_image"
        ;;
    image)
        image_ref="${3:?image reference is required}"
        run_image_scan "$trivy_image" "$image_ref"
        ;;
    *)
        echo "Usage: $0 {config TRIVY_IMAGE|image TRIVY_IMAGE IMAGE_REF}" >&2
        exit 2
        ;;
esac
