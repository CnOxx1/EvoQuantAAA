-- data_quality：DQ 运行与规则结果（PostgreSQL）

CREATE TABLE IF NOT EXISTS dq_run (
    dq_run_id    TEXT PRIMARY KEY,
    scope        TEXT NOT NULL,
    status       TEXT NOT NULL,
    start_date   TEXT,
    end_date     TEXT,
    factor_type  TEXT,
    job_id       TEXT,
    meta_json    TEXT,
    summary_json TEXT,
    created_at   TEXT NOT NULL,
    finished_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_dq_run_scope_status
    ON dq_run (scope, status);

CREATE TABLE IF NOT EXISTS dq_result (
    id           BIGSERIAL PRIMARY KEY,
    dq_run_id    TEXT NOT NULL,
    rule_code    TEXT NOT NULL,
    severity     TEXT NOT NULL,
    status       TEXT NOT NULL,
    message      TEXT,
    detail_json  TEXT,
    checked_at   TEXT NOT NULL,
    UNIQUE (dq_run_id, rule_code)
);

CREATE INDEX IF NOT EXISTS idx_dq_result_run
    ON dq_result (dq_run_id);

CREATE TABLE IF NOT EXISTS dq_gate (
    scope        TEXT NOT NULL,
    start_date   TEXT NOT NULL,
    end_date     TEXT NOT NULL,
    factor_type  TEXT NOT NULL,
    status       TEXT NOT NULL,
    dq_run_id    TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (scope, start_date, end_date, factor_type)
);
