-- risk_engine：风控决策 + Kill Switch

CREATE TABLE IF NOT EXISTS kill_switch (
    scope_key      TEXT PRIMARY KEY,  -- GLOBAL 或 account_id
    is_on          INTEGER NOT NULL DEFAULT 0,
    reason         TEXT,
    actor          TEXT,
    updated_at     TIMESTAMPTZ NOT NULL
);

INSERT INTO kill_switch (scope_key, is_on, reason, actor, updated_at)
VALUES ('GLOBAL', 0, 'seed default off', 'migration', '2026-07-27T00:00:00+00:00')
ON CONFLICT (scope_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS risk_decision (
    decision_id        TEXT PRIMARY KEY,
    portfolio_id       TEXT NOT NULL,
    account_id         TEXT NOT NULL,
    as_of_date         DATE,
    status             TEXT NOT NULL,  -- approved / rejected
    kill_switch_on     INTEGER NOT NULL DEFAULT 0,
    breach_count       INTEGER NOT NULL DEFAULT 0,
    breaches_json      TEXT,
    meta_json          TEXT,
    actor              TEXT,
    job_id             TEXT,
    created_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_risk_decision_portfolio
    ON risk_decision (portfolio_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_risk_decision_status_asof
    ON risk_decision (status, as_of_date);

-- 限额参数（版本化，模块内可读）
CREATE TABLE IF NOT EXISTS risk_limits (
    version              TEXT PRIMARY KEY,
    max_single_weight    DOUBLE PRECISION NOT NULL,
    max_names            INTEGER NOT NULL,
    max_gross_exposure   DOUBLE PRECISION NOT NULL,
    min_names            INTEGER NOT NULL DEFAULT 1,
    meta_json            TEXT,
    created_at           TIMESTAMPTZ NOT NULL
);

INSERT INTO risk_limits (
    version, max_single_weight, max_names, max_gross_exposure, min_names, meta_json, created_at
) VALUES (
    'v1_default',
    0.15,
    50,
    1.01,
    1,
    '{"note":"单票<=15%; 持仓数<=50; 总敞口<=101%"}',
    '2026-07-27T00:00:00+00:00'
) ON CONFLICT (version) DO NOTHING;
