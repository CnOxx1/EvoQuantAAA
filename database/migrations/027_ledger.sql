-- ledger：成交事件过账 + 余额 + T+1 批次可卖

CREATE TABLE IF NOT EXISTS ledger_account (
    account_id       TEXT PRIMARY KEY,
    currency         TEXT NOT NULL DEFAULT 'CNY',
    opening_cash     DOUBLE PRECISION NOT NULL,
    status           TEXT NOT NULL DEFAULT 'active',
    meta_json        TEXT,
    created_at       TIMESTAMPTZ NOT NULL
);

INSERT INTO ledger_account (account_id, currency, opening_cash, status, meta_json, created_at)
VALUES (
    'paper_default',
    'CNY',
    1000000.0,
    'active',
    '{"note":"纸面默认账户"}',
    '2026-07-27T00:00:00+00:00'
) ON CONFLICT (account_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS ledger_posting (
    posting_id       TEXT PRIMARY KEY,
    execution_id     TEXT NOT NULL,
    account_id       TEXT NOT NULL,
    status           TEXT NOT NULL,
    as_of_date       DATE,
    entry_count      INTEGER,
    cash_after       DOUBLE PRECISION,
    job_id           TEXT,
    meta_json        TEXT,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL,
    finished_at      TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_posting_execution_committed
    ON ledger_posting (execution_id)
    WHERE status = 'committed';

CREATE INDEX IF NOT EXISTS idx_ledger_posting_account
    ON ledger_posting (account_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ledger_entry (
    entry_id         TEXT PRIMARY KEY,
    posting_id       TEXT NOT NULL,
    account_id       TEXT NOT NULL,
    entry_type       TEXT NOT NULL,
    symbol           TEXT,
    qty              DOUBLE PRECISION,
    amount           DOUBLE PRECISION NOT NULL,
    fill_id          TEXT,
    trade_date       DATE,
    memo             TEXT,
    created_at       TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_entry_posting
    ON ledger_entry (posting_id, created_at);

CREATE INDEX IF NOT EXISTS idx_ledger_entry_account_date
    ON ledger_entry (account_id, trade_date);

CREATE TABLE IF NOT EXISTS ledger_balance (
    account_id       TEXT NOT NULL,
    asset_type       TEXT NOT NULL,
    symbol           TEXT NOT NULL DEFAULT '',
    qty              DOUBLE PRECISION NOT NULL,
    updated_at       TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (account_id, asset_type, symbol)
);

CREATE TABLE IF NOT EXISTS ledger_lot (
    lot_id           TEXT PRIMARY KEY,
    account_id       TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    buy_date         DATE NOT NULL,
    qty_remaining    DOUBLE PRECISION NOT NULL,
    fill_id          TEXT,
    created_at       TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_lot_sellable
    ON ledger_lot (account_id, symbol, buy_date)
    WHERE qty_remaining > 0;
