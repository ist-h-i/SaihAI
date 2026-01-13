CREATE TABLE external_action_runs (
    run_id VARCHAR(50) PRIMARY KEY,
    job_id VARCHAR(50),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    action_type VARCHAR(50),
    provider VARCHAR(50),
    status VARCHAR(40),
    action_payload JSONB,
    response JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE input_ingestion_runs (
    run_id VARCHAR(50) PRIMARY KEY,
    source_type VARCHAR(50),
    status VARCHAR(40),
    items_inserted INTEGER,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB
);

CREATE INDEX external_action_runs_action_id_idx ON external_action_runs (action_id);
CREATE INDEX input_ingestion_runs_source_type_idx ON input_ingestion_runs (source_type);
