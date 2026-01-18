CREATE TABLE external_action_runs (
    run_id VARCHAR(50) PRIMARY KEY,
    status VARCHAR(30) NOT NULL,
    provider VARCHAR(50),
    action_type VARCHAR(50),
    job_id VARCHAR(50),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    action_payload JSONB,
    response JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE input_ingestion_runs (
    run_id VARCHAR(50) PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL,
    items_inserted INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error TEXT,
    metadata JSONB
);

CREATE INDEX external_action_runs_action_id_idx ON external_action_runs (action_id);
CREATE INDEX input_ingestion_runs_source_type_idx ON input_ingestion_runs (source_type);

