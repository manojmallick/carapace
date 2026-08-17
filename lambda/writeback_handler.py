"""AWS Lambda: the ONLY component holding a write-capable CockroachDB
credential (CARAPACE_DB_WRITE_URL, set in the Lambda's environment).

Writes all three tiers in ONE transaction: the hot-tier cache entry and
the warm-tier embedding land together or not at all -- the "no
consistency gap between your vector data and your operational database"
property, exercised rather than quoted.
"""

import os

import psycopg


def handler(event: dict, context) -> dict:
    db_url = os.environ["CARAPACE_DB_WRITE_URL"]
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPSERT INTO semantic_cache "
                "(query_hash, content_hash, query_text, response, model_id) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    event["query_hash"],
                    event["content_hash"],
                    event["query_text"],
                    event["response"],
                    event.get("model_id", "unknown"),
                ),
            )
            cur.execute(
                "INSERT INTO query_memory (query_text, response, embedding) "
                "VALUES (%s, %s, %s::vector)",
                (event["query_text"], event["response"], str(event["embedding"])),
            )
            if event.get("convention"):
                cur.execute(
                    "INSERT INTO team_conventions (domain, convention, source) "
                    "VALUES (%s, %s, %s)",
                    (
                        event.get("domain", "general"),
                        event["convention"],
                        event.get("source", "writeback"),
                    ),
                )
        conn.commit()
    return {"status": "written", "query_hash": event["query_hash"]}
