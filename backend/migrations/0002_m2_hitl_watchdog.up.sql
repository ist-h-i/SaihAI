CREATE TABLE hitl_states (
    state_id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    status VARCHAR(40),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hitl_approval_requests (
    approval_request_id VARCHAR(50) PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    status VARCHAR(40),
    requested_by VARCHAR(100),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE TABLE hitl_audit_logs (
    audit_id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    approval_request_id VARCHAR(50),
    event_type VARCHAR(50),
    actor VARCHAR(100),
    correlation_id VARCHAR(100),
    detail JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE execution_jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    action_id INTEGER REFERENCES autonomous_actions(action_id),
    approval_request_id VARCHAR(50),
    status VARCHAR(40),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB
);

CREATE TABLE watchdog_jobs (
    job_id VARCHAR(50) PRIMARY KEY,
    status VARCHAR(40),
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    summary TEXT
);

CREATE TABLE watchdog_alerts (
    alert_id SERIAL PRIMARY KEY,
    job_id VARCHAR(50) REFERENCES watchdog_jobs(job_id),
    project_id VARCHAR(50) REFERENCES projects(project_id),
    user_id VARCHAR(50) REFERENCES users(user_id),
    severity VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX hitl_states_thread_id_idx ON hitl_states (thread_id);
CREATE INDEX hitl_approval_requests_thread_id_idx ON hitl_approval_requests (thread_id);
CREATE INDEX hitl_audit_logs_thread_id_idx ON hitl_audit_logs (thread_id);
CREATE INDEX execution_jobs_action_id_idx ON execution_jobs (action_id);
CREATE INDEX watchdog_alerts_job_id_idx ON watchdog_alerts (job_id);
