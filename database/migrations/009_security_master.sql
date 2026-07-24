-- security_master：Universe 日快照（PostgreSQL）

CREATE TABLE IF NOT EXISTS universe_snapshot (
    universe_snapshot_id TEXT PRIMARY KEY,
    as_of_date           TEXT NOT NULL,
    universe_code        TEXT NOT NULL,
    status               TEXT NOT NULL,
    member_count         INTEGER NOT NULL DEFAULT 0,
    source_note          TEXT,
    job_id               TEXT,
    meta_json            TEXT,
    created_at           TEXT NOT NULL,
    UNIQUE (as_of_date, universe_code)
);

CREATE INDEX IF NOT EXISTS idx_universe_snapshot_code_date
    ON universe_snapshot (universe_code, as_of_date);

CREATE TABLE IF NOT EXISTS universe_snapshot_member (
    id                   BIGSERIAL PRIMARY KEY,
    universe_snapshot_id TEXT NOT NULL,
    symbol               TEXT NOT NULL,
    name                 TEXT,
    exchange             TEXT,
    board                TEXT,
    list_date            TEXT,
    delist_date          TEXT,
    industry_code        TEXT,
    industry_name        TEXT,
    is_st                INTEGER NOT NULL DEFAULT 0,
    treat_type           TEXT,
    index_weight         DOUBLE PRECISION,
    is_eligible          INTEGER NOT NULL DEFAULT 1,
    UNIQUE (universe_snapshot_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_universe_member_symbol
    ON universe_snapshot_member (symbol);

CREATE INDEX IF NOT EXISTS idx_universe_member_snapshot
    ON universe_snapshot_member (universe_snapshot_id);
