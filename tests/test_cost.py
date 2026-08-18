import json

from carapace import cost

AUDIT_LINES = [
    {"tier": "hot", "outcome": "miss", "latency_ms": 1, "query_hash": "a"},
    {
        "tier": "warm",
        "outcome": "miss",
        "latency_ms": 1,
        "query_hash": "a",
        "detail": "no candidates embed_input_tokens=10",
    },
    {
        "tier": "bedrock",
        "outcome": "ok",
        "latency_ms": 1,
        "query_hash": "a",
        "detail": "model=eu.amazon.nova-pro-v1:0 input_tokens=100 output_tokens=50",
    },
    {"tier": "hot", "outcome": "hit", "latency_ms": 1, "query_hash": "b"},
]


def test_summarize_computes_real_cost_from_token_counts(tmp_path):
    log = tmp_path / "audit.jsonl"
    log.write_text("\n".join(json.dumps(e) for e in AUDIT_LINES) + "\n")

    result = cost.summarize(str(log))

    assert result["reasoning_calls"] == 1
    assert result["reasoning_input_tokens"] == 100
    assert result["reasoning_output_tokens"] == 50
    assert result["embed_calls"] == 1
    assert result["embed_input_tokens"] == 10
    # Nova Pro: 100 * 0.80e-6 + 50 * 3.20e-6 = 0.00008 + 0.00016 = 0.00024
    assert abs(result["reasoning_cost_usd"] - 0.00024) < 1e-9
    assert result["actual_total_cost_usd"] > 0
    assert 0 <= result["cost_reduction_pct"] <= 100


def test_summarize_handles_all_hot_hits_with_zero_llm_cost(tmp_path):
    log = tmp_path / "audit.jsonl"
    lines = [{"tier": "hot", "outcome": "hit", "latency_ms": 1, "query_hash": "a"}] * 5
    log.write_text("\n".join(json.dumps(e) for e in lines) + "\n")

    result = cost.summarize(str(log))

    assert result["reasoning_calls"] == 0
    assert result["actual_total_cost_usd"] == 0.0
    assert result["cost_reduction_pct"] == 0.0  # no baseline calls to compare against
