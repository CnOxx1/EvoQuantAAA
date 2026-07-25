-- research_lab：基线因子值与实验运行元数据

CREATE TABLE IF NOT EXISTS research_run (
    run_id         TEXT PRIMARY KEY,
    factor_code    TEXT NOT NULL,
    universe_code  TEXT NOT NULL,
    start_date     DATE NOT NULL,
    end_date       DATE NOT NULL,
    status         TEXT NOT NULL,
    meta_json      TEXT,
    created_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_research_run_factor_univ
    ON research_run (factor_code, universe_code, start_date, end_date);

CREATE TABLE IF NOT EXISTS research_factor_value (
    factor_code    TEXT NOT NULL,
    symbol         TEXT NOT NULL,
    trade_date     DATE NOT NULL,
    value          DOUBLE PRECISION,
    universe_code  TEXT NOT NULL,
    run_id         TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (factor_code, symbol, trade_date, universe_code)
);

CREATE INDEX IF NOT EXISTS idx_research_factor_value_lookup
    ON research_factor_value (factor_code, universe_code, trade_date);
CREATE INDEX IF NOT EXISTS idx_research_factor_value_run
    ON research_factor_value (run_id);
