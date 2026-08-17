"""Tier orchestration: hot -> warm -> cold -> Bedrock -> async write-back."""

import time

from . import bedrock, config
from .audit import CarapaceAuditLog
from .hashing import content_hash, query_hash
from .reader import AgentMemoryReader
from .writeback import dispatch_writeback


class CarapaceMemory:
    def __init__(self, reader: AgentMemoryReader = None, audit: CarapaceAuditLog = None):
        self.reader = reader or AgentMemoryReader()
        self.audit = audit or CarapaceAuditLog()

    def query(self, query_text: str, context: str = "", domain: str = "general") -> dict:
        qh = query_hash(query_text)
        ch = content_hash(context)

        # HOT: exact dual-key match.
        t0 = time.time()
        hot = self.reader.check_hot_cache(qh, ch)
        self.audit.record("hot", "hit" if hot else "miss", (time.time() - t0) * 1000, qh)
        if hot:
            return {"tier": "hot", "response": hot["response"], "query_hash": qh}

        # WARM: vector recall over past query embeddings.
        t0 = time.time()
        embedding = bedrock.embed(query_text)
        candidates = self.reader.check_warm_memory(embedding)
        best = candidates[0] if candidates else None
        warm_hit = best is not None and best["distance"] <= config.WARM_DISTANCE_THRESHOLD
        self.audit.record(
            "warm",
            "hit" if warm_hit else "miss",
            (time.time() - t0) * 1000,
            qh,
            detail=f"best_distance={best['distance']:.4f}" if best else "no candidates",
        )
        if warm_hit:
            return {
                "tier": "warm",
                "response": best["response"],
                "matched_query": best["query_text"],
                "distance": best["distance"],
                "query_hash": qh,
            }

        # COLD: standing conventions shape the fresh answer.
        t0 = time.time()
        conventions = self.reader.check_cold_conventions(domain)
        self.audit.record(
            "cold", "hit" if conventions else "miss", (time.time() - t0) * 1000, qh
        )

        # FULL MISS: Bedrock generates, then the interaction is written
        # back asynchronously via Lambda -- never through self.reader,
        # which structurally cannot write.
        t0 = time.time()
        response = bedrock.reason(query_text, context, conventions)
        self.audit.record("bedrock", "ok", (time.time() - t0) * 1000, qh)

        t0 = time.time()
        outcome = dispatch_writeback({
            "query_hash": qh,
            "content_hash": ch,
            "query_text": query_text,
            "response": response,
            "embedding": embedding,
            "model_id": config.BEDROCK_MODEL_ID,
        })
        self.audit.record("writeback", outcome, (time.time() - t0) * 1000, qh)

        return {
            "tier": "cold" if conventions else "full_miss",
            "response": response,
            "conventions_applied": len(conventions),
            "query_hash": qh,
        }
