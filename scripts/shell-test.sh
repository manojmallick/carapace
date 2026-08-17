#!/usr/bin/env bash
# Shell Test, CockroachDB Cloud edition: disrupt a real pod on the live
# cluster via `ccloud cluster disruption` while the read-loop probe runs
# continuously.
#
# `ccloud cluster disruption set/clear` is the real, currently-shipped
# chaos-testing surface on ccloud 0.8.23 -- the CLI has no `node
# drain/stop/start` subcommand (verified against `ccloud cluster --help`
# on this version; an earlier draft of this script assumed that
# interface existed and it does not).
#
# Requires: `ccloud auth login` completed in an interactive terminal
# first (org-level browser OAuth -- this cannot be scripted or run
# non-interactively); CARAPACE_DB_READ_URL pointing at the cluster.
set -euo pipefail
cd "$(dirname "$0")/.."

CLUSTER="${CARAPACE_CLUSTER:?set CARAPACE_CLUSTER}"
REGION="${CARAPACE_DISRUPT_REGION:?set CARAPACE_DISRUPT_REGION, e.g. gcp-europe-west3}"
LOG="${1:-shell_test_results.log}"
: > "$LOG"
PY=".venv/bin/python3"; [ -x "$PY" ] || PY="python3"

ccloud auth whoami >/dev/null 2>&1 || {
  echo "Not logged in to ccloud. Run 'ccloud auth login' in an interactive terminal first." >&2
  exit 1
}

PODS=$(ccloud cluster nodes "$CLUSTER" --region "$REGION" -o json | python3 -c "import json,sys; d=json.load(sys.stdin); print(d[0]['name'] if isinstance(d,list) else d['nodes'][0]['name'])")
echo "Shell Test: target pod for disruption: $PODS" | tee -a "$LOG"

echo "Shell Test: starting continuous memory read loop (1 read/sec)..." | tee -a "$LOG"
( while true; do
    printf '%s -- ' "$(date +%T)"
    "$PY" -m carapace.read_probe || true
    sleep 1
  done >> "$LOG" 2>&1 ) &
PROBE_PID=$!
trap 'kill $PROBE_PID 2>/dev/null || true; ccloud cluster disruption clear "$CLUSTER" >/dev/null 2>&1 || true' EXIT

sleep 8
echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: disrupting pod $PODS in $REGION via ccloud..." | tee -a "$LOG"
ccloud cluster disruption set "$CLUSTER" --region "$REGION" --pods "$PODS" -o json | tee -a "$LOG"

echo "$(date +%T) -- pod disrupted. Reads continuing against surviving nodes..." | tee -a "$LOG"
sleep 25

echo "" | tee -a "$LOG"
echo "$(date +%T) -- Shell Test: clearing disruption..." | tee -a "$LOG"
ccloud cluster disruption clear "$CLUSTER" -o json | tee -a "$LOG"
sleep 12

kill "$PROBE_PID" 2>/dev/null || true
trap - EXIT

echo "" | tee -a "$LOG"
TOTAL=$(grep -c -- '-- OK\|-- FAIL' "$LOG" || true)
FAILS=$(grep -c -- '-- FAIL' "$LOG" || true)
echo "Shell Test complete: $TOTAL probe reads, $FAILS failed. Full log: $LOG" | tee -a "$LOG"
