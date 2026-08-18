"""AWS Bedrock: embeddings (Titan V2) and full-miss reasoning (Claude)."""

import json

import boto3

from . import config

_runtime = None


def _client():
    global _runtime
    if _runtime is None:
        _runtime = boto3.client("bedrock-runtime", region_name=config.AWS_REGION)
    return _runtime


def embed(text: str) -> dict:
    """Returns {"embedding": list, "input_tokens": int} -- the real token
    count Bedrock billed for this call, not an estimate."""
    body = json.dumps({
        "inputText": text,
        "dimensions": config.EMBED_DIMENSIONS,
        "normalize": True,
    })
    resp = _client().invoke_model(modelId=config.EMBED_MODEL_ID, body=body)
    parsed = json.loads(resp["body"].read())
    return {
        "embedding": parsed["embedding"],
        "input_tokens": parsed["inputTextTokenCount"],
    }


def reason(query: str, context: str = "", conventions: list = None) -> dict:
    """Returns {"text": str, "model_id": str, "input_tokens": int,
    "output_tokens": int} -- real usage from whichever model actually
    served the call, Claude or the Nova fallback."""
    system = (
        "You are a senior engineer answering questions about a codebase. "
        "Be concrete and brief."
    )
    if conventions:
        system += "\n\nStanding team conventions you MUST follow:\n" + "\n".join(
            f"- {c['convention']}" for c in conventions
        )
    user = query if not context else f"Codebase context:\n{context}\n\nQuestion: {query}"
    last_exc = None
    # Claude first; Nova as fallback -- Anthropic model enrollment on a
    # fresh Bedrock account propagates unevenly for a while, and a memory
    # layer shouldn't die because one model backend hiccuped.
    for model_id in (config.BEDROCK_MODEL_ID, config.FALLBACK_MODEL_ID):
        try:
            resp = _client().converse(
                modelId=model_id,
                system=[{"text": system}],
                messages=[{"role": "user", "content": [{"text": user}]}],
                inferenceConfig={"maxTokens": 1024},
            )
            usage = resp["usage"]
            return {
                "text": resp["output"]["message"]["content"][0]["text"],
                "model_id": model_id,
                "input_tokens": usage["inputTokens"],
                "output_tokens": usage["outputTokens"],
            }
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise last_exc
