-- 分钟 K：15m / 60m（CORE ingest → process → 可选技术指标）

CREATE TABLE IF NOT EXISTS raw_equity_bar_min (
    id           BIGSERIAL PRIMARY KEY,
    batch_id     TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    bar_time     TEXT NOT NULL,          -- YYYY-MM-DD HH:MM:SS（交易所本地时）
    freq         TEXT NOT NULL,          -- 15m | 60m
    open         DOUBLE PRECISION,
    high         DOUBLE PRECISION,
    low          DOUBLE PRECISION,
    close        DOUBLE PRECISION,
    volume       DOUBLE PRECISION,
    amount       DOUBLE PRECISION,
    source       TEXT NOT NULL,
    ingested_at  TEXT NOT NULL,
    UNIQUE (symbol, bar_time, freq, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_equity_min_sym_time
    ON raw_equity_bar_min (symbol, freq, bar_time);
CREATE INDEX IF NOT EXISTS idx_raw_equity_min_batch
    ON raw_equity_bar_min (batch_id);

CREATE TABLE IF NOT EXISTS processed_equity_bar_min (
    id               BIGSERIAL PRIMARY KEY,
    process_batch_id TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    bar_time         TEXT NOT NULL,
    freq             TEXT NOT NULL,
    open             DOUBLE PRECISION,
    high             DOUBLE PRECISION,
    low              DOUBLE PRECISION,
    close            DOUBLE PRECISION,
    volume           DOUBLE PRECISION,
    amount           DOUBLE PRECISION,
    adj_factor       DOUBLE PRECISION NOT NULL,
    factor_type      TEXT NOT NULL,
    adj_open         DOUBLE PRECISION,
    adj_high         DOUBLE PRECISION,
    adj_low          DOUBLE PRECISION,
    adj_close        DOUBLE PRECISION,
    source           TEXT NOT NULL,
    processed_at     TEXT NOT NULL,
    UNIQUE (symbol, bar_time, freq, factor_type)
);

CREATE INDEX IF NOT EXISTS idx_processed_equity_min_sym_time
    ON processed_equity_bar_min (symbol, freq, bar_time);

CREATE TABLE IF NOT EXISTS processed_tech_indicator_min (
    process_batch_id TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    bar_time         TEXT NOT NULL,
    freq             TEXT NOT NULL,
    factor_type      TEXT NOT NULL,
    indicator_code   TEXT NOT NULL,
    value            DOUBLE PRECISION,
    category         TEXT,
    source           TEXT NOT NULL,
    processed_at     TEXT NOT NULL,
    PRIMARY KEY (symbol, bar_time, freq, factor_type, indicator_code)
);

CREATE INDEX IF NOT EXISTS idx_tech_indicator_min_lookup
    ON processed_tech_indicator_min (freq, bar_time, indicator_code);
