-- alpha_announcement / ingest_common（PostgreSQL）

CREATE TABLE IF NOT EXISTS ingest_batch (
    batch_id        TEXT PRIMARY KEY,
    ingest_module   TEXT NOT NULL,
    ingest_kind     TEXT NOT NULL,
    lane            TEXT NOT NULL DEFAULT 'ALPHA',
    status          TEXT NOT NULL,
    job_id          TEXT,
    meta_json       TEXT,
    created_at      TEXT NOT NULL,
    committed_at    TEXT,
    failed_at       TEXT,
    error_message   TEXT
);

CREATE TABLE IF NOT EXISTS raw_announcement (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    source_ann_id   TEXT NOT NULL,
    symbol          TEXT,
    title           TEXT NOT NULL,
    publish_time    TEXT NOT NULL,
    category_raw    TEXT NOT NULL,
    category_norm   TEXT,
    url             TEXT,
    content_uri     TEXT,
    content_hash    TEXT,
    channel         TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (source_ann_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_ann_publish ON raw_announcement (publish_time);
CREATE INDEX IF NOT EXISTS idx_raw_ann_symbol ON raw_announcement (symbol);
CREATE INDEX IF NOT EXISTS idx_raw_ann_batch ON raw_announcement (batch_id);

CREATE TABLE IF NOT EXISTS ingest_announcement_watermark (
    source      TEXT NOT NULL,
    channel     TEXT NOT NULL,
    watch_key   TEXT NOT NULL DEFAULT '',
    watermark   TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (source, channel, watch_key)
);
