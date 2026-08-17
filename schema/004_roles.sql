-- Access control, enforced by the database, not by convention:
--   carapace_reader -- SELECT only. This is the ONLY credential the
--                      agent's process ever receives.
--   carapace_writer -- INSERT/UPSERT. Lives ONLY in the write-back
--                      Lambda's environment.
CREATE ROLE IF NOT EXISTS carapace_reader LOGIN;
GRANT SELECT ON TABLE semantic_cache, query_memory, team_conventions TO carapace_reader;

CREATE ROLE IF NOT EXISTS carapace_writer LOGIN;
GRANT SELECT, INSERT, UPDATE ON TABLE semantic_cache, query_memory, team_conventions TO carapace_writer;
