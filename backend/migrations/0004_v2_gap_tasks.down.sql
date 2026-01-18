ALTER TABLE external_action_runs
    DROP COLUMN IF EXISTS executed_at,
    DROP COLUMN IF EXISTS error,
    DROP COLUMN IF EXISTS response,
    DROP COLUMN IF EXISTS provider,
    DROP COLUMN IF EXISTS action_id,
    DROP COLUMN IF EXISTS job_id;

DROP TABLE IF EXISTS attendance_logs;
DROP TABLE IF EXISTS slack_messages;
