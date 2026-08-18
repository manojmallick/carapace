"""Real dollar cost accounting from actual Bedrock token usage.

Every figure here comes from carapace_audit.jsonl's real per-call
input/output token counts (carapace/bedrock.py logs the exact usage
Bedrock billed for), multiplied by public on-demand Bedrock pricing.
Nothing here is an estimated token count -- only the per-token dollar
rates are external inputs, and those are cited below.

Pricing as of 2026-08, on-demand, source: AWS Bedrock pricing pages and
cross-checked third-party trackers (pricepertoken.com, AWS re:Post
community confirmation for Titan V2). Not fetched live -- if you're
reading this months later, re-verify against
https://aws.amazon.com/bedrock/pricing/ before trusting these numbers.
"""

import json
import re

# $ per token (not per 1K/1M -- converted once, here, so call sites never
# have to remember which denominator a rate is quoted in).
PRICE_PER_TOKEN = {
    "eu.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.00e-6, "output": 5.00e-6},
    "anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.00e-6, "output": 5.00e-6},
    "eu.amazon.nova-pro-v1:0": {"input": 0.80e-6, "output": 3.20e-6},
    "amazon.nova-pro-v1:0": {"input": 0.80e-6, "output": 3.20e-6},
}
TITAN_EMBED_PRICE_PER_TOKEN = 0.02e-6


def summarize(audit_log_path: str = "carapace_audit.jsonl") -> dict:
    reason_cost = embed_cost = 0.0
    reason_calls = embed_calls = 0
    reason_in_tokens = reason_out_tokens = embed_in_tokens = 0
    hits = misses = 0

    with open(audit_log_path) as f:
        for line in f:
            e = json.loads(line)
            if e["tier"] == "bedrock":
                m = re.search(r"model=(\S+) input_tokens=(\d+) output_tokens=(\d+)", e["detail"])
                model_id, in_tok, out_tok = m.group(1), int(m.group(2)), int(m.group(3))
                rate = PRICE_PER_TOKEN.get(model_id, PRICE_PER_TOKEN["eu.amazon.nova-pro-v1:0"])
                reason_cost += in_tok * rate["input"] + out_tok * rate["output"]
                reason_in_tokens += in_tok
                reason_out_tokens += out_tok
                reason_calls += 1
            elif e["tier"] == "warm":
                m = re.search(r"embed_input_tokens=(\d+)", e["detail"])
                if m:
                    tok = int(m.group(1))
                    embed_cost += tok * TITAN_EMBED_PRICE_PER_TOKEN
                    embed_in_tokens += tok
                    embed_calls += 1
            elif e["tier"] == "hot":
                if e["outcome"] == "hit":
                    hits += 1
                else:
                    misses += 1

    total_queries = hits + misses
    actual_cost = reason_cost + embed_cost

    # What the same query mix would have cost with no memory at all: every
    # query pays the real average embed cost AND the real average reasoning
    # cost measured in this run -- not a guessed baseline.
    avg_embed_cost = (embed_cost / embed_calls) if embed_calls else 0.0
    avg_reason_cost = (reason_cost / reason_calls) if reason_calls else 0.0
    no_memory_cost = total_queries * (avg_embed_cost + avg_reason_cost)

    reduction_pct = (
        round((no_memory_cost - actual_cost) / no_memory_cost * 100, 1)
        if no_memory_cost else 0.0
    )

    return {
        "total_queries": total_queries,
        "reasoning_calls": reason_calls,
        "reasoning_input_tokens": reason_in_tokens,
        "reasoning_output_tokens": reason_out_tokens,
        "reasoning_cost_usd": round(reason_cost, 6),
        "embed_calls": embed_calls,
        "embed_input_tokens": embed_in_tokens,
        "embed_cost_usd": round(embed_cost, 6),
        "actual_total_cost_usd": round(actual_cost, 6),
        "no_memory_baseline_cost_usd": round(no_memory_cost, 6),
        "cost_reduction_pct": reduction_pct,
    }


if __name__ == "__main__":
    print(json.dumps(summarize(), indent=2))
