-- 日线技术指标（data_process kind=tech_indicator）

CREATE TABLE IF NOT EXISTS processed_tech_indicator_1d (
    process_batch_id TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    trade_date       TEXT NOT NULL,
    factor_type      TEXT NOT NULL,
    indicator_code   TEXT NOT NULL,
    value            DOUBLE PRECISION,
    source           TEXT NOT NULL,
    processed_at     TEXT NOT NULL,
    PRIMARY KEY (symbol, trade_date, factor_type, indicator_code)
);

CREATE INDEX IF NOT EXISTS idx_tech_indicator_date
    ON processed_tech_indicator_1d (trade_date, indicator_code);

CREATE INDEX IF NOT EXISTS idx_tech_indicator_symbol_date
    ON processed_tech_indicator_1d (symbol, trade_date);

CREATE INDEX IF NOT EXISTS idx_tech_indicator_batch
    ON processed_tech_indicator_1d (process_batch_id);
