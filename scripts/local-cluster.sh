#!/usr/bin/env bash
# A real (insecure, local) 3-node CockroachDB cluster for development and
# the local Shell Test. Three separate cockroach processes, three stores,
# replication factor 3 -- the same failure semantics as a cloud cluster,
# minus the network.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .local-cluster

# NOTE: not --background -- that flag blocks until the node is live,
# which never happens before `cockroach init`, deadlocking startup.
start_node () {  # id
  nohup cockroach start --insecure \
    --store=.local-cluster/node"$1" \
    --listen-addr=localhost:2600"$1" \
    --sql-addr=localhost:2625"$1" \
    --http-addr=localhost:808"$1" \
    --join=localhost:26001,localhost:26002,localhost:26003 \
    --pid-file=.local-cluster/node"$1".pid \
    > .local-cluster/node"$1".log 2>&1 &
}

case "${1:-start}" in
  start)
    start_node 1; start_node 2; start_node 3
    sleep 2
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      cockroach init --insecure --host=localhost:26001 2>/dev/null && break
      sleep 2
    done
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      cockroach sql --insecure --host=localhost:26251 -e "SELECT 1" >/dev/null 2>&1 && break
      sleep 2
    done
    echo "Cluster up. SQL: localhost:26251,26252,26253  UI: http://localhost:8081"
    ;;
  restart-node2)
    start_node 2
    ;;
  stop)
    for n in 1 2 3; do
      [ -f .local-cluster/node$n.pid ] && kill "$(cat .local-cluster/node$n.pid)" 2>/dev/null || true
    done
    ;;
  *) echo "usage: $0 [start|restart-node2|stop]"; exit 1 ;;
esac
