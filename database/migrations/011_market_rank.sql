-- core_market：市场排名（涨跌幅/成交量/成交额/换手等）

CREATE TABLE IF NOT EXISTS raw_market_rank_1d (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    rank_type       TEXT NOT NULL,
    rank_no         INTEGER NOT NULL,
    symbol          TEXT NOT NULL,
    name            TEXT,
    metric_value    DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    pct_chg         DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    amount          DOUBLE PRECISION,
    turnover        DOUBLE PRECISION,
    extra_json      TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (trade_date, rank_type, symbol, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_market_rank_date_type
    ON raw_market_rank_1d (trade_date, rank_type, rank_no);

CREATE INDEX IF NOT EXISTS idx_raw_market_rank_symbol_date
    ON raw_market_rank_1d (symbol, trade_date);
