CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50),
    skill_level INTEGER CHECK (skill_level BETWEEN 1 AND 10),
    unit_id VARCHAR(50),
    cost_per_month INTEGER,
    can_overtime BOOLEAN DEFAULT TRUE,
    career_aspiration TEXT,
    career_genome_vector vector(1024)
);

CREATE TABLE projects (
    project_id VARCHAR(50) PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    manager_id VARCHAR(50) REFERENCES users(user_id),
    status VARCHAR(20),
    budget_cap INTEGER,
    difficulty_level VARCHAR(10),
    required_skills TEXT[],
    description TEXT
);

CREATE TABLE assignments (
    assignment_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    project_id VARCHAR(50) REFERENCES projects(project_id),
    role_in_pj VARCHAR(50),
    allocation_rate DOUBLE PRECISION CHECK (allocation_rate BETWEEN 0.0 AND 1.0),
    start_date DATE,
    end_date DATE
);

CREATE TABLE weekly_reports (
    report_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    project_id VARCHAR(50) REFERENCES projects(project_id),
    reporting_date DATE,
    content_text TEXT,
    content_vector vector(1024),
    reported_at TIMESTAMP
);

CREATE TABLE assignment_patterns (
    pattern_id VARCHAR(50) PRIMARY KEY,
    name_ja VARCHAR(100),
    description TEXT
);

CREATE TABLE ai_analysis_results (
    analysis_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    project_id VARCHAR(50) REFERENCES projects(project_id),
    pattern_id VARCHAR(50) REFERENCES assignment_patterns(pattern_id),
    debate_log JSONB,
    final_decision VARCHAR(20)
);

CREATE TABLE ai_strategy_proposals (
    proposal_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    plan_type VARCHAR(10),
    is_recommended BOOLEAN DEFAULT FALSE,
    description TEXT,
    predicted_future_impact TEXT
);

CREATE TABLE autonomous_actions (
    action_id SERIAL PRIMARY KEY,
    proposal_id INTEGER REFERENCES ai_strategy_proposals(proposal_id),
    action_type VARCHAR(50),
    draft_content TEXT,
    is_approved BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'pending'
);

CREATE TABLE user_motivation_history (
    history_id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    motivation_score DOUBLE PRECISION,
    sentiment_score DOUBLE PRECISION,
    ai_summary TEXT,
    recorded_at DATE
);

CREATE TABLE project_health_snapshots (
    snapshot_id SERIAL PRIMARY KEY,
    project_id VARCHAR(50) REFERENCES projects(project_id),
    health_score DOUBLE PRECISION,
    risk_level VARCHAR(20),
    variance_score DOUBLE PRECISION,
    manager_gap_score DOUBLE PRECISION,
    aggregate_vector vector(1024),
    calculated_at TIMESTAMP
);

CREATE TABLE langgraph_checkpoints (
    thread_id VARCHAR(100) PRIMARY KEY,
    checkpoint BYTEA,
    metadata JSONB
);

CREATE INDEX assignments_user_id_idx ON assignments (user_id);
CREATE INDEX assignments_project_id_idx ON assignments (project_id);
CREATE INDEX weekly_reports_user_id_idx ON weekly_reports (user_id);
CREATE INDEX weekly_reports_project_id_idx ON weekly_reports (project_id);
CREATE INDEX weekly_reports_reporting_date_idx ON weekly_reports (reporting_date);
CREATE INDEX user_motivation_history_user_id_idx ON user_motivation_history (user_id);
CREATE INDEX project_health_snapshots_project_id_idx ON project_health_snapshots (project_id);
CREATE INDEX ai_analysis_results_user_id_idx ON ai_analysis_results (user_id);
CREATE INDEX ai_analysis_results_project_id_idx ON ai_analysis_results (project_id);
CREATE INDEX ai_strategy_proposals_project_id_idx ON ai_strategy_proposals (project_id);
CREATE INDEX autonomous_actions_proposal_id_idx ON autonomous_actions (proposal_id);
