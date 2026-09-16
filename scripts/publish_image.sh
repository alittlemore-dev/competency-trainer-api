#!/usr/bin/env bash
set -euo pipefail

local_image="${1:?local image is required}"
image_name="${2:?image name is required}"
image_tag="${3:?image tag is required}"

if ! command -v docker >/dev/null 2>&1; then
    echo "docker could not be found." >&2
    exit 2
fi

docker tag "$local_image" "${image_name}:${image_tag}"
docker tag "$local_image" "${image_name}:latest"
docker push "${image_name}:${image_tag}"
docker push "${image_name}:latest"
