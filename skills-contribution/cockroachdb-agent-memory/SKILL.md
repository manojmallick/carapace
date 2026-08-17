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
   query embeddings, for fuzzy recall when the hot tier misses. Keep
   the embedding column's VECTOR dimension and the embedding model's
   output dimension defined in ONE shared config value.
4. Create a cold-tier conventions table with row-level TTL keyed on a
   last_affirmed_at column, so stale conventions decay unless re-affirmed.
5. Connect the agent's READ path through the CockroachDB Cloud Managed
   MCP Server in its default read-only mode -- never give the agent's
   live reasoning loop direct write access. Back it with a SELECT-only
   SQL role so the boundary is enforced by the database, not convention.
6. Route all WRITES through a separate, async path (e.g. a Lambda
   function) holding the only write-capable credential, and write the
   hot-tier row and warm-tier embedding in one transaction so the
   vector data can never drift from the operational data.
7. Before calling the memory layer "production-ready," run a real
   node-failure test: drain and stop one node via ccloud CLI while a
   read-loop probe runs continuously, and verify reads keep succeeding.

## Safety boundaries
- Never let the agent's live reasoning path hold write access to the
  memory store -- writes should be async and auditable, reads should
  be immediate and safe.
- Never claim resilience without having actually run a node-failure
  test -- an assumed property is not a verified one.
