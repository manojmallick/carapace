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

        # WARM: vector recall over past query embeddings. Every non-hot
        # query pays for one embedding call regardless of hit/miss below.
        t0 = time.time()
        embed_result = bedrock.embed(query_text)
        embedding = embed_result["embedding"]
        candidates = self.reader.check_warm_memory(embedding)
        best = candidates[0] if candidates else None
        warm_hit = best is not None and best["distance"] <= config.WARM_DISTANCE_THRESHOLD
        distance_detail = f"best_distance={best['distance']:.4f}" if best else "no candidates"
        self.audit.record(
            "warm",
            "hit" if warm_hit else "miss",
            (time.time() - t0) * 1000,
            qh,
            detail=f"{distance_detail} embed_input_tokens={embed_result['input_tokens']}",
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
        reason_result = bedrock.reason(query_text, context, conventions)
        response = reason_result["text"]
        self.audit.record(
            "bedrock", "ok", (time.time() - t0) * 1000, qh,
            detail=(
                f"model={reason_result['model_id']} "
                f"input_tokens={reason_result['input_tokens']} "
                f"output_tokens={reason_result['output_tokens']}"
            ),
        )

        t0 = time.time()
        outcome = dispatch_writeback({
            "query_hash": qh,
            "content_hash": ch,
            "query_text": query_text,
            "response": response,
            "embedding": embedding,
            "model_id": reason_result["model_id"],
        })
        self.audit.record("writeback", outcome, (time.time() - t0) * 1000, qh)

        return {
            "tier": "cold" if conventions else "full_miss",
            "response": response,
            "conventions_applied": len(conventions),
            "query_hash": qh,
        }
