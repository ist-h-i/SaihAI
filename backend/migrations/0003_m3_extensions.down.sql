DROP TABLE IF EXISTS input_ingestion_runs;
DROP TABLE IF EXISTS external_action_runs;

ALTER TABLE autonomous_actions
    DROP COLUMN action_payload;
