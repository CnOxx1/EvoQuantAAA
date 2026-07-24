-- data_process：加工批次与 processed_*（PostgreSQL）

CREATE TABLE IF NOT EXISTS process_batch (
    process_batch_id TEXT PRIMARY KEY,
    process_module   TEXT NOT NULL,
    process_kind     TEXT NOT NULL,
    status           TEXT NOT NULL,
    job_id           TEXT,
    meta_json        TEXT,
    error_message    TEXT,
    created_at       TEXT NOT NULL,
    committed_at     TEXT,
    failed_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_process_batch_kind_status
    ON process_batch (process_kind, status);

CREATE TABLE IF NOT EXISTS processed_equity_bar_1d (
    id               BIGSERIAL PRIMARY KEY,
    process_batch_id TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    trade_date       TEXT NOT NULL,
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
    ret_1d           DOUBLE PRECISION,
    is_suspended     INTEGER NOT NULL DEFAULT 0,
    is_limit_up      INTEGER NOT NULL DEFAULT 0,
    is_limit_down    INTEGER NOT NULL DEFAULT 0,
    can_buy          INTEGER NOT NULL DEFAULT 1,
    can_sell         INTEGER NOT NULL DEFAULT 1,
    source           TEXT NOT NULL,
    processed_at     TEXT NOT NULL,
    UNIQUE (symbol, trade_date, factor_type)
);

CREATE INDEX IF NOT EXISTS idx_processed_equity_1d_date
    ON processed_equity_bar_1d (trade_date);

CREATE INDEX IF NOT EXISTS idx_processed_equity_1d_symbol_date
    ON processed_equity_bar_1d (symbol, trade_date);

CREATE TABLE IF NOT EXISTS processed_index_bar_1d (
    id               BIGSERIAL PRIMARY KEY,
    process_batch_id TEXT NOT NULL,
    index_symbol     TEXT NOT NULL,
    trade_date       TEXT NOT NULL,
    open             DOUBLE PRECISION,
    high             DOUBLE PRECISION,
    low              DOUBLE PRECISION,
    close            DOUBLE PRECISION,
    volume           DOUBLE PRECISION,
    amount           DOUBLE PRECISION,
    ret_1d           DOUBLE PRECISION,
    source           TEXT NOT NULL,
    processed_at     TEXT NOT NULL,
    UNIQUE (index_symbol, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_processed_index_1d_date
    ON processed_index_bar_1d (trade_date);
