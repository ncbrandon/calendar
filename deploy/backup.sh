#!/usr/bin/env bash
# Makes one dated backup file of the calendar database and every upload.
# Usage:  sudo bash deploy/backup.sh /path/to/backup/folder
# Nightly at 1 am:  echo '0 1 * * * root bash /opt/opsboard-repo/deploy/backup.sh /mnt/backups' | sudo tee /etc/cron.d/opsboard-backup
set -euo pipefail
DATA="${OPSBOARD_DATA:-/var/lib/opsboard}"
DEST="${1:?Give the folder to put the backup in}"
STAMP="$(date +%Y-%m-%d_%H%M)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$DEST"
# .backup takes a consistent copy even while the server is running.
sqlite3 "$DATA/opsboard.db" ".backup '$WORK/opsboard.db'"
cp -r "$DATA/uploads" "$WORK/uploads"
tar -czf "$DEST/opsboard-$STAMP.tar.gz" -C "$WORK" .
# Keep the newest 30 backups.
ls -1t "$DEST"/opsboard-*.tar.gz | tail -n +31 | xargs -r rm --
echo "Saved $DEST/opsboard-$STAMP.tar.gz"
