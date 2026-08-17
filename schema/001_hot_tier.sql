-- HOT TIER: exact-match semantic cache, dual-key (query hash + content
-- hash). If the underlying context changes, the content hash changes and
-- stale entries simply never match again.
CREATE TABLE IF NOT EXISTS semantic_cache (
    query_hash   STRING NOT NULL,
    content_hash STRING NOT NULL,
    query_text   STRING NOT NULL,
    response     STRING NOT NULL,
    model_id     STRING,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (query_hash, content_hash)
);
