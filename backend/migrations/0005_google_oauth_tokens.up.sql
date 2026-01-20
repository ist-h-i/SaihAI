CREATE TABLE google_oauth_tokens (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_id),
    google_email VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_type VARCHAR(50),
    scope TEXT,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX google_oauth_tokens_email_idx ON google_oauth_tokens (google_email);
