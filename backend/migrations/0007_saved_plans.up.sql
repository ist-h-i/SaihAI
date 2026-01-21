CREATE TABLE saved_plans (
    plan_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL REFERENCES users(user_id),
    simulation_id VARCHAR(64) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content_json JSONB NOT NULL,
    content_text TEXT,
    selected_plan VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX saved_plans_user_idx ON saved_plans (user_id, updated_at);
CREATE INDEX saved_plans_simulation_idx ON saved_plans (simulation_id);
