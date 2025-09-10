CREATE TABLE IF NOT EXISTS feedbacks (
    id UUID PRIMARY KEY,
    helpful BOOLEAN NOT NULL,
    question TEXT,
    answer TEXT,
    session_id TEXT,
    sources JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feedbacks_created_at ON feedbacks (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feedbacks_helpful ON feedbacks (helpful);
