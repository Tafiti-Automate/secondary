#!/usr/bin/env bash
set -euo pipefail

: "${1:?Usage: verify_backup.sh /path/to/backup-directory}"
BACKUP_PATH="$1"

test -f "$BACKUP_PATH/database.dump"
test -f "$BACKUP_PATH/SHA256SUMS"
cd "$BACKUP_PATH"
sha256sum --check SHA256SUMS
pg_restore --list database.dump >/dev/null

printf 'Backup verification passed: %s\n' "$BACKUP_PATH"
