#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# SofaFlow PostgreSQL backup with rotation.
#
# Retention (max 5 archives at any time):
#   • daily   — one per run, keep the DAILY_KEEP newest   (default 3)
#   • monthly — one per calendar month, keep MONTHLY_KEEP newest (default 2)
#
# Layout:
#   /opt/backups/daily/sofa_flow-YYYYMMDD.sql.gz
#   /opt/backups/monthly/sofa_flow-YYYYMM.sql.gz
#
# Schedule (root crontab) — run once a day:
#   30 2 * * * /opt/apps/sofa-flow/scripts/backup_db.sh >> /var/log/sofa-backup.log 2>&1
#
# Restore:
#   gunzip -c /opt/backups/daily/sofa_flow-YYYYMMDD.sql.gz \
#     | docker exec -i sofa-flow-prod-db-1 psql -U sofa_user -d sofa_flow
# ---------------------------------------------------------------------------
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/opt/backups}"
DAILY_DIR="$BACKUP_ROOT/daily"
MONTHLY_DIR="$BACKUP_ROOT/monthly"
DAILY_KEEP="${DAILY_KEEP:-3}"
MONTHLY_KEEP="${MONTHLY_KEEP:-2}"
DB_CONTAINER="${DB_CONTAINER:-sofa-flow-prod-db-1}"
DB_USER="${DB_USER:-sofa_user}"
DB_NAME="${DB_NAME:-sofa_flow}"
MIN_BYTES="${MIN_BYTES:-1000}"   # a valid dump is never this small

log() { echo "[$(date '+%F %T')] $*"; }

mkdir -p "$DAILY_DIR" "$MONTHLY_DIR"

TS="$(date +%Y%m%d)"
MONTH="$(date +%Y%m)"
DAILY_FILE="$DAILY_DIR/sofa_flow-$TS.sql.gz"
TMP="$DAILY_FILE.tmp"

log "Dumping '$DB_NAME' from container '$DB_CONTAINER' ..."
if ! docker exec "$DB_CONTAINER" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$TMP"; then
    log "ERROR: pg_dump failed"; rm -f "$TMP"; exit 1
fi
if ! gzip -t "$TMP" 2>/dev/null; then
    log "ERROR: backup is not a valid gzip (corrupt)"; rm -f "$TMP"; exit 1
fi
SIZE="$(stat -c%s "$TMP")"
if [ "$SIZE" -lt "$MIN_BYTES" ]; then
    log "ERROR: dump suspiciously small ($SIZE bytes) — keeping old backups, aborting"; rm -f "$TMP"; exit 1
fi
mv -f "$TMP" "$DAILY_FILE"
log "Daily backup OK: $DAILY_FILE ($SIZE bytes)"

# Monthly snapshot — created once per calendar month from today's daily dump.
MONTHLY_FILE="$MONTHLY_DIR/sofa_flow-$MONTH.sql.gz"
if [ ! -e "$MONTHLY_FILE" ]; then
    cp -f "$DAILY_FILE" "$MONTHLY_FILE"
    log "Monthly backup OK: $MONTHLY_FILE"
else
    log "Monthly backup for $MONTH already exists — skipping"
fi

# Rotation: keep the N newest in each directory.
prune() {
    local dir="$1" keep="$2"
    find "$dir" -maxdepth 1 -type f -name 'sofa_flow-*.sql.gz' -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | awk -v k="$keep" 'NR>k {print $2}' \
        | while read -r f; do log "Pruning old backup: $f"; rm -f "$f"; done
}
prune "$DAILY_DIR" "$DAILY_KEEP"
prune "$MONTHLY_DIR" "$MONTHLY_KEEP"

log "Done. daily=$(find "$DAILY_DIR" -name 'sofa_flow-*.sql.gz' | wc -l) / keep $DAILY_KEEP, monthly=$(find "$MONTHLY_DIR" -name 'sofa_flow-*.sql.gz' | wc -l) / keep $MONTHLY_KEEP"
