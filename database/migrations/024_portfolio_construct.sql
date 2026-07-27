-- portfolio_construct：目标持仓草稿（经 signal_prod，未经 risk 放行）

CREATE TABLE IF NOT EXISTS portfolio_target (
    portfolio_id           TEXT PRIMARY KEY,
    strategy_version       TEXT NOT NULL,
    signal_batch_id        TEXT,
    signal_trade_date      DATE,
    as_of_date             DATE NOT NULL,
    account_id             TEXT NOT NULL,
    status                 TEXT NOT NULL,
    nav                    DOUBLE PRECISION NOT NULL,
    cost_version           TEXT NOT NULL,
    universe_code          TEXT,
    row_count              INTEGER,
    invested_value         DOUBLE PRECISION,
    cash_residual          DOUBLE PRECISION,
    job_id                 TEXT,
    meta_json              TEXT,
    error_message          TEXT,
    created_at             TIMESTAMPTZ NOT NULL,
    finished_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_portfolio_target_version_asof
    ON portfolio_target (strategy_version, as_of_date, status);

CREATE INDEX IF NOT EXISTS idx_portfolio_target_account
    ON portfolio_target (account_id, as_of_date);

CREATE TABLE IF NOT EXISTS portfolio_target_position (
    portfolio_id     TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    target_weight    DOUBLE PRECISION NOT NULL,
    target_value     DOUBLE PRECISION NOT NULL,
    target_shares    DOUBLE PRECISION NOT NULL,
    price            DOUBLE PRECISION NOT NULL,
    signal_value     DOUBLE PRECISION,
    signal_weight    DOUBLE PRECISION,
    can_buy          INTEGER,
    status           TEXT NOT NULL DEFAULT 'draft',
    created_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (portfolio_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_target_position_symbol
    ON portfolio_target_position (symbol, portfolio_id);
