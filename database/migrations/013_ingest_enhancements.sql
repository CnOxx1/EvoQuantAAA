-- 估值 / 板块日线 / 限售解禁 / 股东户数（kind 增强，不新建模块）

CREATE TABLE IF NOT EXISTS raw_valuation_1d (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    close           DOUBLE PRECISION,
    pe_ttm          DOUBLE PRECISION,
    pe_static       DOUBLE PRECISION,
    pb              DOUBLE PRECISION,
    ps_ttm          DOUBLE PRECISION,
    pcf_ttm         DOUBLE PRECISION,
    peg             DOUBLE PRECISION,
    total_mv        DOUBLE PRECISION,
    float_mv        DOUBLE PRECISION,
    total_shares    DOUBLE PRECISION,
    float_shares    DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_valuation_1d_date
    ON raw_valuation_1d (trade_date);
CREATE INDEX IF NOT EXISTS idx_raw_valuation_1d_symbol_date
    ON raw_valuation_1d (symbol, trade_date);

CREATE TABLE IF NOT EXISTS raw_board_bar_1d (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    board_type      TEXT NOT NULL,
    board_code      TEXT,
    board_name      TEXT NOT NULL,
    trade_date      TEXT NOT NULL,
    open            DOUBLE PRECISION,
    high            DOUBLE PRECISION,
    low             DOUBLE PRECISION,
    close           DOUBLE PRECISION,
    volume          DOUBLE PRECISION,
    amount          DOUBLE PRECISION,
    pct_chg         DOUBLE PRECISION,
    turnover        DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (board_type, board_name, trade_date, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_board_bar_1d_date
    ON raw_board_bar_1d (trade_date, board_type);
CREATE INDEX IF NOT EXISTS idx_raw_board_bar_1d_name_date
    ON raw_board_bar_1d (board_name, trade_date);

CREATE TABLE IF NOT EXISTS raw_restricted_release (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    name            TEXT,
    release_date    TEXT NOT NULL,
    share_type      TEXT,
    release_shares  DOUBLE PRECISION,
    actual_shares   DOUBLE PRECISION,
    actual_mv       DOUBLE PRECISION,
    float_ratio     DOUBLE PRECISION,
    pre_close       DOUBLE PRECISION,
    pct_chg_b20     DOUBLE PRECISION,
    pct_chg_a20     DOUBLE PRECISION,
    source_event_id TEXT NOT NULL,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, release_date, source_event_id, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_restricted_release_date
    ON raw_restricted_release (release_date);
CREATE INDEX IF NOT EXISTS idx_raw_restricted_release_symbol
    ON raw_restricted_release (symbol, release_date);

CREATE TABLE IF NOT EXISTS raw_holder_count (
    id              BIGSERIAL PRIMARY KEY,
    batch_id        TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    asof_date       TEXT NOT NULL,
    announce_date   TEXT,
    holder_count    DOUBLE PRECISION,
    holder_count_prev DOUBLE PRECISION,
    holder_change   DOUBLE PRECISION,
    holder_change_pct DOUBLE PRECISION,
    avg_market_cap  DOUBLE PRECISION,
    avg_shares      DOUBLE PRECISION,
    total_mv        DOUBLE PRECISION,
    total_shares    DOUBLE PRECISION,
    source          TEXT NOT NULL,
    ingested_at     TEXT NOT NULL,
    UNIQUE (symbol, asof_date, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_holder_count_asof
    ON raw_holder_count (asof_date);
CREATE INDEX IF NOT EXISTS idx_raw_holder_count_symbol
    ON raw_holder_count (symbol, asof_date);
