-- execution：纸面/仿真 OMS 事件（不过账；ledger 消费 fill）

CREATE TABLE IF NOT EXISTS execution_run (
    execution_id       TEXT PRIMARY KEY,
    portfolio_id       TEXT NOT NULL,
    account_id         TEXT NOT NULL,
    adapter            TEXT NOT NULL,
    status             TEXT NOT NULL,
    as_of_date         DATE,
    decision_id        TEXT,
    cost_version       TEXT NOT NULL,
    order_count        INTEGER,
    fill_count         INTEGER,
    job_id             TEXT,
    meta_json          TEXT,
    error_message      TEXT,
    created_at         TIMESTAMPTZ NOT NULL,
    finished_at        TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_run_portfolio_committed
    ON execution_run (portfolio_id)
    WHERE status = 'committed';

CREATE INDEX IF NOT EXISTS idx_execution_run_account_asof
    ON execution_run (account_id, as_of_date, status);

CREATE TABLE IF NOT EXISTS order_event (
    event_id           TEXT PRIMARY KEY,
    order_id           TEXT NOT NULL,
    execution_id       TEXT NOT NULL,
    portfolio_id       TEXT NOT NULL,
    account_id         TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    side               TEXT NOT NULL,
    qty                DOUBLE PRECISION NOT NULL,
    limit_price        DOUBLE PRECISION,
    status             TEXT NOT NULL,
    event_type         TEXT NOT NULL,
    reason             TEXT,
    created_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_order_event_execution
    ON order_event (execution_id, created_at);

CREATE INDEX IF NOT EXISTS idx_order_event_order
    ON order_event (order_id, created_at);

CREATE TABLE IF NOT EXISTS fill_event (
    fill_id            TEXT PRIMARY KEY,
    order_id           TEXT NOT NULL,
    execution_id       TEXT NOT NULL,
    portfolio_id       TEXT NOT NULL,
    account_id         TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    side               TEXT NOT NULL,
    qty                DOUBLE PRECISION NOT NULL,
    price              DOUBLE PRECISION NOT NULL,
    amount             DOUBLE PRECISION NOT NULL,
    commission         DOUBLE PRECISION NOT NULL,
    stamp_tax          DOUBLE PRECISION NOT NULL DEFAULT 0,
    slippage_cost      DOUBLE PRECISION NOT NULL DEFAULT 0,
    trade_date         DATE NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_fill_event_execution
    ON fill_event (execution_id, trade_date);

CREATE INDEX IF NOT EXISTS idx_fill_event_account_date
    ON fill_event (account_id, trade_date);
