"""Tier-selection logic, mocked -- no live database or Bedrock calls.
Verifies the actual branching behavior: a hot hit must never reach
Bedrock at all, a warm hit must embed but never reason, and only a
real full miss may write back."""

from unittest.mock import MagicMock, patch

from carapace.memory import CarapaceMemory


class FakeReader:
    def __init__(self, hot=None, warm=None, cold=None):
        self.hot = hot
        self.warm = warm or []
        self.cold = cold or []

    def check_hot_cache(self, query_hash, content_hash):
        return self.hot

    def check_warm_memory(self, embedding, limit=5):
        return self.warm

    def check_cold_conventions(self, domain):
        return self.cold


def _mem(reader):
    return CarapaceMemory(reader=reader, audit=MagicMock())


@patch("carapace.memory.bedrock")
def test_hot_hit_never_calls_bedrock(mock_bedrock):
    reader = FakeReader(hot={"response": "cached answer", "model_id": "x"})
    result = _mem(reader).query("how do I handle errors?")

    assert result["tier"] == "hot"
    assert result["response"] == "cached answer"
    mock_bedrock.embed.assert_not_called()
    mock_bedrock.reason.assert_not_called()


@patch("carapace.memory.dispatch_writeback")
@patch("carapace.memory.bedrock")
def test_warm_hit_embeds_but_never_reasons_or_writes_back(mock_bedrock, mock_writeback):
    mock_bedrock.embed.return_value = {"embedding": [0.1, 0.2], "input_tokens": 5}
    reader = FakeReader(
        hot=None,
        warm=[{"query_text": "similar q", "response": "reused answer", "distance": 0.1}],
    )
    result = _mem(reader).query("a differently worded question")

    assert result["tier"] == "warm"
    assert result["response"] == "reused answer"
    mock_bedrock.embed.assert_called_once()
    mock_bedrock.reason.assert_not_called()
    mock_writeback.assert_not_called()


@patch("carapace.memory.dispatch_writeback")
@patch("carapace.memory.bedrock")
def test_warm_candidate_beyond_threshold_falls_through_to_full_miss(mock_bedrock, mock_writeback):
    mock_bedrock.embed.return_value = {"embedding": [0.1, 0.2], "input_tokens": 5}
    mock_bedrock.reason.return_value = {
        "text": "fresh answer",
        "model_id": "eu.amazon.nova-pro-v1:0",
        "input_tokens": 10,
        "output_tokens": 20,
    }
    mock_writeback.return_value = "ok"
    # distance 0.9 is well beyond WARM_DISTANCE_THRESHOLD -- must not be
    # treated as a match.
    reader = FakeReader(
        hot=None,
        warm=[{"query_text": "unrelated q", "response": "wrong answer", "distance": 0.9}],
    )
    result = _mem(reader).query("a genuinely new question")

    assert result["tier"] == "full_miss"
    assert result["response"] == "fresh answer"
    mock_bedrock.reason.assert_called_once()
    mock_writeback.assert_called_once()


@patch("carapace.memory.dispatch_writeback")
@patch("carapace.memory.bedrock")
def test_full_miss_applies_cold_conventions_and_writes_back(mock_bedrock, mock_writeback):
    mock_bedrock.embed.return_value = {"embedding": [0.1], "input_tokens": 3}
    mock_bedrock.reason.return_value = {
        "text": "answer using conventions",
        "model_id": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "input_tokens": 8,
        "output_tokens": 12,
    }
    mock_writeback.return_value = "ok"
    reader = FakeReader(hot=None, warm=[], cold=[{"convention": "use snake_case", "source": "x"}])

    result = _mem(reader).query("how should I name variables?", domain="style")

    assert result["tier"] == "cold"
    assert result["conventions_applied"] == 1
    mock_writeback.assert_called_once()
    written_payload = mock_writeback.call_args[0][0]
    assert written_payload["response"] == "answer using conventions"
    assert written_payload["model_id"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
