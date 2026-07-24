-- alpha_news_monitor ALPHA 媒体新闻（PostgreSQL）

CREATE TABLE IF NOT EXISTS raw_news_media (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    source_news_id  TEXT NOT NULL,
    symbol          TEXT,
    title           TEXT NOT NULL,
    summary         TEXT,
    publish_time    TEXT NOT NULL,
    url             TEXT,
    media_source    TEXT,
    channel         TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (source_news_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_news_publish ON raw_news_media (publish_time);
CREATE INDEX IF NOT EXISTS idx_raw_news_symbol ON raw_news_media (symbol);
CREATE INDEX IF NOT EXISTS idx_raw_news_batch ON raw_news_media (batch_id);

CREATE TABLE IF NOT EXISTS ingest_news_watermark (
    source      TEXT NOT NULL,
    channel     TEXT NOT NULL,
    watch_key   TEXT NOT NULL DEFAULT '',
    watermark   TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (source, channel, watch_key)
);
