#!/usr/bin/env bash
set -euo pipefail

# --- CONFIG ---
DB_FILE="/home/ubuntu/GitHub/compiler-tester/db/compilers.db"
BACKUP_DIR="/home/ubuntu/GitHub/compiler-tester/db/backup"
SQLITE_BIN="/usr/bin/sqlite3"

DATE=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/compilers_$DATE.db"

# --- ENSURE DIR EXISTS ---
mkdir -p "$BACKUP_DIR"

CMD=".backup $BACKUP_FILE"
# --- BACKUP ---
"$SQLITE_BIN" "$DB_FILE" "$CMD"

# --- OPTIONAL: COMPRESSION ---
gzip "$BACKUP_FILE"

# --- OPTIONAL: RETENTION (keep last 14 days) ---
find "$BACKUP_DIR" -type f -name "*.gz" -mtime +14 -delete
