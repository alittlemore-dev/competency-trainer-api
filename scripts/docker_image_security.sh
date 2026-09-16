#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

image_name="${1:?image name is required}"
image_tag="${2:?IMAGE_TAG is required}"
dockerfile="${3:?Dockerfile path is required}"
build_context="${4:?build context is required}"
trivy_image="${5:?Trivy image is required}"
image_export_path="${6:-}"
image_ref="${image_name}:${image_tag}"
image_created="false"

cleanup_image() {
    if [ "$image_created" = "true" ]; then
        docker image rm "$image_ref" >/dev/null 2>&1 || true
    fi
}

if ! command -v docker >/dev/null 2>&1; then
    echo "docker could not be found." >&2
    exit 2
fi

if docker image inspect "$image_ref" >/dev/null 2>&1; then
    echo "Refusing to overwrite existing local image: ${image_ref}" >&2
    exit 2
fi

trap cleanup_image EXIT

docker build \
    -f "${repo_dir}/${dockerfile}" \
    -t "$image_ref" \
    "${repo_dir}/${build_context}"
image_created="true"

bash "${script_dir}/docker_lint.sh" dockle "$image_ref"
bash "${script_dir}/trivy_scan.sh" image "$trivy_image" "$image_ref"

if [ -n "$image_export_path" ]; then
    docker save --output "$image_export_path" "$image_ref"
fi
