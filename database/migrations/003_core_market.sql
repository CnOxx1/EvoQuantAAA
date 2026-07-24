-- core_market CORE 行情表（PostgreSQL）

CREATE TABLE IF NOT EXISTS raw_equity_bar_1d (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    amount          DOUBLE PRECISION,
    turnover        DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, source)
);

CREATE TABLE IF NOT EXISTS raw_adj_factor (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    factor_type     TEXT NOT NULL,
    factor          DOUBLE PRECISION NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, factor_type, source)
);

CREATE TABLE IF NOT EXISTS raw_suspend (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    suspend_type    TEXT,
    reason          TEXT,
    resume_date     TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, event_type, source)
);

CREATE TABLE IF NOT EXISTS raw_limit_board (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    close           DOUBLE PRECISION,
    pct_chg         DOUBLE PRECISION,
    amount          DOUBLE PRECISION,
    first_time      TEXT,
    last_time       TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, event_type, source)
);

CREATE TABLE IF NOT EXISTS raw_index_bar_1d (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    index_symbol    TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    amount          DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (index_symbol, trade_date, source)
);

CREATE TABLE IF NOT EXISTS raw_corp_action (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    ex_date         TEXT NOT NULL,
    action_type     TEXT NOT NULL,
    raw_payload     TEXT,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, ex_date, action_type, source)
);
