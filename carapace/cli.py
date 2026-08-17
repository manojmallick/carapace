"""Carapace demo CLI.

    python -m carapace.cli demo      # 3-query walk through all tiers
    python -m carapace.cli ask "..." # single query
"""

import json
import sys
import time

from .memory import CarapaceMemory

DEMO_CONTEXT = (
    "Service: payments-api (Python/FastAPI). Errors are currently raised "
    "ad hoc; there is a shared exceptions.py with ApiError(status, code, "
    "message) that maps to RFC7807 responses via one exception handler."
)


def _run(mem: CarapaceMemory, query: str, label: str):
    print(f"\n=== {label}\n    Q: {query}")
    t0 = time.time()
    result = mem.query(query, context=DEMO_CONTEXT, domain="error-handling")
    ms = (time.time() - t0) * 1000
    print(f"    tier={result['tier']}  latency={ms:.0f}ms")
    if result.get("matched_query"):
        print(f"    warm match ({result['distance']:.3f}): {result['matched_query']!r}")
    if result.get("conventions_applied"):
        print(f"    conventions applied: {result['conventions_applied']}")
    print(f"    A: {result['response'][:300]}")
    return result


def demo():
    mem = CarapaceMemory()
    novel = "How should I handle errors in this service?"
    _run(mem, novel, "QUERY 1 -- novel: full miss -> Bedrock -> Lambda write-back")
    print("    ...waiting 3s for the async write-back to land...")
    time.sleep(3)
    _run(mem, novel, "QUERY 2 -- exact repeat: HOT tier (dual-hash match)")
    _run(mem, "What's the right way to deal with exceptions in this API?",
         "QUERY 3 -- paraphrase: WARM tier (vector recall)")


def ask(query: str):
    result = CarapaceMemory().query(query, context=DEMO_CONTEXT)
    print(json.dumps({k: v for k, v in result.items() if k != "response"}, indent=2))
    print(result["response"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "demo":
        demo()
    elif cmd == "ask" and len(sys.argv) > 2:
        ask(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
