-- COLD TIER: long-term convention memory with TTL-based decay.
-- Conventions expire 180 days after they were last affirmed; re-affirming
-- (an UPSERT touching last_affirmed_at) keeps a live convention alive.
CREATE TABLE IF NOT EXISTS team_conventions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain           STRING NOT NULL,
    convention       STRING NOT NULL,
    source           STRING,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_affirmed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    INDEX (domain)
) WITH (
    ttl_expiration_expression = $$ (last_affirmed_at + INTERVAL '180 days') $$,
    ttl_job_cron = '@daily'
);
