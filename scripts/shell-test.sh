#!/usr/bin/env bash
# Shell Test, CockroachDB Cloud edition: drain and stop a real cluster
# node via ccloud CLI while the read-loop probe runs continuously.
# Requires: ccloud auth login; CARAPACE_DB_READ_URL pointing at the
# cluster; CLUSTER name below matching your ccloud cluster.
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER="${CARAPACE_CLUSTER:-carapace-demo}"
LOG="${1:-shell_test_results.log}"
: > "$LOG"
PY=".venv/bin/python3"; [ -x "$PY" ] || PY="python3"

echo "Shell Test: starting continuous memory read loop (1 read/sec)..." | tee -a "$LOG"
( while true; do
    printf '%s -- ' "$(date +%T)"
    "$PY" -m carapace.read_probe || true
    sleep 1
  done >> "$LOG" 2>&1 ) &
PROBE_PID=$!
trap 'kill $PROBE_PID 2>/dev/null || true' EXIT

sleep 8
echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: draining + stopping node 2 of $CLUSTER via ccloud..." | tee -a "$LOG"
ccloud cluster node drain --cluster "$CLUSTER" --node-id 2 --json | tee -a "$LOG"
ccloud cluster node stop  --cluster "$CLUSTER" --node-id 2 --json | tee -a "$LOG"

echo "$(date +%T) -- node 2 down. Reads continuing against surviving nodes..." | tee -a "$LOG"
sleep 25

echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: restarting node 2..." | tee -a "$LOG"
ccloud cluster node start --cluster "$CLUSTER" --node-id 2 --json | tee -a "$LOG"
sleep 12

kill "$PROBE_PID" 2>/dev/null || true
trap - EXIT

echo "" | tee -a "$LOG"
TOTAL=$(grep -c -- '-- OK\|-- FAIL' "$LOG" || true)
FAILS=$(grep -c -- '-- FAIL' "$LOG" || true)
echo "Shell Test complete: $TOTAL probe reads, $FAILS failed. Full log: $LOG" | tee -a "$LOG"
