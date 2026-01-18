CREATE TABLE hitl_states (
    thread_id VARCHAR(100) PRIMARY KEY,
    status VARCHAR(30) NOT NULL,
    approval_request_id VARCHAR(50),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    checkpoint BYTEA,
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hitl_approval_requests (
    approval_request_id VARCHAR(50) PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    requested_by VARCHAR(50),
    requested_at TIMESTAMP,
    status VARCHAR(30) NOT NULL,
    slack_channel VARCHAR(100),
    slack_message_ts VARCHAR(50),
    slack_thread_ts VARCHAR(50),
    idempotency_key VARCHAR(100)
);

CREATE TABLE hitl_audit_logs (
    audit_id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    approval_request_id VARCHAR(50),
    event_type VARCHAR(50) NOT NULL,
    actor VARCHAR(50),
    correlation_id VARCHAR(50),
    detail JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE execution_jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    status VARCHAR(30) NOT NULL,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error TEXT,
    result JSONB
);

CREATE TABLE watchdog_jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    status VARCHAR(30) NOT NULL,
    payload JSONB,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    error TEXT
);

CREATE TABLE watchdog_alerts (
    alert_id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) REFERENCES watchdog_jobs(job_id),
    project_id VARCHAR(50),
    severity VARCHAR(20),
    title VARCHAR(200),
    message TEXT,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX hitl_approval_requests_thread_id_idx ON hitl_approval_requests (thread_id);
CREATE INDEX hitl_audit_logs_thread_id_idx ON hitl_audit_logs (thread_id);
CREATE INDEX execution_jobs_action_id_idx ON execution_jobs (action_id);
CREATE INDEX watchdog_alerts_project_id_idx ON watchdog_alerts (project_id);

