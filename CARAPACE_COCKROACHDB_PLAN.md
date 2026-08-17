# CARAPACE — COCKROACHDB × AWS HACKATHON: BUILD WITH AGENTIC MEMORY
# Prize: $8,750 total | Deadline: Aug 18, 2026 @ 5:00pm EDT | Participants: 1,830
# Builder: Manoj Mallick | LearnHubPlay BV | Amsterdam
# Gap-closing upgrades applied natively throughout (per hackathon-winning-bar skill)

---

## SECTION 0 — SITUATION ANALYSIS

### The numbers

$8,750 / 1,830 participants = $4.78/participant -- low on paper, but only
3 winning slots exist (no runner-up tiers, no per-category prizes), and
this hackathon has real technical filtering built into its own
requirements: 2+ CockroachDB tools AND 1+ AWS service, with explicit
disclosure required for both. That bar alone will eliminate most
low-effort registrants before judging even starts.

### Real runway: 31 days

Deadline Aug 18. The longest runway of the recent batch -- comparable to
DataHub (23 days) and Arm (27 days), slightly longer than both.

### Why this is the strongest natural fit of any hackathon this season

This is not a stretch. Manoj already built, in production at ING, a
SHA-based dual-key semantic cache (query hash + content hash) that cut
LLM calls by 70%. He already designed a 3-tier hot/warm/cold memory
architecture for CodeMind (built for the Qwen Cloud Hackathon). Carapace
is the direct, honest extension of both: the same memory architecture,
now built on CockroachDB specifically, with the production-readiness
rigor (resilience, access control, audit) that a real distributed SQL
database is built to prove and a former EU FinTech architect knows how
to demonstrate credibly.

### The judges' own framing, read carefully

"An agent whose memory goes offline doesn't degrade gracefully, it
stops... CockroachDB was built for exactly this." This is a direct
invitation to demonstrate memory surviving a real failure, not just
memory existing. Most submissions will show CockroachDB storing data
correctly; almost none will show it surviving a node going down mid-query.

### The judging criteria

- **Agentic Memory Design** -- "more than toy queries -- state,
  embeddings, context, or transactional data at real scale."
- **Technical Implementation** -- "uses the tools correctly and safely."
- **Real-World Impact** -- "meaningful, not just technically impressive."
- **Production Readiness** -- explicitly asks about "resilience, access
  control, and what happens when things go wrong." This is its own full
  judging category, distinct from Technical Implementation -- unusually
  direct for a hackathon, and a strong signal that a genuine failure-mode
  demonstration is rewarded specifically, not just implied.
- **Creativity & Originality** -- "insight into what makes agentic
  systems different from traditional apps."

### Tool selection: all four CockroachDB tools, not the minimum two

Rather than doing the minimum (2 tools), Carapace uses all 4 -- MCP
Server, Distributed Vector Indexing, ccloud CLI, and a real Agent Skills
Repo contribution -- because each maps onto a genuinely different part
of the memory architecture, not a checkbox. AWS: Bedrock (agent
reasoning) + Lambda (decoupled memory write path).

---

## SECTION 1 — THE IDEA: CARAPACE

**One sentence:** A coding agent's persistent memory -- exact-match
semantic cache, fuzzy/semantic recall via embeddings, and long-term
convention memory -- built on CockroachDB specifically because the
memory has to survive a node dying mid-session, not just store data
correctly when nothing goes wrong.

### Why "Carapace"

A carapace is the hard protective shell that lets an organism survive
things that would otherwise be fatal -- a direct, honest echo of
CockroachDB's own resilience-first brand identity, without literally
naming the product. It signals genuine understanding of what
CockroachDB is actually for, which is exactly what the "Creativity &
Originality" criterion asks for ("insight into what makes agentic
systems different").

### The three memory tiers, each mapped to a real CockroachDB capability

1. **Hot: exact-match semantic cache** (CockroachDB relational tables) --
   the same SHA-based dual-key pattern (query hash + content hash)
   validated in production at ING, now running on CockroachDB.
2. **Warm: fuzzy semantic recall** (CockroachDB Distributed Vector
   Indexing) -- embeddings of past query-context pairs, so a
   differently-worded but semantically similar question still gets a
   grounded, cached answer instead of missing the exact-match cache and
   falling through to a full LLM call.
3. **Cold: long-term convention memory** (CockroachDB relational tables,
   TTL-based decay) -- team conventions and corrections that should
   persist indefinitely unless explicitly overridden.

All three tiers live in the same CockroachDB cluster, giving genuine
cross-tier transactional consistency -- exactly the "no consistency
gaps between your vector data and your operational database" property
CockroachDB's own tool description highlights.

---

## SECTION 2 — ARCHITECTURE

```
AGENT QUERY
"How should I handle errors in this service?"

        v

MCP SERVER (read-only, CockroachDB Cloud Managed MCP)
  Agent queries memory via https://cockroachlabs.cloud/mcp
  Read-only mode enforced -- the agent can never write directly

        v

HOT TIER CHECK (relational, exact match)
  SELECT * FROM semantic_cache
  WHERE query_hash = ? AND content_hash = ?
  -> cache hit: return immediately, no LLM call needed

        v (on hot miss)

WARM TIER CHECK (Distributed Vector Indexing, fuzzy match)
  SELECT *, embedding <-> query_embedding AS distance
  FROM query_memory
  ORDER BY distance LIMIT 5
  -> semantically similar past query found: reuse with adaptation

        v (on warm miss)

COLD TIER CHECK (relational, long-term conventions)
  SELECT * FROM team_conventions WHERE domain = ?
  -> apply any standing correction/preference before generating

        v (full miss across all 3 tiers)

AWS BEDROCK (agent reasoning)
  LLM generates a fresh answer using SigMap codebase context
  + whatever partial memory was found above

        v

MEMORY WRITE-BACK (via AWS Lambda, NOT via the agent's MCP connection)
  Lambda function, triggered async, writes the new interaction to
  all 3 tiers as appropriate -- decoupled from the agent's read path,
  so a slow or failed write never blocks the agent's response

        v

CARAPACE RESILIENCE SUITE (see Section 3)
  Read-only MCP boundary + audit log + Shell Test chaos verification
```

---

## SECTION 3 — NAMED PRODUCTION-READINESS FEATURE: THE CARAPACE RESILIENCE SUITE

This directly answers the Production Readiness criterion's own
language -- resilience, access control, and "what happens when things
go wrong" -- as a real, demonstrable feature, not a design-doc claim.

### 3.1 Read-only MCP boundary (access control)

```python
# carapace/mcp_boundary.py
# The agent's ONLY path to CockroachDB is the read-only MCP Server
# connection. All writes happen exclusively through the Lambda
# write-back path (Section 2), never directly from agent-issued calls.
# This is enforced, not just documented.

MCP_ENDPOINT = "https://cockroachlabs.cloud/mcp"

class AgentMemoryReader:
    """Wraps the CockroachDB Cloud Managed MCP Server connection.
    Structurally cannot issue a write -- no write method exists on
    this class at all, by design, not by convention."""

    def __init__(self, mcp_client):
        self.mcp_client = mcp_client  # configured read-only per MCP Server default

    async def check_hot_cache(self, query_hash: str, content_hash: str):
        return await self.mcp_client.call_tool("sql_query", {
            "query": (
                "SELECT response FROM semantic_cache "
                "WHERE query_hash = $1 AND content_hash = $2"
            ),
            "params": [query_hash, content_hash],
        })

    async def check_warm_memory(self, query_embedding: list, limit: int = 5):
        return await self.mcp_client.call_tool("sql_query", {
            "query": (
                "SELECT query_text, response, "
                "embedding <-> $1 AS distance "
                "FROM query_memory ORDER BY distance LIMIT $2"
            ),
            "params": [query_embedding, limit],
        })

    # No write_* method exists on this class. Intentionally.
```

### 3.2 Shell Test (resilience, verified not asserted)

```bash
#!/usr/bin/env bash
# scripts/shell-test.sh
# A real, repeatable chaos test: kill a CockroachDB node mid-session
# and prove memory reads continue succeeding. This is the single most
# convincing piece of evidence for "Production Readiness" -- a live
# demonstration, not a claim about CockroachDB's general reputation.

set -euo pipefail

echo "Shell Test: starting continuous memory read loop..."
( while true; do
    RESULT=$(python3 carapace/read_probe.py 2>&1) || echo "READ FAILED: $RESULT"
    echo "$(date +%T) -- $RESULT"
    sleep 1
  done ) &
PROBE_PID=$!

sleep 5
echo ""
echo "Shell Test: killing node 2 of 3 via ccloud CLI..."
ccloud cluster node drain --cluster carapace-demo --node-id 2 --json
ccloud cluster node stop --cluster carapace-demo --node-id 2 --json

echo "Shell Test: node 2 down. Memory reads continuing against nodes 1 and 3..."
sleep 20

echo ""
echo "Shell Test: restoring node 2..."
ccloud cluster node start --cluster carapace-demo --node-id 2 --json

sleep 10
kill "$PROBE_PID"

echo ""
echo "Shell Test complete. Review the read-loop log above for any"
echo "failed reads during the node-2 outage window."
```

Run this for real, capture the actual read-loop log, and report the
real numbers: how many read attempts occurred during the outage window,
how many succeeded, and the actual latency distribution during the
failover -- not an assumed "zero downtime," the measured reality.

### 3.3 Full audit log (observability)

```python
# carapace/audit.py
# Every memory access -- hit, miss, or write -- is logged with tier,
# latency, and outcome. This is what "observable" means in practice,
# not just a claim in the README.

import time
import json

class CarapaceAuditLog:
    def __init__(self, log_path: str = "carapace_audit.jsonl"):
        self.log_path = log_path

    def record(self, tier: str, outcome: str, latency_ms: float, query_hash: str):
        entry = {
            "timestamp": time.time(),
            "tier": tier,        # "hot", "warm", "cold", "miss"
            "outcome": outcome,  # "hit", "miss", "error"
            "latency_ms": latency_ms,
            "query_hash": query_hash,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

---

## SECTION 4 — FRESH BENCHMARK (measured on this build, not recycled from ING)

The ING 70% LLM-call-reduction number is real, but it belongs to a
different system on different infrastructure -- citing it directly for
Carapace would be exactly the recycled-number pattern this season's
gap analysis flagged. Carapace earns its own number.

```python
# benchmark/cache_hit_benchmark.py
# Runs a real sequence of developer queries against Carapace's 3-tier
# memory, freshly measuring hit rate per tier and end-to-end latency.

import time
import json

def run_benchmark(queries: list, carapace_client) -> dict:
    results = {"hot": 0, "warm": 0, "cold": 0, "full_miss": 0, "latencies_ms": []}

    for q in queries:
        start = time.time()
        outcome = carapace_client.query(q)  # returns which tier answered
        elapsed = (time.time() - start) * 1000

        results[outcome["tier"]] += 1
        results["latencies_ms"].append(elapsed)

    total = len(queries)
    return {
        "total_queries": total,
        "hot_hit_rate": round(results["hot"] / total, 3),
        "warm_hit_rate": round(results["warm"] / total, 3),
        "cold_hit_rate": round(results["cold"] / total, 3),
        "full_miss_rate": round(results["full_miss"] / total, 3),
        "avg_latency_ms": round(sum(results["latencies_ms"]) / total, 1),
        "p95_latency_ms": round(sorted(results["latencies_ms"])[int(total * 0.95)], 1),
    }

if __name__ == "__main__":
    with open("benchmark_queries.json") as f:
        queries = json.load(f)

    results = run_benchmark(queries, carapace_client=get_client())
    with open("benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
```

Run this for real against a real CockroachDB Cloud cluster with a real
query sequence, and report whatever the actual hit rates and latencies
are -- including if the warm (vector) tier's hit rate is modest at first,
since that's an honest reflection of how much real usage history exists
at demo time, not a flaw to hide.

---

## SECTION 5 — REAL CHALLENGES DIARY (fill in during build)

```
CHALLENGE 1: [exact issue -- e.g. "the MCP Server's read-only mode
  rejected an UPSERT-style query pattern I initially tried to use for
  cache writes, which is exactly why the write path had to move to a
  separate Lambda function rather than being a workaround"]
  What we assumed: ...
  What actually happened: [exact error message]
  The fix: [exact architectural change]

CHALLENGE 2: [exact issue hit with Distributed Vector Indexing -- e.g.
  embedding dimension mismatch between the model used to generate
  query embeddings and the index configuration]

CHALLENGE 3: [exact issue hit during the Shell Test -- e.g. ccloud CLI
  node drain taking longer than expected, requiring the read-loop probe
  interval to be adjusted to actually capture the transition window]
```

---

## SECTION 6 — TOOL COVERAGE CHECKLIST (explicit, as required by the submission form)

```
COCKROACHDB TOOLS (at least 2 required -- Carapace uses all 4):
[ ] MCP Server: read-only agent memory access -- sql_query tool,
    ___ calls per session
[ ] Distributed Vector Indexing: warm-tier semantic recall -- ___
    embeddings stored, ___ similarity queries per session
[ ] ccloud CLI: cluster provisioning + Shell Test node drain/stop/start
    -- ___ commands run
[ ] Agent Skills Repo: real PR contributing a cockroachdb-agent-memory
    skill (see Section 7)

AWS SERVICES (at least 1 required -- Carapace uses 2):
[ ] Amazon Bedrock: agent reasoning / LLM calls on full-miss
[ ] AWS Lambda: decoupled, async memory write-back path
```

---

## SECTION 7 — REAL OPEN-SOURCE CONTRIBUTION

The CockroachDB Agent Skills Repo is real, curated, and portable across
Claude/Cursor/LangChain/MCP -- the same mechanism as DataHub's Skills
repo used earlier this season. The contribution: a real skill packaging
the 3-tier memory pattern.

```markdown
---
name: cockroachdb-agent-memory
description: Implements a 3-tier agent memory pattern on CockroachDB --
  exact-match semantic cache, vector-indexed fuzzy recall, and long-term
  convention memory -- with a read-only MCP boundary separating agent
  reads from an async write-back path. Use this skill when designing
  persistent memory for a production coding or reasoning agent that
  needs to survive node failures without losing consistency.
---

# cockroachdb-agent-memory

## When to use this skill
- Designing persistent memory for an agent that runs in production,
  not just a demo
- The memory needs both exact-match caching AND semantic/fuzzy recall
- Resilience to node failure is a real requirement, not a nice-to-have

## Procedure
1. Provision a CockroachDB Cloud cluster with at least 3 nodes for
   real failure-tolerance (not a single-node dev instance).
2. Create a hot-tier table for exact-match caching, keyed on a
   dual hash (query hash + content hash) to avoid stale cache hits
   when underlying context changes.
3. Enable Distributed Vector Indexing on a warm-tier table storing
   query embeddings, for fuzzy recall when the hot tier misses.
4. Connect the agent's READ path through the CockroachDB Cloud Managed
   MCP Server in its default read-only mode -- never give the agent's
   live reasoning loop direct write access.
5. Route all WRITES through a separate, async path (e.g. a Lambda
   function) so a slow or failed write never blocks the agent's
   response to the user.
6. Before calling the memory layer "production-ready," run a real
   node-failure test: drain and stop one node via ccloud CLI while a
   read-loop probe runs continuously, and verify reads keep succeeding.

## Safety boundaries
- Never let the agent's live reasoning path hold write access to the
  memory store -- writes should be async and auditable, reads should
  be immediate and safe.
- Never claim resilience without having actually run a node-failure
  test -- an assumed property is not a verified one.
```

**Submission plan:** fork the CockroachDB Agent Skills Repo, add this
skill following its existing format, open a real PR before the
deadline -- independently verifiable by any judge who checks the link.

---

## SECTION 8 — DEMO VIDEO SCRIPT (under 3 minutes)

```
[0:00-0:15] THE CLAIM
"CockroachDB's own pitch: memory that never goes down. Let's actually
test that, not just believe it."
Show: a 3-node CockroachDB Cloud cluster, all healthy.

[0:15-0:45] THE MEMORY WORKING NORMALLY
Live agent query -> hot cache hit shown, then a paraphrased query ->
warm/vector tier hit shown, then a genuinely novel query -> full miss
to Bedrock, then written back via Lambda.

[0:45-1:30] THE SHELL TEST, LIVE
Terminal: shell-test.sh running. Node 2 drained and stopped via ccloud
CLI, live on screen. The read-loop probe continues running underneath --
show the actual log, not a cutaway.
"Node's down. Memory reads keep succeeding against nodes 1 and 3."

[1:30-1:50] THE NUMBERS
Show benchmark_results.json: real hit rates per tier, real latency
during the Shell Test's outage window.

[1:50-2:20] THE READ-ONLY BOUNDARY
"The agent can never write directly to memory -- only read, through
CockroachDB's own read-only MCP mode. Every write goes through an
audited, async Lambda path instead."

[2:20-2:45] THE OPEN-SOURCE PIECE
Show the real PR to the CockroachDB Agent Skills Repo.

[2:45-3:00] CLOSE
"Carapace. Memory that survives what it's supposed to survive."
GitHub + demo URL held 3+ seconds.
```

---

## SECTION 9 — README.md

```markdown
# Carapace

Agent memory built on CockroachDB, proven against a real node failure --
not just designed to survive one. Built for the CockroachDB x AWS
Hackathon 2026.

## The pattern

Three memory tiers, one CockroachDB cluster:
1. Hot -- exact-match semantic cache (dual-hash: query + content)
2. Warm -- fuzzy semantic recall via Distributed Vector Indexing
3. Cold -- long-term convention memory, TTL-decayed

Reads go through CockroachDB's read-only Managed MCP Server. Writes go
through a separate, async AWS Lambda path -- the agent's live reasoning
loop never holds write access.

## Production readiness, verified not asserted

scripts/shell-test.sh kills a real cluster node mid-session via ccloud
CLI while a continuous read-loop probe runs. See
shell_test_results.log for the actual output from a real run.

## CockroachDB tools used
MCP Server, Distributed Vector Indexing, ccloud CLI, Agent Skills Repo
(real PR: [link])

## AWS services used
Amazon Bedrock (agent reasoning), AWS Lambda (async memory write-back)

## Install

git clone https://github.com/manojmallick/carapace
cd carapace
pip install -r requirements.txt
# Configure COCKROACHDB_CLUSTER_URL, AWS credentials
python carapace/cli.py demo

## Benchmark

python benchmark/cache_hit_benchmark.py
cat benchmark_results.json

## License

MIT
```

---

## SECTION 10 — 31-DAY BUILD PLAN (July 18 — Aug 18)

```
Week 1 (Jul 18-24): CockroachDB Cloud setup
  [ ] Provision a 3-node CockroachDB Cloud cluster (multi-node is
      required for the Shell Test to mean anything)
  [ ] Connect the CockroachDB Cloud Managed MCP Server, confirm
      read-only mode works as documented
  [ ] Create hot-tier and cold-tier relational schemas
  [ ] Enable Distributed Vector Indexing on the warm-tier table

Week 2 (Jul 25-31): Core memory pipeline + AWS wiring
  [ ] Wire AWS Bedrock for full-miss agent reasoning
  [ ] Build the async Lambda write-back path
  [ ] Wire SigMap as the codebase-context source feeding into queries
  [ ] First full end-to-end run: query -> tier check -> Bedrock ->
      Lambda write-back -> visible in CockroachDB

Week 3 (Aug 1-7): Resilience suite + benchmark
  [ ] Build and run shell-test.sh for real, capture the actual log
  [ ] Build cache_hit_benchmark.py, run it for real, get real numbers
  [ ] Fill in the Real Challenges diary
  [ ] Fork the Agent Skills Repo, add cockroachdb-agent-memory, open PR

Week 4 (Aug 8-17): Polish and submission
  [ ] Record demo video, deploy the functional demo app
  [ ] Write README, confirm repo public with license visible
  [ ] Optional: build the architecture diagram

Aug 18: Submit by 5:00pm EDT, several hours early
```

---

## SECTION 11 — WINNING INDEX

| Criterion | Score | Why |
|---|---|---|
| Agentic Memory Design | 9.5 | Real 3-tier design, transactionally consistent in one cluster, not a bolted-on vector store |
| Technical Implementation | 9.4 | All 4 CockroachDB tools used with genuine purpose, read-only boundary enforced structurally |
| Real-World Impact | 9.2 | Direct extension of a validated production pattern (70% LLM call reduction at ING), not a hypothetical |
| Production Readiness | 9.7 | A real, live node-failure test with a real log -- not an assumed property |
| Creativity & Originality | 9.3 | The Shell Test itself is the differentiator few other submissions will attempt |
| **WEIGHTED** | **9.42** | |

**Why the Shell Test is the single highest-leverage thing in this
submission:** Production Readiness is its own full judging category,
and "what happens when things go wrong" is asked explicitly. Almost
every competing submission will describe CockroachDB's resilience
properties. Very few will actually kill a node on camera and show the
reads keep working.
