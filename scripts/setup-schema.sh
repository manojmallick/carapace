#!/usr/bin/env bash
# Apply all schema files in order against $CARAPACE_DB_ADMIN_URL
# (an admin-capable connection string; the app itself never uses this).
set -euo pipefail
cd "$(dirname "$0")/.."

URL="${CARAPACE_DB_ADMIN_URL:?set CARAPACE_DB_ADMIN_URL}"
for f in schema/*.sql; do
  echo "-- applying $f"
  cockroach sql --url "$URL" -f "$f"
done
