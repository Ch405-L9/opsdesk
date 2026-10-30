CREATE TABLE IF NOT EXISTS search_cache (
    query_key TEXT PRIMARY KEY,
    payload_json TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'google_places'
);
