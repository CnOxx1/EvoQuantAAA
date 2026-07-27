-- strategy_registry + signal_prod：版本状态机与生产信号权重

CREATE TABLE IF NOT EXISTS strategy_version (
    strategy_version   TEXT PRIMARY KEY,
    strategy_code      TEXT NOT NULL,
    strategy_kind      TEXT NOT NULL,
    status             TEXT NOT NULL,
    params_json        TEXT NOT NULL,
    research_run_id    TEXT,
    backtest_run_id    TEXT,
    artifact_hash      TEXT,
    note               TEXT,
    created_at         TIMESTAMPTZ NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategy_version_code_status
    ON strategy_version (strategy_code, status);

-- 同一 strategy_code 至多一个 LIVE
CREATE UNIQUE INDEX IF NOT EXISTS uq_strategy_version_live_code
    ON strategy_version (strategy_code)
    WHERE status = 'LIVE';

CREATE TABLE IF NOT EXISTS strategy_transition (
    transition_id      TEXT PRIMARY KEY,
    strategy_version   TEXT NOT NULL,
    from_status        TEXT NOT NULL,
    to_status          TEXT NOT NULL,
    actor              TEXT,
    reason             TEXT,
    created_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_strategy_transition_version
    ON strategy_transition (strategy_version, created_at);

CREATE TABLE IF NOT EXISTS signal_batch (
    signal_batch_id        TEXT PRIMARY KEY,
    strategy_version       TEXT NOT NULL,
    status                 TEXT NOT NULL,
    start_date             DATE NOT NULL,
    end_date               DATE NOT NULL,
    as_of_date             DATE,
    universe_code          TEXT,
    universe_snapshot_id   TEXT,
    row_count              INTEGER,
    job_id                 TEXT,
    meta_json              TEXT,
    error_message          TEXT,
    created_at             TIMESTAMPTZ NOT NULL,
    finished_at            TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_signal_batch_version_status
    ON signal_batch (strategy_version, status, created_at);

CREATE TABLE IF NOT EXISTS signal_prod_weight (
    strategy_version   TEXT NOT NULL,
    trade_date         DATE NOT NULL,
    symbol             TEXT NOT NULL,
    weight             DOUBLE PRECISION NOT NULL,
    signal_value       DOUBLE PRECISION,
    signal_batch_id    TEXT NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (strategy_version, trade_date, symbol)
);

CREATE INDEX IF NOT EXISTS idx_signal_prod_weight_batch
    ON signal_prod_weight (signal_batch_id);

CREATE INDEX IF NOT EXISTS idx_signal_prod_weight_date
    ON signal_prod_weight (trade_date, strategy_version);
