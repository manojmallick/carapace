# Devpost Submission Draft

Copy each section into the matching Devpost field. Fill in `[VIDEO URL]` once
the demo is uploaded and `[DEVPOST-VISIBLE handle]` if the form asks for a
team/member handle separate from GitHub.

---

## Tagline (short, ~120 chars)

A coding agent's 3-tier memory on CockroachDB -- proven against a real node failure, not just designed to survive one.

## Inspiration

The hackathon's own framing was a direct challenge: "an agent whose memory
goes offline doesn't degrade gracefully, it stops." Most agent-memory demos
show a database storing data correctly. Almost none show what happens when a
node actually goes down mid-query -- the one scenario CockroachDB is
specifically built for. Carapace exists to close that gap: build the memory
layer, then actually kill a cluster node and report what really happened,
instead of describing CockroachDB's resilience secondhand.

## What it does

Carapace gives an AI coding agent persistent memory across three tiers, all
in one CockroachDB cluster so nothing ever drifts out of consistency:

- **Hot** -- exact-match cache, keyed on a dual hash of the query *and* its
  underlying context, so a changed file silently invalidates stale entries.
- **Warm** -- fuzzy semantic recall via CockroachDB's Distributed Vector
  Indexing: a differently-worded question that means the same thing still
  hits memory (measured 0.505 cosine distance between two real paraphrases).
- **Cold** -- long-term team conventions with row-level TTL decay, so
  standing corrections shape fresh answers but expire if never reaffirmed.

The agent's live reasoning loop can only *read* -- enforced both in code (no
write method exists on the reader class) and in the database (a SELECT-only
SQL role). Every write goes through a real, deployed, asynchronous AWS Lambda
instead, so a slow or failed write never blocks the agent's response.

Then it's stress-tested for real: a script SIGKILLs a live cluster node
mid-session while a continuous read probe runs, and the actual log --
0 failed reads across 36 probes -- is committed to the repo, not asserted in
a README.

## How we built it

- **CockroachDB Cloud** -- hot/warm/cold schema, a SELECT-only `carapace_reader`
  role and an INSERT/UPDATE-only `carapace_writer` role (no DELETE), a
  Distributed Vector Index on the warm tier, and the CockroachDB Cloud
  Managed MCP Server registered as the agent's read-only boundary.
- **AWS Bedrock** -- Claude for full-miss reasoning (with a same-call fallback
  to Amazon Nova if a model's account enrollment lags), Titan V2 for
  embeddings.
- **AWS Lambda** -- `carapace-writeback`, a real deployed function holding the
  only write-capable database credential, invoked asynchronously and writing
  the hot-tier row and warm-tier embedding together in one transaction.
- **ccloud CLI** -- cluster identification and authentication, and a real
  investigation into CockroachDB Cloud's `cluster disruption` chaos-testing
  API (see Challenges).
- **CockroachDB Agent Skills Repo** -- a real, open PR
  ([cockroachlabs/cockroachdb-skills#24](https://github.com/cockroachlabs/cockroachdb-skills/pull/24))
  contributing the pattern back as a skill, validated with the target repo's
  own spec validator before submission.

## Challenges we ran into

Documented in full, with the exact error messages, in
[`docs/CHALLENGES.md`](https://github.com/manojmallick/carapace/blob/main/docs/CHALLENGES.md)
-- eight real problems, not a sanitized list. The two worth calling out:

1. **The vector-distance threshold was wrong for the actual embedding model.**
   A threshold borrowed from a different model's typical range (0.35) missed
   a genuine paraphrase that measured 0.505 on Titan V2. Recalibrated against
   real measured distances, not assumed ones.
2. **The cloud chaos-testing API turned out to be gated.** `ccloud cluster
   disruption` -- the CockroachDB Cloud mechanism for killing a real node --
   requires an Advanced-plan cluster *and* explicit enrollment by a Cockroach
   Labs account team, not self-service on any plan. Rather than quietly
   dropping the Shell Test or chasing an uncertain paid upgrade on deadline
   day, we ran the equivalent test against a real local 3-node cluster
   (genuine SIGKILL, no drain, no grace period) and documented the cloud
   limitation honestly instead of hiding it.

## Accomplishments that we're proud of

- A real, committed log of a cluster node dying and the memory layer
  surviving it -- not a claim.
- All 4 CockroachDB tools used with genuine purpose, not the minimum 2.
- A real PR open against CockroachDB's own Agent Skills Repo, validated with
  their own tooling before submission.
- Every number in the README was measured on this build today -- no recycled
  benchmarks from other projects.

## What we learned

That "production-ready" is a claim worth being suspicious of until it's been
tested against an actual failure -- and that the gap between "the CLI has a
command for this" and "this feature is actually available to your account"
is exactly the kind of thing that only shows up by trying the real thing,
not by reading the docs.

## What's next

- Run the equivalent Shell Test against CockroachDB Cloud itself once
  `cluster disruption` enrollment is available.
- Replace the demo's fixed context paragraph with a real, ranked lookup
  against the actual target codebase for the full-miss reasoning step.

## Built With

cockroachdb, cockroachdb-cloud, aws-bedrock, aws-lambda, python, psycopg,
distributed-vector-indexing, mcp, ccloud-cli

## Try it out

- Repo: https://github.com/manojmallick/carapace
- Agent Skills Repo PR: https://github.com/cockroachlabs/cockroachdb-skills/pull/24
- Demo video: [VIDEO URL]
