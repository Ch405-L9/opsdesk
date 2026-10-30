CREATE TABLE IF NOT EXISTS source (
    id INTEGER PRIMARY KEY,
    tool TEXT NOT NULL,
    kind TEXT NOT NULL,
    ref TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    terms_note TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    complete INTEGER NOT NULL DEFAULT 1 CHECK (complete IN (0, 1))
);

CREATE TABLE IF NOT EXISTS lead (
    wb_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_id INTEGER REFERENCES source(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bid (
    wb_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_id INTEGER REFERENCES source(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS job (
    wb_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_id INTEGER REFERENCES source(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS application (
    wb_key TEXT PRIMARY KEY,
    job_key TEXT NOT NULL REFERENCES job(wb_key) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'interested',
    applied_at TEXT,
    receipt_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Workflow data is separated so fetchers/importers can never overwrite user edits.
CREATE TABLE IF NOT EXISTS workflow (
    wb_key TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'new',
    priority TEXT NOT NULL DEFAULT 'normal',
    done INTEGER NOT NULL DEFAULT 0 CHECK (done IN (0, 1)),
    contacted INTEGER NOT NULL DEFAULT 0 CHECK (contacted IN (0, 1)),
    followup_date TEXT,
    followup_note TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS followup (
    id INTEGER PRIMARY KEY,
    wb_key TEXT NOT NULL,
    due_at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    completed_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS note (
    id INTEGER PRIMARY KEY,
    wb_key TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY,
    action TEXT NOT NULL,
    wb_key TEXT,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE IF NOT EXISTS export (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL,
    exported_at TEXT NOT NULL,
    areas_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS export_cell (
    export_id INTEGER NOT NULL REFERENCES export(id) ON DELETE CASCADE,
    wb_key TEXT NOT NULL,
    column_name TEXT NOT NULL,
    value_json TEXT,
    PRIMARY KEY (export_id, wb_key, column_name)
);

CREATE TABLE IF NOT EXISTS quota_ledger (
    provider TEXT NOT NULL,
    period TEXT NOT NULL,
    used INTEGER NOT NULL DEFAULT 0 CHECK (used >= 0),
    free_limit INTEGER NOT NULL CHECK (free_limit >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (provider, period)
);

CREATE INDEX IF NOT EXISTS idx_workflow_followup ON workflow(followup_date, done);
CREATE INDEX IF NOT EXISTS idx_activity_created_at ON activity(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_note_wb_key ON note(wb_key, created_at DESC);
