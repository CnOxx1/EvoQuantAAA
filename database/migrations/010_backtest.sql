-- backtest：费用参数 + 回测 run / NAV / 成交（PostgreSQL）

CREATE TABLE IF NOT EXISTS cost_params (
    version          TEXT PRIMARY KEY,
    commission_rate  DOUBLE PRECISION NOT NULL,
    min_commission   DOUBLE PRECISION NOT NULL,
    stamp_tax_rate   DOUBLE PRECISION NOT NULL,
    slippage_rate    DOUBLE PRECISION NOT NULL,
    lot_size         INTEGER NOT NULL DEFAULT 100,
    meta_json        TEXT,
    created_at       TEXT NOT NULL
);

INSERT INTO cost_params (
    version, commission_rate, min_commission, stamp_tax_rate,
    slippage_rate, lot_size, meta_json, created_at
) VALUES (
    'v1_ashare_default',
    0.0003,
    5.0,
    0.0005,
    0.0005,
    100,
    '{"note":"佣金万三双边下限5；印花税卖出万五；滑点万五"}',
    '2026-07-24T00:00:00+00:00'
) ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS backtest_run (
    run_id                 TEXT PRIMARY KEY,
    strategy_code          TEXT NOT NULL,
    status                 TEXT NOT NULL,
    start_date             TEXT NOT NULL,
    end_date               TEXT NOT NULL,
    universe_code          TEXT,
    universe_snapshot_id   TEXT,
    factor_type            TEXT NOT NULL,
    cost_version           TEXT NOT NULL,
    benchmark_index        TEXT,
    initial_cash           DOUBLE PRECISION NOT NULL,
    final_nav              DOUBLE PRECISION,
    total_return           DOUBLE PRECISION,
    benchmark_return       DOUBLE PRECISION,
    max_drawdown           DOUBLE PRECISION,
    trade_count            INTEGER,
    dq_required            INTEGER NOT NULL DEFAULT 1,
    job_id                 TEXT,
    meta_json              TEXT,
    error_message          TEXT,
    created_at             TEXT NOT NULL,
    finished_at            TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_run_status
    ON backtest_run (status, strategy_code);

CREATE TABLE IF NOT EXISTS backtest_nav (
    id             BIGSERIAL PRIMARY KEY,
    run_id         TEXT NOT NULL,
    trade_date     TEXT NOT NULL,
    nav            DOUBLE PRECISION NOT NULL,
    cash           DOUBLE PRECISION NOT NULL,
    market_value   DOUBLE PRECISION NOT NULL,
    benchmark_nav  DOUBLE PRECISION,
    UNIQUE (run_id, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_backtest_nav_run_date
    ON backtest_nav (run_id, trade_date);

CREATE TABLE IF NOT EXISTS backtest_trade (
    id          BIGSERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    trade_date  TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    shares      DOUBLE PRECISION NOT NULL,
    price       DOUBLE PRECISION NOT NULL,
    amount      DOUBLE PRECISION NOT NULL,
    cost        DOUBLE PRECISION NOT NULL,
    reason      TEXT
);

CREATE INDEX IF NOT EXISTS idx_backtest_trade_run
    ON backtest_trade (run_id, trade_date);
