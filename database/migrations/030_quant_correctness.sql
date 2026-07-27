-- 量化正确性补丁：目标持仓 can_sell；策略账户资本配额

ALTER TABLE portfolio_target_position
    ADD COLUMN IF NOT EXISTS can_sell INTEGER;

-- 同账户多策略资本配额（权重之和建议 ≤ 1；未登记则等权）
CREATE TABLE IF NOT EXISTS strategy_capital_alloc (
    account_id         TEXT NOT NULL,
    strategy_version   TEXT NOT NULL,
    capital_weight     DOUBLE PRECISION NOT NULL,
    updated_at         TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (account_id, strategy_version)
);

CREATE INDEX IF NOT EXISTS idx_strategy_capital_alloc_account
    ON strategy_capital_alloc (account_id);
