-- BADGR funding tracker schema v1. Money in integer cents. Dates ISO-8601 text.
-- Unknown values are NULL (or 'unknown' for tri-state fields), never zero.

CREATE TABLE opportunities (
    id                      TEXT PRIMARY KEY,
    sponsor                 TEXT NOT NULL,
    program                 TEXT NOT NULL,
    cycle                   TEXT,                      -- e.g. '2026', 'FY27 Phase I'; NULL = unknown/recurring
    dedupe_key              TEXT NOT NULL UNIQUE,
    funding_type            TEXT NOT NULL CHECK (funding_type IN (
                               'grant','prize','loan','loan_support','advisory','workspace',
                               'equipment','transport','property','rd','contracting','lever')),
    official_url            TEXT,
    geography               TEXT,
    for_profit_eligible     TEXT NOT NULL DEFAULT 'unknown' CHECK (for_profit_eligible IN ('yes','no','unknown')),
    ownership_requirements  TEXT,
    revenue_history_rules   TEXT,
    min_months_in_business  INTEGER,
    registrations_required  TEXT,
    prerequisite_tier       TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (prerequisite_tier IN (
                               'NONE','UEI_ONLY','SAM_ACTIVE','GRANTS_GOV_ROLE','HISTORY_MIN',
                               'CERTIFICATION_REQUIRED','COLLATERAL_REPAYMENT','UNKNOWN')),
    amount_min_cents        INTEGER,
    amount_max_cents        INTEGER,
    deadline_date           TEXT,                      -- YYYY-MM-DD; NULL = unknown (never implies rolling)
    deadline_time           TEXT,                      -- HH:MM; NULL = date-only
    deadline_tz             TEXT,
    rolling                 TEXT NOT NULL DEFAULT 'unknown' CHECK (rolling IN ('yes','no','unknown')),
    match_required          TEXT,
    reimbursement_basis     TEXT NOT NULL DEFAULT 'unknown' CHECK (reimbursement_basis IN ('yes','no','unknown')),
    uses_allowed            TEXT,
    uses_disallowed         TEXT,
    fees                    TEXT,
    rate_apr                TEXT,
    term_months             INTEGER,
    guarantee               TEXT,
    collateral              TEXT,
    repayment_gate          TEXT,
    required_documents      TEXT,
    contact                 TEXT,
    source_status           TEXT NOT NULL DEFAULT 'UNVERIFIED_CURRENT' CHECK (source_status IN (
                               'UNVERIFIED_CURRENT','VERIFIED_OPEN','VERIFIED_CLOSED','ROLLING_CONFIRMED',
                               'DISCONTINUED','CHANGED','UNREACHABLE')),
    source_checked_at       TEXT,
    source_checked_tz       TEXT,
    eligibility             TEXT NOT NULL DEFAULT 'unknown' CHECK (eligibility IN ('yes','no','unknown')),
    application_status      TEXT NOT NULL DEFAULT 'NOT_STARTED' CHECK (application_status IN (
                               'NOT_STARTED','PREPARING','BLOCKED','READY_FOR_OWNER_REVIEW',
                               'SUBMITTED_BY_OWNER','AWARDED','DECLINED','WITHDRAWN')),
    effort_hours            INTEGER,
    revisit_date            TEXT,
    next_action             TEXT,
    owner                   TEXT,
    followup_date           TEXT,
    override_score          INTEGER,
    override_reason         TEXT,
    caution                 TEXT,
    notes                   TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    CHECK (override_score IS NULL OR (override_reason IS NOT NULL AND length(trim(override_reason)) > 0)),
    CHECK (amount_min_cents IS NULL OR amount_max_cents IS NULL OR amount_min_cents <= amount_max_cents)
);

CREATE TABLE sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
    url             TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('official','lead')),
    excerpt         TEXT,                      -- short; summary-derived when method says so
    method          TEXT NOT NULL,
    checked_at      TEXT NOT NULL,
    checked_tz      TEXT NOT NULL,
    UNIQUE (opportunity_id, url, checked_at)
);

CREATE TABLE criteria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
    criterion       TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('yes','no','unknown')),
    material        INTEGER NOT NULL DEFAULT 1 CHECK (material IN (0,1)),
    evidence        TEXT,
    UNIQUE (opportunity_id, criterion)
);

CREATE TABLE history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL REFERENCES opportunities(id),
    field           TEXT NOT NULL,
    old_value       TEXT,
    new_value       TEXT,
    changed_at      TEXT NOT NULL,
    reason          TEXT
);

CREATE TABLE review_flags (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    opportunity_id  TEXT NOT NULL,
    other_id        TEXT,
    flag            TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    resolved        INTEGER NOT NULL DEFAULT 0
);
