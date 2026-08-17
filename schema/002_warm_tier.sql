-- WARM TIER: fuzzy semantic recall via Distributed Vector Indexing.
-- VECTOR(1024) matches Titan Text Embeddings V2 (config.EMBED_DIMENSIONS).
CREATE TABLE IF NOT EXISTS query_memory (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text STRING NOT NULL,
    response   STRING NOT NULL,
    embedding  VECTOR(1024) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE VECTOR INDEX IF NOT EXISTS query_memory_embedding_idx
    ON query_memory (embedding);
