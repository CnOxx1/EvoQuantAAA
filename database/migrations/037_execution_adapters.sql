-- 阶段 20：执行适配器注册（纸面 + 柜台 stub；无真实下单）

CREATE TABLE IF NOT EXISTS execution_adapter_params (
    kind           TEXT PRIMARY KEY,
    enabled        INTEGER NOT NULL DEFAULT 1,
    allow_fills    INTEGER NOT NULL DEFAULT 0,
    require_live_env INTEGER NOT NULL DEFAULT 0,
    meta_json      TEXT,
    created_at     TEXT NOT NULL
);

INSERT INTO execution_adapter_params (
    kind, enabled, allow_fills, require_live_env, meta_json, created_at
) VALUES (
    'paper',
    1,
    1,
    0,
    '{"note":"纸面即时撮合；默认生产路径"}',
    '2026-07-28T00:00:00+00:00'
) ON CONFLICT (kind) DO NOTHING;

INSERT INTO execution_adapter_params (
    kind, enabled, allow_fills, require_live_env, meta_json, created_at
) VALUES (
    'broker_stub',
    1,
    0,
    0,
    '{"note":"柜台骨架：一律 dry_run_no_live 拒单；禁止真实成交"}',
    '2026-07-28T00:00:00+00:00'
) ON CONFLICT (kind) DO NOTHING;
