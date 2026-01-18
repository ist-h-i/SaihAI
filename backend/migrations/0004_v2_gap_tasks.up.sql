CREATE TABLE slack_messages (
    message_id SERIAL PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    message_ts VARCHAR(50) NOT NULL,
    user_id VARCHAR(50),
    text TEXT,
    thread_ts VARCHAR(50),
    client_msg_id VARCHAR(100),
    message_type VARCHAR(30),
    raw_payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX slack_messages_channel_ts_idx ON slack_messages (channel_id, message_ts);
CREATE INDEX slack_messages_thread_ts_idx ON slack_messages (thread_ts);

CREATE TABLE attendance_logs (
    log_id SERIAL PRIMARY KEY,
    employee_id VARCHAR(50) NOT NULL,
    work_date DATE NOT NULL,
    status VARCHAR(30),
    hours_worked DOUBLE PRECISION,
    overtime_hours DOUBLE PRECISION,
    source VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX attendance_logs_employee_date_idx ON attendance_logs (employee_id, work_date);

ALTER TABLE external_action_runs
    ADD COLUMN job_id VARCHAR(50),
    ADD COLUMN action_id INTEGER,
    ADD COLUMN provider VARCHAR(50),
    ADD COLUMN response JSONB,
    ADD COLUMN error TEXT,
    ADD COLUMN executed_at TIMESTAMP;
