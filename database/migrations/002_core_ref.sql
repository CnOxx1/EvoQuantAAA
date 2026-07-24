-- core_ref CORE 参考数据表（PostgreSQL）

CREATE TABLE IF NOT EXISTS raw_trade_calendar (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    is_open         INTEGER NOT NULL,
    is_half_day     INTEGER NOT NULL DEFAULT 0,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (exchange, trade_date, source)
);

CREATE TABLE IF NOT EXISTS raw_security_listing (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    name            TEXT,
    exchange        TEXT,
    board           TEXT,
    list_date       TEXT,
    delist_date     TEXT,
    effective_date  TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, effective_date, source)
);

CREATE TABLE IF NOT EXISTS raw_industry_class (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    standard        TEXT NOT NULL,
    industry_code   TEXT NOT NULL,
    industry_name   TEXT,
    effective_date  TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, effective_date, standard, source)
);

CREATE TABLE IF NOT EXISTS raw_share_capital (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    total_shares    DOUBLE PRECISION,
    float_shares    DOUBLE PRECISION,
    effective_date  TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, effective_date, source)
);

CREATE TABLE IF NOT EXISTS raw_index_member (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    index_symbol    TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    weight          DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (index_symbol, symbol, trade_date, source)
);

CREATE TABLE IF NOT EXISTS raw_special_treat (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    treat_type      TEXT NOT NULL,
    effective_date  TEXT NOT NULL,
    end_date        TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, effective_date, treat_type, source)
);
