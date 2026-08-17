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

## Challenge 8: local write-back's daemon thread can die before it writes

**What we assumed:** `CARAPACE_LOCAL_WRITEBACK=1`'s dev-convenience path
(`writeback.py: _dispatch_local`, a daemon thread standing in for the
real Lambda) would reliably complete its write shortly after
`carapace.cli ask` printed its response and exited.

**What actually happened:** a first Shell Test run showed `rows=0`
across every single probe -- the table was empty. `ask` is a one-shot
process: it prints the response and exits immediately, and daemon
threads do not keep a process alive, so the background write was
killed mid-flight before it reached CockroachDB.

**The fix:** this is specific to the local dev fallback, not the real
architecture -- the actual `aws lambda invoke` write-back path has no
such lifecycle dependency, since the Lambda's own process is what
stays alive until the write completes. For local runs, use
`carapace.cli demo`, which sleeps in-process between queries and so
lets the same daemon thread finish before the process exits; the Shell
Test log below was captured after populating memory this way, and
shows `rows=1` throughout -- real data, not an empty table.

## Challenge 9: the first Shell Test never actually proved failover

**What we assumed:** killing node 2 while the read probe ran (the
original Shell Test) was sufficient evidence that the memory layer
survives a node failure -- 0 failed reads across 36-37 probes,
consistently.

**What actually happened:** every single probe line in that log reads
`via_node=1`, before, during, and after the kill -- because the
client's multi-host connection string (`localhost:26251,...252,...253`)
always connects to the first reachable host, and node 1 was never
touched. The test proved an *idle, untouched node kept working*, which
is trivially true and proves nothing about failover. That log is kept
at `shell_test_results_node2.log` for the record, but it is not the
headline evidence -- it isn't a rigorous resilience test.

**The fix:** generalized `scripts/local-cluster.sh` (`restart-node
<n>`) and `scripts/shell-test-local.sh` (now takes a target node
number, second argument) to kill **node 1** instead -- the node the
client actually depends on under normal conditions. That is the real
test: does the client actually fail over to a surviving node, not just
"does an unrelated node keep responding."

## Shell Test result (real run, local 3-node cluster, kill node 1, `2026-08-18`)

Real failover, not just an untouched node staying up. Full log
committed at `shell_test_results.log`:

- Before the kill: every read served via node 1 (`via_node=1`).
- `02:46:42` -- SIGKILL node 1. The very next probe **failed** (the
  only failure in the run): a 4056.5ms `OperationalError` showing
  libpq walking all three hosts in the connection string and hitting
  `Connection refused` on the now-dead node 1 and a `connection
  timeout expired` reaching node 2, before the client gave up on that
  attempt.
- `02:46:47`, five seconds after the kill -- the next probe succeeds,
  now served via node 3 (`via_node=3`). Every read for the rest of the
  outage window is served via node 3.
- `02:47:07` -- node 1 restarted; traffic reverts to `via_node=1` once
  it rejoins.

**34 probes, 1 failed (97% success including the failover transition
itself), full recovery within ~5 seconds of the kill.** Reporting the
one real failure instead of a suspiciously clean zero -- a distributed
system failing over in a handful of seconds, once, at the exact
instant a node dies, is a more credible resilience story than a
zero-failure number that turns out not to have tested failover at all.
