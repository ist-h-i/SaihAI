CREATE TABLE hitl_states (
    hitl_state_id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    state JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hitl_approval_requests (
    request_id SERIAL PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    status VARCHAR(30) DEFAULT 'pending',
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE hitl_audit_logs (
    audit_id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES hitl_approval_requests(request_id),
    event_type VARCHAR(50) NOT NULL,
    detail JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE execution_jobs (
    job_id SERIAL PRIMARY KEY,
    request_id INTEGER REFERENCES hitl_approval_requests(request_id),
    status VARCHAR(30) DEFAULT 'queued',
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE watchdog_jobs (
    job_id SERIAL PRIMARY KEY,
    status VARCHAR(30) DEFAULT 'queued',
    payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE watchdog_alerts (
    alert_id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES watchdog_jobs(job_id),
    alert_level VARCHAR(30),
    message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
