-- 阶段 3：基本面 PIT 区间快照（publish_date = announce_date）

CREATE TABLE IF NOT EXISTS processed_fund_snapshot (
    id                BIGSERIAL PRIMARY KEY,
    process_batch_id  TEXT NOT NULL,
    symbol            TEXT NOT NULL,
    report_period     TEXT NOT NULL,
    publish_date      TEXT NOT NULL,
    valid_from        TEXT NOT NULL,
    valid_to          TEXT,
    revenue           DOUBLE PRECISION,
    net_profit        DOUBLE PRECISION,
    total_assets      DOUBLE PRECISION,
    total_liabilities DOUBLE PRECISION,
    roe               DOUBLE PRECISION,
    eps               DOUBLE PRECISION,
    metrics_json      TEXT,
    source            TEXT NOT NULL,
    processed_at      TEXT NOT NULL,
    UNIQUE (symbol, valid_from)
);

CREATE INDEX IF NOT EXISTS idx_processed_fund_snap_symbol_range
    ON processed_fund_snapshot (symbol, valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_processed_fund_snap_publish
    ON processed_fund_snapshot (publish_date);
