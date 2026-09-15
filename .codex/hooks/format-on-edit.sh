#!/usr/bin/env bash
set -euo pipefail

input=$(cat)
repo=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
format_backend=0

repo_relative_path() {
    local path="${1#./}"
    case "$path" in
        "$repo"/*) path="${path#"$repo"/}" ;;
    esac
    printf '%s\n' "$path"
}

extract_changed_paths() {
    printf '%s\n' "$input" |
        grep -Eo '"(file_path|path)"[[:space:]]*:[[:space:]]*"[^"]+"' |
        sed -E 's/^"[^"]+"[[:space:]]*:[[:space:]]*"([^"]+)".*$/\1/' || true

    printf '%s\n' "$input" |
        grep -Eo '\*\*\* (Add|Update|Delete) File: [^\"]+' |
        sed -E 's/^\*\*\* (Add|Update|Delete) File: //' |
        sed -E 's/\\n.*$//' || true
}

while IFS= read -r changed_path; do
    [ -n "$changed_path" ] || continue
    relative_path=$(repo_relative_path "$changed_path")

    case "$relative_path" in
        backend/src/*.py|backend/src/*.pyi|backend/tests/*.py|backend/tests/*.pyi|backend/performance/*.py|backend/performance/*.pyi)
            format_backend=1
            ;;
    esac
done < <(extract_changed_paths)

if [ "$format_backend" = 1 ]; then
    UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/codex-uv-cache}" make -C "$repo/backend" format
fi
