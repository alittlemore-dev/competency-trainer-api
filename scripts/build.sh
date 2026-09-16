#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

docker build -t "${IMAGE_REF:-alittlemore-dev/competency-trainer:local}" "$repo_dir"
