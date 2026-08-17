"""The agent's ONLY path to CockroachDB memory.

Two layers of enforcement, neither of which is a convention:
1. Structural: no write method exists on this class at all.
2. Database: the connection string is for the carapace_reader role,
   which holds SELECT-only grants (schema/004_roles.sql). Even a bug
   that smuggled an INSERT through would be rejected by CockroachDB.

All writes happen exclusively through the Lambda write-back path
(lambda/writeback_handler.py), never from agent-issued calls.
"""

import psycopg

from . import config


class AgentMemoryReader:
    def __init__(self, db_url: str = None):
        self._db_url = db_url or config.DB_READ_URL
        if not self._db_url:
            raise RuntimeError("CARAPACE_DB_READ_URL is not set")

    def _query(self, sql: str, params=()):
        # A fresh short-lived connection per read keeps the probe honest
        # during the Shell Test: every read renegotiates with whatever
        # nodes are actually alive, rather than coasting on a session
        # opened before the failure.
        with psycopg.connect(self._db_url, connect_timeout=5) as conn:
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()

    def check_hot_cache(self, query_hash: str, content_hash: str):
        rows = self._query(
            "SELECT response, model_id FROM semantic_cache "
            "WHERE query_hash = %s AND content_hash = %s",
            (query_hash, content_hash),
        )
        return {"response": rows[0][0], "model_id": rows[0][1]} if rows else None

    def check_warm_memory(self, query_embedding: list, limit: int = 5):
        rows = self._query(
            "SELECT query_text, response, embedding <=> %s::vector AS distance "
            "FROM query_memory ORDER BY distance LIMIT %s",
            (str(query_embedding), limit),
        )
        return [
            {"query_text": r[0], "response": r[1], "distance": float(r[2])}
            for r in rows
        ]

    def check_cold_conventions(self, domain: str):
        rows = self._query(
            "SELECT convention, source FROM team_conventions WHERE domain = %s",
            (domain,),
        )
        return [{"convention": r[0], "source": r[1]} for r in rows]

    # No write_* method exists on this class. Intentionally.
