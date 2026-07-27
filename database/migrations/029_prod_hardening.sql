-- 生产链路硬化：组合按日幂等；卡住的 running 可被识别

-- 清理历史重复活跃组合（保留同日最新一条），再建唯一索引
WITH ranked AS (
    SELECT portfolio_id,
           ROW_NUMBER() OVER (
               PARTITION BY strategy_version, as_of_date, account_id
               ORDER BY created_at DESC
           ) AS rn
    FROM portfolio_target
    WHERE status IN ('running', 'draft', 'approved', 'executed')
)
UPDATE portfolio_target t
SET status = 'superseded',
    error_message = CASE
        WHEN t.error_message IS NULL OR t.error_message = '' THEN 'superseded_by_029'
        ELSE t.error_message || ' | superseded_by_029'
    END
FROM ranked r
WHERE t.portfolio_id = r.portfolio_id AND r.rn > 1;

-- 同一策略/账户/交易日仅允许一条活跃组合（failed/rejected/superseded 可重建）
CREATE UNIQUE INDEX IF NOT EXISTS uq_portfolio_target_day_active
    ON portfolio_target (strategy_version, as_of_date, account_id)
    WHERE status IN ('running', 'draft', 'approved', 'executed');

-- 同 portfolio 至多一条未结束的 execution（防 crash 后双开）
CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_run_portfolio_open
    ON execution_run (portfolio_id)
    WHERE status = 'running';

-- 同 execution 至多一条未结束的 posting
CREATE UNIQUE INDEX IF NOT EXISTS uq_ledger_posting_execution_open
    ON ledger_posting (execution_id)
    WHERE status = 'running';
