-- 阶段 16：策略晋升质量门（IC / 回撤 / 样本窗 / 成交笔数）

CREATE TABLE IF NOT EXISTS promotion_gate_params (
    version           TEXT PRIMARY KEY,
    thresholds_json   TEXT NOT NULL,
    meta_json         TEXT,
    created_at        TIMESTAMPTZ NOT NULL
);

INSERT INTO promotion_gate_params (version, thresholds_json, meta_json, created_at)
VALUES (
    'v1_default',
    '{
      "BACKTESTED": {
        "max_drawdown": 0.80,
        "min_total_return": -1.0,
        "min_calendar_days": 1,
        "min_trade_count": 1,
        "require_research_ic": false
      },
      "PAPER": {
        "max_drawdown": 0.50,
        "min_total_return": -0.50,
        "min_calendar_days": 1,
        "min_trade_count": 1,
        "require_research_ic": false
      },
      "LIVE": {
        "max_drawdown": 0.40,
        "min_total_return": -0.10,
        "min_calendar_days": 20,
        "min_trade_count": 1,
        "require_research_ic": true,
        "min_ic_mean": 0.0,
        "min_ic_days": 5
      }
    }',
    '{"note":"BACKTESTED/PAPER 宽松；LIVE 要求样本窗>=20 日且有 IC（research_run）"}',
    '2026-07-27T00:00:00+00:00'
)
ON CONFLICT (version) DO NOTHING;

CREATE TABLE IF NOT EXISTS promotion_gate_result (
    gate_id            TEXT PRIMARY KEY,
    strategy_version   TEXT NOT NULL,
    to_status          TEXT NOT NULL,
    gate_version       TEXT NOT NULL,
    passed             INTEGER NOT NULL,
    skipped            INTEGER NOT NULL DEFAULT 0,
    backtest_run_id    TEXT,
    research_run_id    TEXT,
    metrics_json       TEXT NOT NULL,
    checks_json        TEXT NOT NULL,
    actor              TEXT,
    reason             TEXT,
    created_at         TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_promotion_gate_result_sv
    ON promotion_gate_result (strategy_version, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_promotion_gate_result_pass
    ON promotion_gate_result (passed, to_status, created_at DESC);
