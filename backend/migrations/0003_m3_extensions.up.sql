CREATE TABLE external_action_runs (
    run_id SERIAL PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL,
    status VARCHAR(30) DEFAULT 'queued',
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE input_ingestion_runs (
    run_id SERIAL PRIMARY KEY,
    source VARCHAR(100),
    status VARCHAR(30) DEFAULT 'queued',
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE action_payload (
    payload_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES external_action_runs(run_id),
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
