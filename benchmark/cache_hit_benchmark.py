"""Fresh benchmark, measured on THIS build against a real cluster.

Runs benchmark_queries.json (a realistic developer-query sequence with
repeats and paraphrases) through the full 3-tier pipeline and reports
per-tier hit rates and the latency distribution -- whatever they
actually are.

    python3 benchmark/cache_hit_benchmark.py
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from carapace.cli import DEMO_CONTEXT  # noqa: E402
from carapace.memory import CarapaceMemory  # noqa: E402


def run_benchmark(queries: list, mem: CarapaceMemory) -> dict:
    counts = {"hot": 0, "warm": 0, "cold": 0, "full_miss": 0}
    latencies = []

    for i, q in enumerate(queries, 1):
        start = time.time()
        outcome = mem.query(q, context=DEMO_CONTEXT)
        elapsed = (time.time() - start) * 1000
        counts[outcome["tier"]] += 1
        latencies.append(elapsed)
        print(f"[{i}/{len(queries)}] {outcome['tier']:9s} {elapsed:7.0f}ms  {q[:60]}")
        if outcome["tier"] == "full_miss":
            time.sleep(2)  # let the async write-back land before any repeat

    total = len(queries)
    latencies.sort()
    return {
        "total_queries": total,
        "hot_hit_rate": round(counts["hot"] / total, 3),
        "warm_hit_rate": round(counts["warm"] / total, 3),
        "cold_hit_rate": round(counts["cold"] / total, 3),
        "full_miss_rate": round(counts["full_miss"] / total, 3),
        "llm_calls_avoided": counts["hot"] + counts["warm"],
        "avg_latency_ms": round(sum(latencies) / total, 1),
        "p50_latency_ms": round(latencies[total // 2], 1),
        "p95_latency_ms": round(latencies[min(int(total * 0.95), total - 1)], 1),
    }


if __name__ == "__main__":
    with open(os.path.join(os.path.dirname(__file__), "benchmark_queries.json")) as f:
        queries = json.load(f)

    results = run_benchmark(queries, CarapaceMemory())
    out = os.path.join(os.path.dirname(__file__), "..", "benchmark_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))
