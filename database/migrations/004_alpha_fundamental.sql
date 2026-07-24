-- alpha_fundamental ALPHA 基本面表（PostgreSQL）

CREATE TABLE IF NOT EXISTS raw_fund_statement (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    statement_type  TEXT NOT NULL,
    report_period   TEXT NOT NULL,
    announce_date   TEXT NOT NULL,
    item_code       TEXT NOT NULL,
    item_value      DOUBLE PRECISION,
    currency        TEXT,
    report_type     TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, statement_type, report_period, item_code, source)
);

CREATE TABLE IF NOT EXISTS raw_fund_indicator (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    report_period   TEXT NOT NULL,
    announce_date   TEXT,
    indicator_code  TEXT NOT NULL,
    indicator_value DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, report_period, indicator_code, source)
);

CREATE TABLE IF NOT EXISTS raw_consensus_estimate (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    asof_date       TEXT NOT NULL,
    metric          TEXT NOT NULL,
    period_year     TEXT NOT NULL,
    value           DOUBLE PRECISION,
    version         TEXT NOT NULL DEFAULT 'latest',
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, asof_date, metric, period_year, source, version)
);
