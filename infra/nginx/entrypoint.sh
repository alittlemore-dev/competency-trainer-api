#!/usr/bin/env sh
set -eu

readonly template_file=/etc/nginx/runtime-templates/site.conf.template
readonly rendered_directory=/tmp/nginx-conf.d
readonly rendered_file="${rendered_directory}/site.conf"
readonly temporary_file="${rendered_file}.tmp"

mkdir -p "$rendered_directory"
envsubst '$APP_DOMAIN $SSL_CERT $SSL_KEY $ACTIVE_BACKEND_SLOT $MINIO_PUBLIC_URL' \
    < "$template_file" > "$temporary_file"

if [ ! -s "$temporary_file" ]; then
    echo "Rendered nginx configuration is empty." >&2
    exit 1
fi

mv "$temporary_file" "$rendered_file"
exec nginx -g "daemon off;"
