CREATE TABLE team_suggestion_drafts (
    draft_id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(50) NOT NULL REFERENCES projects(project_id),
    member_ids JSONB NOT NULL,
    min_availability INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX team_suggestion_drafts_project_idx ON team_suggestion_drafts (project_id);

