# Real Challenges Diary

## Challenge 1: Bedrock's Anthropic models needed EU cross-region + use-case enrollment

**What we assumed:** any `anthropic.claude-*` model ID would work directly
in `us-east-1` once IAM had `bedrock:InvokeModel`.

**What actually happened:** `us-east-1` calls to Titan embeddings threw
`ThrottlingException` on every retry (a fresh account's low default TPS
quota, not real contention), and direct `anthropic.claude-haiku-*` calls
threw `ResourceNotFoundException: Model use case details have not been
submitted for this account`, both AWS-account-specific first-use gates,
not application bugs.

**The fix:** moved the default region to `eu-central-1` (Titan V2 and
Nova worked immediately there) and switched to the `eu.` cross-region
inference profile ID for Claude, which was already enrolled. Also added
a same-call fallback from Claude to `eu.amazon.nova-pro-v1:0`
(`carapace/bedrock.py: reason()`) so a single model's enrollment lag
never blocks the memory layer -- this is a real resilience property of
the reasoning step, discovered by hitting the failure it protects
against, not designed in the abstract.

## Challenge 2: warm-tier distance threshold was miscalibrated for Titan V2

**What we assumed:** a cosine-distance threshold of 0.35 (a reasonable
prior for OpenAI-style embeddings) would separate a paraphrase from an
unrelated query.

**What actually happened:** running the demo, a genuine paraphrase
("What's the right way to deal with exceptions in this API?" vs. "How
should I handle errors in this service?") measured a distance of
0.5045 -- correctly semantically close, but past the 0.35 cutoff, so it
fell all the way through to `full_miss` instead of being served by the
warm tier.

**The fix:** measured actual paraphrase-vs-distinct-query distances on
Titan V2 (paraphrases: ~0.42-0.55; unrelated queries: 0.7+) and moved
`WARM_DISTANCE_THRESHOLD` to 0.6 (`carapace/config.py`). The benchmark
run afterward showed warm-tier hits at distances of 0.26-0.37 once
enough queries existed in memory to compare against.

## Challenge 3: `cockroach start --background` deadlocked cluster startup

**What we assumed:** starting all three local nodes with `cockroach
start --background` and then running `cockroach init` afterward would
bring the cluster up like the single-node dev case.

**What actually happened:** `--background` blocks the `start` command
until the node reports itself healthy -- which never happens for any
node in a fresh multi-node cluster before `cockroach init` runs, since
an uninitialized cluster has no Raft leader yet. All three `start`
invocations hung indefinitely.

**The fix:** switched to `nohup cockroach start ... &` (non-blocking)
for all three nodes, then polled with `cockroach init` in a retry loop
until it succeeded, then polled `cockroach sql -e "SELECT 1"` until the
cluster actually accepted queries (`scripts/local-cluster.sh`).

## Challenge 4: `crdb_internal` access is restricted by default

**What we assumed:** `SELECT crdb_internal.node_id()` in the read probe
would work out of the box, to show which node served each read during
the Shell Test.

**What actually happened:**
`ERROR: Access to crdb_internal and system is restricted. SQLSTATE:
42501` -- CockroachDB 26.2 locks this down for the `carapace_reader`
role by default, "unsupported in production."

**The fix:** the probe (a diagnostic tool, not the app's actual memory
path) sets `allow_unsafe_internals = true` per-session before that one
query (`carapace/read_probe.py`). The application's real reads
(`carapace/reader.py`) never touch `crdb_internal` and needed no
change.

## Challenge 5: `ccloud cluster node drain/stop/start` doesn't exist

**What we assumed:** the ccloud CLI would expose `node drain`, `node
stop`, and `node start` subcommands under `ccloud cluster` for the
Shell Test, matching an earlier draft of this script written before
the CLI was actually installed.

**What actually happened:** `ccloud cluster --help` on the installed
`ccloud 0.8.23` lists no `node` subcommand at all -- only `nodes`
(read-only listing). The real chaos-testing surface CockroachDB Cloud
ships is `ccloud cluster disruption set/get/clear`, which disrupts a
named pod or an entire region/AZ directly.

**The fix:** rewrote `scripts/shell-test.sh` around `ccloud cluster
disruption set <cluster> --region <region> --pods <pod>` /
`disruption clear`, which is arguably a better fit than the imagined
drain/stop/start sequence -- it's the officially supported
disaster-recovery testing primitive, not a repurposed maintenance
operation. Running it against the live cluster requires `ccloud auth
login`, an org-level browser OAuth flow that cannot be completed
non-interactively -- this is queued as a manual pre-demo step.

## Challenge 6: Lambda's execution environment has no default CA cert path

**What we assumed:** deploying `writeback_handler.py` to Lambda with
just `CARAPACE_DB_WRITE_URL` set would connect the same way local
`psycopg` connections did once `~/.postgresql/root.crt` existed
locally.

**What actually happened:** the first real invoke failed with
`root certificate file "/home/sbx_user1051/.postgresql/root.crt" does
not exist` -- Lambda's execution environment has no home directory
psycopg can default into, so `sslmode=verify-full` had nothing to
verify against.

**The fix:** bundled CockroachDB Cloud's CA cert directly into the
deployment zip (`scripts/deploy-lambda.sh` now copies
`~/.postgresql/root.crt` into `build/`) and set `PGSSLROOTCERT=
/var/task/root.crt` as a Lambda environment variable, which libpq
(and therefore psycopg) reads directly. Verified with a real
synchronous `aws lambda invoke` against the live cluster: the row
appeared in both `semantic_cache` and `query_memory`, confirmed via
the read-only `carapace_reader` role afterward.

## Challenge 7: `ccloud cluster disruption` is gated per-organization

**What we assumed:** once `ccloud auth login` succeeded, `ccloud
cluster disruption set` would work against the live cluster the same
way it worked in `--help`.

**What actually happened:** `ccloud cluster nodes <name>` and `ccloud
cluster disruption get <name>` both failed -- first with "unable to
find a cluster" using the routing ID as the name (the actual cluster
name is `cotton-bigfoot`, the id `7c1adba4-...`; the routing ID
`cotton-bigfoot-19571` is a serverless-specific DNS label, not a valid
`ccloud` identifier). Once the right identifier was used, the real
error surfaced: `{"code": 7, "message": "Cluster disruption is not
enabled for this organization"}` (403). The cluster itself is also
Serverless (`plan: BASIC`, `node_count: 0` in `ccloud cluster list
-o json`), which explains why `ccloud cluster nodes` -- documented as
"List nodes for a **dedicated** cluster" -- had nothing to list in the
first place: Serverless is multi-tenant and doesn't expose individual
node/pod identity to the customer at all.

**Where this stands:** node-level chaos-testing via `ccloud` is not
available against this cluster under this org's current entitlements,
regardless of the script. Checked further: `cluster disruption` is
gated to CockroachDB **Advanced**-plan clusters specifically (not
available on Basic/Serverless or Standard/Provisioned), and even on
Advanced, Cockroach Labs' own docs state the org must be explicitly
enrolled by an account team before the feature activates -- it isn't
self-service on any plan tier. On a hackathon deadline, an Advanced
cluster ($476/mo, exceeding the trial credit) bought nothing but the
*chance* of enrollment landing in time, with no guarantee. Decision:
don't chase it. The Shell Test's evidence for this submission comes
from the real local 3-node cluster run below (0 failures across 37
probes, real SIGKILL, no drain, no grace period) -- reported honestly
as local-cluster evidence, not claimed as a cloud result it isn't. The
live CockroachDB Cloud cluster is real and fully wired for everything
else (schema, roles, MCP, Lambda write-back, Bedrock reasoning) --
only the node-kill demonstration runs locally instead.

## Shell Test result (real run, local 3-node cluster, `2026-08-18`)

37 read-loop probes across the full kill/recovery window, SIGKILL'd node
2 with no drain and no grace period. **0 failed reads.** Full log:
`shell_test_results.log`. Latency stayed in the 20-30ms band throughout,
including the instant of the kill -- unsurprising given the client's
multi-host connection string kept it pinned to node 1, which was never
touched; the meaningful result is that killing a node outright caused
zero read failures, not a latency story.
