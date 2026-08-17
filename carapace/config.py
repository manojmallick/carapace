"""Central configuration, all sourced from environment variables."""

import os

# Read path: a CockroachDB connection string for a SELECT-only role
# (carapace_reader). The agent's process only ever gets this URL.
DB_READ_URL = os.environ.get("CARAPACE_DB_READ_URL", "")

# Write path: used ONLY by the Lambda write-back handler (or the local
# fallback writer run with --allow-local-writeback). Never handed to
# the agent's reasoning loop.
DB_WRITE_URL = os.environ.get("CARAPACE_DB_WRITE_URL", "")

AWS_REGION = os.environ.get("AWS_REGION", "eu-central-1")

# Bedrock model for full-miss reasoning (eu. cross-region inference profile).
BEDROCK_MODEL_ID = os.environ.get(
    "CARAPACE_BEDROCK_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
)
FALLBACK_MODEL_ID = os.environ.get(
    "CARAPACE_FALLBACK_MODEL_ID", "eu.amazon.nova-pro-v1:0"
)

# Titan Text Embeddings V2: 1024 dimensions, matches VECTOR(1024) in
# schema/002_warm_tier.sql. If you change one, change both.
EMBED_MODEL_ID = os.environ.get("CARAPACE_EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIMENSIONS = 1024

# Warm-tier cosine-distance acceptance threshold: results farther than
# this are treated as a miss rather than a wrong-but-confident recall.
# Calibrated on Titan V2: paraphrases of the same question land ~0.45-0.55,
# genuinely different questions ~0.7+.
WARM_DISTANCE_THRESHOLD = float(os.environ.get("CARAPACE_WARM_THRESHOLD", "0.6"))

# Name of the deployed write-back Lambda.
WRITEBACK_LAMBDA = os.environ.get("CARAPACE_WRITEBACK_LAMBDA", "carapace-writeback")

AUDIT_LOG_PATH = os.environ.get("CARAPACE_AUDIT_LOG", "carapace_audit.jsonl")
