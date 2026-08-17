#!/usr/bin/env bash
# Shell Test, local edition: a REAL 3-node CockroachDB cluster on this
# machine (scripts/local-cluster.sh start), then SIGKILL a node mid-read-loop
# and prove memory reads keep succeeding via the survivors. Same probe, same
# schema, same verdict as the ccloud edition -- only the kill mechanism
# differs (SIGKILL here, node drain/stop there).
#
# Defaults to killing node 1 -- the FIRST host in the client's multi-host
# connection string, i.e. the one it actually connects to under normal
# conditions. Killing node 2 or 3 instead only proves an already-idle node
# kept working; it doesn't prove the client fails over to a different node.
# Pass a node number (1, 2, or 3) as the second argument to target a
# different one.

set -euo pipefail
cd "$(dirname "$0")/.."

LOG="${1:-shell_test_results.log}"
TARGET="${2:-1}"
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
NODE_PID=$(cat .local-cluster/node"$TARGET".pid)
echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: SIGKILL node $TARGET (pid $NODE_PID). No drain, no grace." | tee -a "$LOG"
kill -9 "$NODE_PID"

echo "$(date +%T) -- node $TARGET is dead. Reads continuing against the survivors..." | tee -a "$LOG"
sleep 25

echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: restarting node $TARGET..." | tee -a "$LOG"
scripts/local-cluster.sh restart-node "$TARGET" >> "$LOG" 2>&1
sleep 12

kill "$PROBE_PID" 2>/dev/null || true
trap - EXIT

echo "" | tee -a "$LOG"
TOTAL=$(grep -c -- '-- OK\|-- FAIL' "$LOG" || true)
FAILS=$(grep -c -- '-- FAIL' "$LOG" || true)
echo "Shell Test complete: $TOTAL probe reads, $FAILS failed. Full log: $LOG" | tee -a "$LOG"
