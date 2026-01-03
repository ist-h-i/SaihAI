CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
    user_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    role VARCHAR(50),
    skill_level INTEGER CHECK (skill_level BETWEEN 1 AND 10),
    unit_price INTEGER,
    can_overtime BOOLEAN DEFAULT TRUE,
    career_aspiration TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE projects (
    project_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(20),
    budget_cap INTEGER,
    difficulty_level VARCHAR(2),
    required_skills TEXT[],
    description TEXT
);

CREATE TABLE assignments (
    assignment_id SERIAL PRIMARY KEY,
    project_id VARCHAR(10) REFERENCES projects(project_id),
    user_id VARCHAR(10) REFERENCES users(user_id),
    role_in_pj VARCHAR(50),
    start_date DATE,
    end_date DATE,
    remarks TEXT
);

CREATE TABLE weekly_reports (
    report_id SERIAL PRIMARY KEY,
    user_id VARCHAR(10) REFERENCES users(user_id),
    posted_at TIMESTAMP NOT NULL,
    content TEXT NOT NULL,
    content_embedding vector(1024)
);

CREATE TABLE assignment_patterns (
    pattern_id VARCHAR(20) PRIMARY KEY,
    name_ja VARCHAR(50),
    description TEXT
);

CREATE TABLE ai_analysis_results (
    analysis_id SERIAL PRIMARY KEY,
    user_id VARCHAR(10) REFERENCES users(user_id),
    project_id VARCHAR(10) REFERENCES projects(project_id),
    pattern_id VARCHAR(20) REFERENCES assignment_patterns(pattern_id),
    pm_risk_score INTEGER,
    hr_risk_score INTEGER,
    risk_risk_score INTEGER,
    debate_log JSONB,
    final_decision VARCHAR(20),
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE ai_strategy_proposals (
    proposal_id SERIAL PRIMARY KEY,
    project_id VARCHAR(10) REFERENCES projects(project_id),
    plan_type VARCHAR(10),
    is_recommended BOOLEAN DEFAULT FALSE,
    recommendation_score INTEGER,
    description TEXT,
    total_cost INTEGER,
    predicted_future_impact TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE autonomous_actions (
    action_id SERIAL PRIMARY KEY,
    proposal_id INTEGER REFERENCES ai_strategy_proposals(proposal_id),
    action_type VARCHAR(50),
    draft_content TEXT,
    is_approved BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP,
    scheduled_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending'
);

CREATE TABLE user_motivation_history (
    history_id SERIAL PRIMARY KEY,
    user_id VARCHAR(10) REFERENCES users(user_id),
    measured_date DATE,
    score INTEGER,
    ai_summary TEXT
);

CREATE TABLE project_health_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    project_id VARCHAR(10) REFERENCES projects(project_id),
    measured_date DATE,
    budget_usage_rate INTEGER,
    delay_risk_rate INTEGER,
    overall_health VARCHAR(20)
);

CREATE TABLE langgraph_checkpoints (
    thread_id VARCHAR(100) PRIMARY KEY,
    checkpoint BYTEA NOT NULL,
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_profiles (
    user_id VARCHAR(10) PRIMARY KEY REFERENCES users(user_id),
    availability_pct INTEGER,
    notes TEXT
);

CREATE TABLE user_skills (
    user_id VARCHAR(10) REFERENCES users(user_id),
    skill VARCHAR(50) NOT NULL,
    PRIMARY KEY (user_id, skill)
);
