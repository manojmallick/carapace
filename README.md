# Carapace

Agent memory built on CockroachDB, proven against a real node failure --
not just designed to survive one. Built for the CockroachDB x AWS
Hackathon 2026 by Manoj Mallick.

A carapace is the hard shell that lets an organism survive things that
would otherwise be fatal. An agent whose memory goes offline doesn't
degrade gracefully -- it stops. Carapace is the shell.

## The pattern

Three memory tiers, one CockroachDB cluster, transactionally consistent:

1. **Hot** -- exact-match semantic cache, dual-hash keyed (query hash +
   content hash), so a change in underlying context silently invalidates
   stale entries. Pattern validated in production at ING (70% LLM-call
   reduction there; Carapace measures its own numbers fresh, below).
2. **Warm** -- fuzzy semantic recall via CockroachDB Distributed Vector
   Indexing over Titan V2 embeddings: a differently-worded but
   semantically similar question still hits memory.
3. **Cold** -- long-term team-convention memory with row-level TTL decay
   (conventions expire unless re-affirmed).

**The boundary:** the agent's reasoning loop can only READ memory --
structurally (no write method exists on `AgentMemoryReader`) and at the
database (SELECT-only `carapace_reader` role / read-only MCP mode).
Every write goes through an async AWS Lambda (`lambda/writeback_handler.py`)
holding the only write-capable credential, writing the hot-tier row and
warm-tier embedding in ONE transaction. A slow or failed write can never
block the agent's answer.

## Architecture

```
agent query
  -> HOT   exact dual-hash lookup          (relational)
  -> WARM  vector similarity, top-5        (Distributed Vector Indexing)
  -> COLD  standing conventions by domain  (relational + TTL)
  -> AWS Bedrock (Claude) generates fresh, conventions applied
  -> AWS Lambda write-back, async, all tiers, one transaction
```

Every access is audit-logged (`carapace_audit.jsonl`) with tier,
outcome, and latency.

## Production readiness, verified not asserted

`scripts/shell-test.sh` (CockroachDB Cloud, via `ccloud cluster
disruption set/clear`) and `scripts/shell-test-local.sh` (real local
3-node cluster, SIGKILL) disrupt a cluster node mid-session while a
1/sec read-loop probe runs continuously. See `shell_test_results.log`
for the actual output of a real run -- including which gateway node served each
read, so you can watch traffic move to the survivors.

## CockroachDB tools used

MCP Server (read-only agent memory access, `.mcp.json`), Distributed
Vector Indexing (warm tier), ccloud CLI (auth + Shell Test), Agent
Skills Repo (real PR, open:
[cockroachlabs/cockroachdb-skills#24](https://github.com/cockroachlabs/cockroachdb-skills/pull/24)).

## AWS services used

Amazon Bedrock (Claude reasoning + Titan V2 embeddings), AWS Lambda
(async memory write-back).

## Run it

```bash
git clone https://github.com/manojmallick/carapace && cd carapace
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # then: set -a; source .env; set +a

scripts/local-cluster.sh start        # real 3-node cluster, RF=3
cockroach sql --insecure --host=localhost:26251 -e "CREATE DATABASE IF NOT EXISTS carapace"
CARAPACE_DB_ADMIN_URL="postgresql://root@localhost:26251/carapace?sslmode=disable" scripts/setup-schema.sh

python3 -m carapace.cli demo          # novel -> hot -> warm walk-through
scripts/shell-test-local.sh           # kill node 2 mid-read-loop
python3 benchmark/cache_hit_benchmark.py
```

## Benchmark

`benchmark/cache_hit_benchmark.py` runs a 20-query realistic developer
sequence (repeats + paraphrases) through the full pipeline; results in
`benchmark_results.json` are from a real run against a real cluster.

## License

MIT
