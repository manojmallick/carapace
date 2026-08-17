# Demo Video Script (under 3 minutes)

Every command below is real and already verified working. Run them live for the
recording -- nothing here is staged or pre-baked. Terminal font size up, screen
recording + mic, no edits needed beyond trimming dead air between commands.

## Setup (do this before hitting record, not on camera)

```bash
cd /Users/manojmallick/Documents/carapace
scripts/local-cluster.sh start
cockroach sql --insecure --host=localhost:26251 -e "CREATE DATABASE IF NOT EXISTS carapace"
CARAPACE_DB_ADMIN_URL="postgresql://root@localhost:26251/carapace?sslmode=disable" scripts/setup-schema.sh
set -a; source .env; set +a
export CARAPACE_DB_READ_URL="postgresql://carapace_reader@localhost:26251,localhost:26252,localhost:26253/carapace?sslmode=disable"
export CARAPACE_DB_WRITE_URL="postgresql://carapace_writer@localhost:26251,localhost:26252,localhost:26253/carapace?sslmode=disable"
export CARAPACE_LOCAL_WRITEBACK=1
```

Have three terminal panes/tabs visible: (1) main command pane, (2) a pane with
`README.md` or the GitHub repo open in a browser tab, (3) the open PR
(https://github.com/cockroachlabs/cockroachdb-skills/pull/24) in another tab.

---

## [0:00-0:15] THE CLAIM

**Say:** "CockroachDB's own pitch is memory that never goes down. Let's actually
test that, instead of just believing it."

**Show:** the README's architecture diagram (scroll to it in the GitHub repo),
then cut to the terminal.

## [0:15-0:50] THE MEMORY WORKING NORMALLY

**Run, live:**
```bash
python3 -m carapace.cli demo
```

**Narrate over the output as it prints:**
- Query 1 (novel) -> full miss -> real Bedrock call -> async Lambda write-back
- Query 2 (exact repeat) -> hot tier, ~10ms, no LLM call
- Query 3 (paraphrase: "What's the right way to deal with exceptions in this
  API?") -> warm tier, vector match at distance 0.505 against the first query
  -- different words, same memory.

## [0:50-1:35] THE SHELL TEST, LIVE

**Say:** "Now the actual test -- kill the exact node the client is connected
to, not a spare one, while the memory keeps getting read from."

**Run, live:**
```bash
scripts/shell-test-local.sh
```

**Narrate as it runs:** point at the terminal the moment the SIGKILL line
prints (`Shell Test: SIGKILL node 1 (pid ...). No drain, no grace.`). The very
next read will actually FAIL -- let it show, don't cut away. Then narrate the
next line succeeding via a different node.

**Say once it finishes:** "One failed read, right at the instant the node
died -- and the very next read, five seconds later, came back from a
different node. That's real failover, not a suspiciously clean zero. It's
all in the committed log at `shell_test_results.log`."

## [1:35-2:00] THE NUMBERS

**Show:** `cat benchmark_results.json` (or have it already open in an editor
tab) while narrating:

**Say:** "75% of queries in this run were served straight from memory -- 35%
exact hits, 40% semantic matches -- avoiding 15 of 20 possible calls to
Bedrock. These are fresh numbers from this build, not a recycled benchmark."

## [2:00-2:25] THE READ-ONLY BOUNDARY

**Run, live:**
```bash
cockroach sql --url "$CARAPACE_DB_READ_URL" -e "INSERT INTO team_conventions (domain, convention) VALUES ('x','x')"
```

**Say, over the `ERROR: user carapace_reader does not have INSERT privilege`
that prints:** "The agent's connection can only ever read -- enforced by the
database itself, not just application code. Every real write goes through a
separate, async AWS Lambda instead."

## [2:25-2:50] THE OPEN-SOURCE PIECE

**Show:** the browser tab with the real, open PR --
https://github.com/cockroachlabs/cockroachdb-skills/pull/24 -- scroll it
briefly.

**Say:** "And a real contribution back -- a skill documenting this exact
pattern, submitted to CockroachDB's own Agent Skills Repo."

## [2:50-3:00] CLOSE

**Say:** "Carapace. Memory that survives what it's supposed to survive."

**Show:** GitHub repo URL (`github.com/manojmallick/carapace`) held on screen
for 3+ seconds.

---

## Cleanup (after recording)

```bash
scripts/local-cluster.sh stop
rm -rf .local-cluster carapace_audit.jsonl
```
