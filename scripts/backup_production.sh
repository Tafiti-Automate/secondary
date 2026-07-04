#!/usr/bin/env bash
set -euo pipefail

umask 077

: "${BACKUP_DIR:?Set BACKUP_DIR to a protected backup directory}"
: "${DB_NAME:?Set DB_NAME}"
: "${DB_USER:?Set DB_USER}"
: "${DB_PASSWORD:?Set DB_PASSWORD}"

DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
MEDIA_ROOT="${MEDIA_ROOT:-/app/media}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DESTINATION="${BACKUP_DIR%/}/${STAMP}"

mkdir -p "$DESTINATION"
PGPASSWORD="$DB_PASSWORD" pg_dump \
  --host "$DB_HOST" \
  --port "$DB_PORT" \
  --username "$DB_USER" \
  --format custom \
  --no-owner \
  --no-acl \
  --file "$DESTINATION/database.dump" \
  "$DB_NAME"

if [[ -d "$MEDIA_ROOT" ]]; then
  tar --create --gzip --file "$DESTINATION/media.tar.gz" --directory "$MEDIA_ROOT" .
fi

sha256sum "$DESTINATION"/* > "$DESTINATION/SHA256SUMS"
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -delete

printf 'Backup created: %s\n' "$DESTINATION"
