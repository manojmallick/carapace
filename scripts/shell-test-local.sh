#!/usr/bin/env bash
# Shell Test, local edition: a REAL 3-node CockroachDB cluster on this
# machine (scripts/local-cluster.sh start), then kill node 2 with SIGKILL
# mid-read-loop and prove memory reads keep succeeding via nodes 1 and 3.
# Same probe, same schema, same verdict as the ccloud edition -- only the
# kill mechanism differs (SIGKILL here, node drain/stop there).

set -euo pipefail
cd "$(dirname "$0")/.."

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
NODE2_PID=$(cat .local-cluster/node2.pid)
echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: SIGKILL node 2 (pid $NODE2_PID). No drain, no grace." | tee -a "$LOG"
kill -9 "$NODE2_PID"

echo "$(date +%T) -- node 2 is dead. Reads continuing against nodes 1 and 3..." | tee -a "$LOG"
sleep 25

echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: restarting node 2..." | tee -a "$LOG"
scripts/local-cluster.sh restart-node2 >> "$LOG" 2>&1
sleep 12

kill "$PROBE_PID" 2>/dev/null || true
trap - EXIT

echo "" | tee -a "$LOG"
TOTAL=$(grep -c -- '-- OK\|-- FAIL' "$LOG" || true)
FAILS=$(grep -c -- '-- FAIL' "$LOG" || true)
echo "Shell Test complete: $TOTAL probe reads, $FAILS failed. Full log: $LOG" | tee -a "$LOG"
