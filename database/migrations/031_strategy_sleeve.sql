-- 阶段 15：策略 sleeve 持仓（同账户共享现金；持仓/批次按 strategy_version 隔离）

ALTER TABLE ledger_lot
    ADD COLUMN IF NOT EXISTS strategy_version TEXT NOT NULL DEFAULT '';

ALTER TABLE ledger_posting
    ADD COLUMN IF NOT EXISTS strategy_version TEXT;

CREATE TABLE IF NOT EXISTS ledger_sleeve_position (
    account_id         TEXT NOT NULL,
    strategy_version   TEXT NOT NULL,
    symbol             TEXT NOT NULL,
    qty                DOUBLE PRECISION NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (account_id, strategy_version, symbol)
);

CREATE INDEX IF NOT EXISTS idx_ledger_sleeve_sv
    ON ledger_sleeve_position (account_id, strategy_version);

CREATE INDEX IF NOT EXISTS idx_ledger_lot_sleeve_sellable
    ON ledger_lot (account_id, strategy_version, symbol, buy_date)
    WHERE qty_remaining > 0;

-- 存量账户级 POSITION 迁入空 strategy_version sleeve（兼容旧单策略数据）
INSERT INTO ledger_sleeve_position (account_id, strategy_version, symbol, qty, updated_at)
SELECT account_id, '', symbol, qty, updated_at
FROM ledger_balance
WHERE asset_type = 'POSITION' AND qty <> 0
ON CONFLICT (account_id, strategy_version, symbol) DO NOTHING;
