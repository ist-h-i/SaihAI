ALTER TABLE autonomous_actions
    ADD COLUMN action_payload JSONB;

CREATE TABLE external_action_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    job_id VARCHAR(100) REFERENCES execution_jobs(job_id),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    action_type VARCHAR(50) NOT NULL,
    provider VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    request_payload JSONB,
    response_payload JSONB,
    error TEXT,
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX external_action_runs_job_idx ON external_action_runs (job_id);
CREATE INDEX external_action_runs_action_idx ON external_action_runs (action_id);

CREATE TABLE input_ingestion_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    items_inserted INTEGER DEFAULT 0,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    metadata JSONB,
    error TEXT
);

CREATE INDEX input_ingestion_runs_source_idx ON input_ingestion_runs (source_type);
CREATE INDEX input_ingestion_runs_status_idx ON input_ingestion_runs (status);
