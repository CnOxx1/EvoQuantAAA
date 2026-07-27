-- 阶段 17：未成交残差 pending（下日续撮）

ALTER TABLE execution_run
    ADD COLUMN IF NOT EXISTS run_kind TEXT NOT NULL DEFAULT 'portfolio';

ALTER TABLE execution_run
    ADD COLUMN IF NOT EXISTS strategy_version TEXT;

-- 仅 portfolio 类：同 portfolio 至多一 committed（pending_resume 可多日多次）
DROP INDEX IF EXISTS uq_execution_run_portfolio_committed;
CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_run_portfolio_committed
    ON execution_run (portfolio_id)
    WHERE status = 'committed' AND run_kind = 'portfolio';

CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_run_pending_resume_day
    ON execution_run (account_id, as_of_date, strategy_version)
    WHERE status = 'committed'
      AND run_kind = 'pending_resume'
      AND strategy_version IS NOT NULL;

CREATE TABLE IF NOT EXISTS execution_pending (
    pending_id            TEXT PRIMARY KEY,
    account_id            TEXT NOT NULL,
    strategy_version      TEXT NOT NULL,
    symbol                TEXT NOT NULL,
    side                  TEXT NOT NULL,
    qty_remaining         DOUBLE PRECISION NOT NULL,
    qty_origin            DOUBLE PRECISION NOT NULL,
    source_portfolio_id   TEXT NOT NULL,
    source_execution_id   TEXT,
    origin_as_of          DATE NOT NULL,
    last_reason           TEXT,
    status                TEXT NOT NULL,
    meta_json             TEXT,
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_pending_open
    ON execution_pending (account_id, strategy_version, symbol, side)
    WHERE status = 'open';

CREATE INDEX IF NOT EXISTS idx_execution_pending_open_acct
    ON execution_pending (account_id, strategy_version)
    WHERE status = 'open';

CREATE TABLE IF NOT EXISTS execution_pending_event (
    event_id       TEXT PRIMARY KEY,
    pending_id     TEXT NOT NULL,
    execution_id   TEXT,
    trade_date     DATE,
    qty_before     DOUBLE PRECISION NOT NULL,
    qty_after      DOUBLE PRECISION NOT NULL,
    reason         TEXT,
    created_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_execution_pending_event_pending
    ON execution_pending_event (pending_id, created_at);
