CREATE TABLE hitl_states (
    thread_id VARCHAR(100) PRIMARY KEY,
    status VARCHAR(30) NOT NULL,
    approval_request_id VARCHAR(100),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    state_payload JSONB,
    slack_channel VARCHAR(50),
    slack_message_ts VARCHAR(50),
    slack_thread_ts VARCHAR(50),
    version INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX hitl_states_status_idx ON hitl_states (status);
CREATE INDEX hitl_states_action_idx ON hitl_states (action_id);

CREATE TABLE hitl_approval_requests (
    approval_request_id VARCHAR(100) PRIMARY KEY,
    thread_id VARCHAR(100) REFERENCES hitl_states(thread_id),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    status VARCHAR(30) NOT NULL,
    idempotency_key VARCHAR(200) NOT NULL,
    requested_by VARCHAR(50),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    slack_channel VARCHAR(50),
    slack_message_ts VARCHAR(50),
    slack_thread_ts VARCHAR(50)
);

CREATE UNIQUE INDEX hitl_approval_requests_idempotency_idx ON hitl_approval_requests (idempotency_key);
CREATE INDEX hitl_approval_requests_thread_idx ON hitl_approval_requests (thread_id);

CREATE TABLE hitl_audit_logs (
    audit_id VARCHAR(100) PRIMARY KEY,
    thread_id VARCHAR(100),
    event_type VARCHAR(50) NOT NULL,
    actor VARCHAR(50),
    correlation_id VARCHAR(100),
    detail JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX hitl_audit_logs_thread_idx ON hitl_audit_logs (thread_id);

CREATE TABLE execution_jobs (
    job_id VARCHAR(100) PRIMARY KEY,
    thread_id VARCHAR(100) REFERENCES hitl_states(thread_id),
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    status VARCHAR(30) NOT NULL,
    idempotency_key VARCHAR(200) NOT NULL,
    enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    last_error TEXT
);

CREATE UNIQUE INDEX execution_jobs_idempotency_idx ON execution_jobs (idempotency_key);
CREATE INDEX execution_jobs_status_idx ON execution_jobs (status);

CREATE TABLE watchdog_jobs (
    job_id VARCHAR(100) PRIMARY KEY,
    status VARCHAR(20) NOT NULL,
    payload JSONB,
    enqueued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    run_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    attempts INTEGER DEFAULT 0,
    last_error TEXT
);

CREATE INDEX watchdog_jobs_status_idx ON watchdog_jobs (status);

CREATE TABLE watchdog_alerts (
    alert_id VARCHAR(100) PRIMARY KEY,
    thread_id VARCHAR(100),
    project_id VARCHAR(10) REFERENCES projects(project_id),
    summary TEXT NOT NULL,
    severity VARCHAR(10) NOT NULL,
    status VARCHAR(20) NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX watchdog_alerts_status_idx ON watchdog_alerts (status);
