"""Every memory access -- hit, miss, or write -- is logged with tier,
latency, and outcome. This is what "observable" means in practice."""

import json
import time

from . import config


class CarapaceAuditLog:
    def __init__(self, log_path: str = None):
        self.log_path = log_path or config.AUDIT_LOG_PATH

    def record(self, tier: str, outcome: str, latency_ms: float, query_hash: str, detail: str = ""):
        entry = {
            "timestamp": time.time(),
            "tier": tier,        # "hot", "warm", "cold", "bedrock", "writeback"
            "outcome": outcome,  # "hit", "miss", "error", "ok"
            "latency_ms": round(latency_ms, 2),
            "query_hash": query_hash,
        }
        if detail:
            entry["detail"] = detail
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
